// api/export.js — read-only Oura export with a copy button (no writes to Sheets)
//   /api/export?from=2026-08-28&to=2026-11-06

import { getOuraDays, chicagoToday, addDays } from './_oura.js';

export const config = { maxDuration: 30 };

const ISO = /^\d{4}-\d{2}-\d{2}$/;
const COLS = ['steps','totalSleep','hrv','readinessScore','sleepScore','activityScore','rhr',
              'deepSleep','remSleep','sleepEfficiency','bodyTemp','activeCalories'];

export default async function handler(req, res) {
  try {
    const q = req.query || {};
    const to = ISO.test(q.to || '') ? q.to : addDays(chicagoToday(), -1);
    const from = ISO.test(q.from || '') ? q.from : addDays(to, -30);
    const days = await getOuraDays(process.env.OURA_ACCESS_TOKEN, from, to);
    const lines = ['date,' + COLS.join(',')].concat(
      Object.keys(days).sort().map(d => [d, ...COLS.map(c => days[d][c] ?? '')].join(','))
    );
    const csv = lines.join('\n');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.status(200).send(`<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oura export</title></head><body style="font-family:-apple-system,sans-serif;background:#111;color:#eee;padding:16px">
<h2 style="margin:0 0 8px">Oura ${from} → ${to}</h2><p>${lines.length - 1} días</p>
<button id="b" style="font-size:20px;padding:14px 22px;border-radius:12px;border:0;background:#4ade80;color:#000;width:100%">Copiar datos</button>
<textarea id="t" readonly style="width:100%;height:55vh;margin-top:12px;font-size:11px;background:#000;color:#9f9">${csv}</textarea>
<script>document.getElementById('b').onclick=async()=>{const t=document.getElementById('t');t.select();
try{await navigator.clipboard.writeText(t.value)}catch(e){document.execCommand('copy')}
document.getElementById('b').textContent='¡Copiado! Pégalo en Claude';};</script></body></html>`);
  } catch (e) {
    res.status(500).send(`Error: ${e.message}`);
  }
}
