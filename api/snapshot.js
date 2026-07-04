// api/snapshot.js
// Cron job — runs at 11:59 PM CST every day
// Pulls Oura data and merges into existing row or creates new one

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const token    = process.env.OURA_ACCESS_TOKEN;
    const sheetUrl = process.env.SHEET_URL;

    const today = new Date().toISOString().split('T')[0];

    // Fetch all Oura endpoints in parallel
    const [sleepRes, sleepDetailRes, readinessRes, activityRes] = await Promise.all([
      fetch(`https://api.ouraring.com/v2/usercollection/daily_sleep?start_date=${today}&end_date=${today}`, {
        headers: { Authorization: `Bearer ${token}` }
      }),
      fetch(`https://api.ouraring.com/v2/usercollection/sleep?start_date=${today}&end_date=${today}`, {
        headers: { Authorization: `Bearer ${token}` }
      }),
      fetch(`https://api.ouraring.com/v2/usercollection/daily_readiness?start_date=${today}&end_date=${today}`, {
        headers: { Authorization: `Bearer ${token}` }
      }),
      fetch(`https://api.ouraring.com/v2/usercollection/daily_activity?start_date=${today}&end_date=${today}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
    ]);

    const [sleepData, sleepDetailData, readinessData, activityData] = await Promise.all([
      sleepRes.json(), sleepDetailRes.json(), readinessRes.json(), activityRes.json()
    ]);

    const latestSleep     = sleepData.data?.[sleepData.data.length - 1] || {};
    const sleepSessions   = sleepDetailData.data || [];
    const mainSleep       = sleepSessions
      .filter(s => s.type === 'long_sleep' || s.type === 'sleep')
      .sort((a, b) => (b.total_sleep_duration || 0) - (a.total_sleep_duration || 0))[0] || {};
    const latestReadiness = readinessData.data?.[readinessData.data.length - 1] || {};
    const latestActivity  = activityData.data?.[activityData.data.length - 1] || {};

    const ouraFields = {
      steps:           latestActivity.steps || '',
      sleep:           mainSleep.total_sleep_duration
                         ? Math.round((mainSleep.total_sleep_duration / 3600) * 10) / 10 : '',
      hrv:             mainSleep.average_hrv ? Math.round(mainSleep.average_hrv) : '',
      readiness:       latestReadiness.score || '',
      sleepScore:      latestSleep.score || '',
      activityScore:   latestActivity.score || '',
      rhr:             mainSleep.lowest_heart_rate || latestReadiness.lowest_heart_rate || '',
      deepSleep:       mainSleep.deep_sleep_duration
                         ? Math.round((mainSleep.deep_sleep_duration / 3600) * 10) / 10 : '',
      remSleep:        mainSleep.rem_sleep_duration
                         ? Math.round((mainSleep.rem_sleep_duration / 3600) * 10) / 10 : '',
      sleepEfficiency: mainSleep.efficiency || '',
      bodyTemp:        latestReadiness.temperature_deviation || '',
      activeCalories:  latestActivity.active_calories || '',
    };

    // Send to Sheets with merge flag — Apps Script will handle upsert
    const payload = {
      date:   today,
      day:    'auto',
      source: 'oura_auto',
      merge:  true,  // tells Apps Script to update existing row if date exists
      ...ouraFields
    };

    await fetch(sheetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    return res.status(200).json({ success: true, date: today, data: payload });

  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
}
