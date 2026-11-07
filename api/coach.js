import { getOuraDays, chicagoToday, addDays } from './_oura.js';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();

  // ── GET OURA DATA ─────────────────────────────
  if (req.method === 'GET' && req.query.source === 'oura') {
    try {
      const token = process.env.OURA_ACCESS_TOKEN;
      const today = chicagoToday();
      const days = await getOuraDays(token, addDays(today, -1), today);
      const sorted = Object.keys(days).sort().reverse();
      // Last night's sleep is filed under today's date; fall back to yesterday if not synced yet
      const sleepDay = sorted.find(d => days[d].totalSleep || days[d].readinessScore) || sorted[0];
      const actDay   = sorted.find(d => days[d].steps) || sleepDay;
      const s = days[sleepDay] || {}, a = days[actDay] || {};

      const ouraData = {
        sleepScore: s.sleepScore ?? null, totalSleep: s.totalSleep ?? null,
        deepSleep: s.deepSleep ?? null, remSleep: s.remSleep ?? null, lightSleep: s.lightSleep ?? null,
        sleepEfficiency: s.sleepEfficiency ?? null, sleepLatency: s.sleepLatency ?? null,
        readinessScore: s.readinessScore ?? null, hrv: s.hrv ?? null, rhr: s.rhr ?? null,
        bodyTemp: s.bodyTemp ?? null,
        steps: a.steps ?? null, activityScore: a.activityScore ?? null,
        activeCalories: a.activeCalories ?? null, totalCalories: a.totalCalories ?? null,
        date: sleepDay || today,
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
          model: 'claude-sonnet-4-6',
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
