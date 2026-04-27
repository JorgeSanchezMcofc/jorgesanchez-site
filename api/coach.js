export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();

  // ── GET OURA DATA ─────────────────────────────
  if (req.method === 'GET' && req.query.source === 'oura') {
    try {
      const token = process.env.OURA_ACCESS_TOKEN;
      const today = new Date().toISOString().split('T')[0];
      const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];

      // Fetch all Oura endpoints in parallel
      const [sleepRes, sleepDetailRes, readinessRes, activityRes] = await Promise.all([
        fetch(`https://api.ouraring.com/v2/usercollection/daily_sleep?start_date=${yesterday}&end_date=${today}`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`https://api.ouraring.com/v2/usercollection/sleep?start_date=${yesterday}&end_date=${today}`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`https://api.ouraring.com/v2/usercollection/daily_readiness?start_date=${yesterday}&end_date=${today}`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`https://api.ouraring.com/v2/usercollection/daily_activity?start_date=${yesterday}&end_date=${today}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      const [sleepData, sleepDetailData, readinessData, activityData] = await Promise.all([
        sleepRes.json(),
        sleepDetailRes.json(),
        readinessRes.json(),
        activityRes.json()
      ]);

      // Latest daily sleep score
      const latestSleep = sleepData.data?.[sleepData.data.length - 1] || {};

      // Detailed sleep — find longest session (main sleep)
      const sleepSessions = sleepDetailData.data || [];
      const mainSleep = sleepSessions
        .filter(s => s.type === 'long_sleep' || s.type === 'sleep')
        .sort((a, b) => (b.total_sleep_duration || 0) - (a.total_sleep_duration || 0))[0] || {};

      // Readiness
      const latestReadiness = readinessData.data?.[readinessData.data.length - 1] || {};

      // Activity
      const latestActivity = activityData.data?.[activityData.data.length - 1] || {};

      const ouraData = {
        // Sleep — from daily_sleep (score) + sleep (details)
        sleepScore: latestSleep.score || null,
        totalSleep: mainSleep.total_sleep_duration
          ? Math.round((mainSleep.total_sleep_duration / 3600) * 10) / 10
          : null,
        deepSleep: mainSleep.deep_sleep_duration
          ? Math.round((mainSleep.deep_sleep_duration / 3600) * 10) / 10
          : null,
        remSleep: mainSleep.rem_sleep_duration
          ? Math.round((mainSleep.rem_sleep_duration / 3600) * 10) / 10
          : null,
        lightSleep: mainSleep.light_sleep_duration
          ? Math.round((mainSleep.light_sleep_duration / 3600) * 10) / 10
          : null,
        sleepEfficiency: mainSleep.efficiency || null,
        sleepLatency: mainSleep.latency ? Math.round(mainSleep.latency / 60) : null,

        // Readiness
        readinessScore: latestReadiness.score || null,
        hrv: latestReadiness.contributors?.hrv_balance
          ? Math.round(latestReadiness.contributors.hrv_balance)
          : null,
        rhr: latestReadiness.contributors?.resting_heart_rate || 62,
        bodyTemp: latestReadiness.temperature_deviation || null,

        // Activity
        steps: latestActivity.steps || null,
        activityScore: latestActivity.score || null,
        activeCalories: latestActivity.active_calories || null,
        totalCalories: latestActivity.total_calories || null,

        // Meta
        date: yesterday,
        fetchedAt: new Date().toISOString()
      };

      return res.status(200).json({ oura: ouraData });

    } catch (error) {
      console.error('Oura API error:', error);
      return res.status(500).json({ error: 'Could not fetch Oura data' });
    }
  }

  // ── GET LOGS FROM GOOGLE SHEETS ───────────────
  if (req.method === 'GET') {
    try {
      const response = await fetch(process.env.SHEET_URL);
      const data = await response.json();
      return res.status(200).json(data);
    } catch (error) {
      return res.status(500).json({ error: 'Could not read from Sheets' });
    }
  }

  // ── POST — AI ANALYSIS VIA CLAUDE ─────────────
  if (req.method === 'POST') {
    try {
      const { system, prompt } = req.body;

      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 1000,
          system: system,
          messages: [{ role: 'user', content: prompt }]
        })
      });

      const data = await response.json();
      if (data.error) return res.status(400).json({ error: data.error.message });
      return res.status(200).json({ text: data.content[0].text });

    } catch (error) {
      return res.status(500).json({ error: 'Coach offline' });
    }
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
