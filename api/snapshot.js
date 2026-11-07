// api/snapshot.js
// Cron job: runs at 11:59 PM CST (05:59 UTC) every day.
// Pulls Oura data for Jorge's local day and upserts it into Google Sheets.
//
//   /api/snapshot                                  → today (America/Chicago)
//   /api/snapshot?date=2026-11-01                  → one day
//   /api/snapshot?from=2026-07-06&to=2026-11-06    → backfill a range

import { getOuraDays, toSheetRow, chicagoToday } from './_oura.js';

export const config = { maxDuration: 60 };

const ISO = /^\d{4}-\d{2}-\d{2}$/;

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const token    = process.env.OURA_ACCESS_TOKEN;
    const sheetUrl = process.env.SHEET_URL;
    const q = req.query || {};

    let from, to;
    if (ISO.test(q.from || '') && ISO.test(q.to || '')) { from = q.from; to = q.to; }
    else if (ISO.test(q.date || '')) { from = to = q.date; }
    else { from = to = chicagoToday(); }
    if (from > to) return res.status(400).json({ error: 'from is after to' });

    const days = await getOuraDays(token, from, to);
    const dates = Object.keys(days).sort();
    if (!dates.length) return res.status(200).json({ success: false, from, to, reason: 'No Oura data returned' });

    // Write in small parallel batches so a long backfill fits in the time limit
    const written = [], failed = [];
    for (let i = 0; i < dates.length; i += 6) {
      const batch = dates.slice(i, i + 6);
      await Promise.all(batch.map(async d => {
        try {
          const r = await fetch(sheetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSheetRow(d, days[d])),
          });
          (r.ok ? written : failed).push(d);
        } catch { failed.push(d); }
      }));
    }

    return res.status(200).json({ success: failed.length === 0, from, to, written: written.length, failed, sample: days[dates[dates.length - 1]] });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
}
