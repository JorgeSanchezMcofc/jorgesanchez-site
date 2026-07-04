// api/snapshot.js
// Cron job — runs at 11:59 PM every day
// Pulls Oura data and saves to Google Sheets automatically

export default async function handler(req, res) {
  // Only allow cron calls from Vercel or manual GET for testing
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const token = process.env.OURA_ACCESS_TOKEN;
    const sheetUrl = process.env.SHEET_URL;

    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];

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
      sleepRes.json(),
      sleepDetailRes.json(),
      readinessRes.json(),
      activityRes.json()
    ]);

    // Extract data
    const latestSleep     = sleepData.data?.[sleepData.data.length - 1] || {};
    const sleepSessions   = sleepDetailData.data || [];
    const mainSleep       = sleepSessions
      .filter(s => s.type === 'long_sleep' || s.type === 'sleep')
      .sort((a, b) => (b.total_sleep_duration || 0) - (a.total_sleep_duration || 0))[0] || {};
    const latestReadiness = readinessData.data?.[readinessData.data.length - 1] || {};
    const latestActivity  = activityData.data?.[activityData.data.length - 1] || {};

    const snapshot = {
      date:          today,
      day:           'auto',
      weight:        '',  // not available from Oura
      calories:      '',  // not available from Oura
      protein:       '',  // not available from Oura
      carbs:         '',  // not available from Oura
      fat:           '',  // not available from Oura
      steps:         latestActivity.steps || '',
      sleep:         mainSleep.total_sleep_duration
                       ? Math.round((mainSleep.total_sleep_duration / 3600) * 10) / 10
                       : '',
      hrv:           mainSleep.average_hrv
                       ? Math.round(mainSleep.average_hrv)
                       : '',
      readiness:     latestReadiness.score || '',
      sleepScore:    latestSleep.score || '',
      activityScore: latestActivity.score || '',
      rhr:           mainSleep.lowest_heart_rate
                       || latestReadiness.lowest_heart_rate
                       || '',
      // Extra Oura fields
      deepSleep:     mainSleep.deep_sleep_duration
                       ? Math.round((mainSleep.deep_sleep_duration / 3600) * 10) / 10
                       : '',
      remSleep:      mainSleep.rem_sleep_duration
                       ? Math.round((mainSleep.rem_sleep_duration / 3600) * 10) / 10
                       : '',
      sleepEfficiency: mainSleep.efficiency || '',
      bodyTemp:      latestReadiness.temperature_deviation || '',
      activeCalories: latestActivity.active_calories || '',
      source:        'oura_auto'  // marks this row as auto-generated
    };

    // Send to Google Sheets
    await fetch(sheetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(snapshot)
    });

    console.log(`[snapshot] ${today} — saved to Sheets`, snapshot);

    return res.status(200).json({
      success: true,
      date: today,
      data: snapshot
    });

  } catch (error) {
    console.error('[snapshot] Error:', error);
    return res.status(500).json({ error: error.message });
  }
}
