// api/_oura.js — shared Oura helpers (files starting with _ are not deployed as routes)
//
// Quirk: /v2/usercollection/sleep treats end_date as EXCLUSIVE, while the daily_*
// endpoints are inclusive. Querying sleep with end_date = today returned the previous
// night, so the sleep range is padded by one day. Oura also returns naps and rests
// per day, so the night is the long_sleep record, falling back to the longest one.

export function addDays(iso, n) {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().split('T')[0];
}

export function chicagoToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Chicago' }).format(new Date());
}

const MONS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
export function sheetDate(iso) {
  const [, m, d] = iso.split('-').map(Number);
  return `${MONS[m - 1]} ${d}`; // same "Nov 6" format the app's manual log uses
}

async function getAll(token, path, start, end) {
  const out = [];
  let next = null;
  do {
    const url = `https://api.ouraring.com/v2/usercollection/${path}?start_date=${start}&end_date=${end}`
      + (next ? `&next_token=${encodeURIComponent(next)}` : '');
    const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`Oura ${path} ${r.status}`);
    const j = await r.json();
    out.push(...(j.data || []));
    next = j.next_token || null;
  } while (next);
  return out;
}

const hrs = s => (s ? Math.round((s / 3600) * 10) / 10 : null);

// Returns { 'YYYY-MM-DD': {...fields} } for every day in [from, to] that has any data
export async function getOuraDays(token, from, to) {
  const [daily, sleeps, readiness, activity] = await Promise.all([
    getAll(token, 'daily_sleep', from, to),
    getAll(token, 'sleep', from, addDays(to, 1)),
    getAll(token, 'daily_readiness', from, to),
    getAll(token, 'daily_activity', from, to),
  ]);

  const byDay = (arr) => Object.fromEntries(arr.map(x => [x.day, x]));
  const dS = byDay(daily), dR = byDay(readiness), dA = byDay(activity);

  const night = {};
  for (const s of sleeps) {
    if (s.day < from || s.day > to) continue;
    if (!['long_sleep', 'sleep'].includes(s.type)) continue;
    const cur = night[s.day];
    const better = !cur
      || (s.type === 'long_sleep' && cur.type !== 'long_sleep')
      || (s.type === cur.type && (s.total_sleep_duration || 0) > (cur.total_sleep_duration || 0));
    if (better) night[s.day] = s;
  }

  const days = {};
  for (let d = from; d <= to; d = addDays(d, 1)) {
    const s = night[d] || {}, ds = dS[d] || {}, r = dR[d] || {}, a = dA[d] || {};
    const f = {
      sleepScore:      ds.score ?? null,
      totalSleep:      hrs(s.total_sleep_duration),
      deepSleep:       hrs(s.deep_sleep_duration),
      remSleep:        hrs(s.rem_sleep_duration),
      lightSleep:      hrs(s.light_sleep_duration),
      sleepEfficiency: s.efficiency ?? null,
      sleepLatency:    s.latency ? Math.round(s.latency / 60) : null,
      readinessScore:  r.score ?? null,
      hrv:             s.average_hrv ? Math.round(s.average_hrv) : null, // real ms, not hrv_balance
      rhr:             s.lowest_heart_rate ?? null,
      bodyTemp:        r.temperature_deviation ?? null,
      steps:           a.steps ?? null,
      activityScore:   a.score ?? null,
      activeCalories:  a.active_calories ?? null,
      totalCalories:   a.total_calories ?? null,
    };
    if (Object.values(f).some(v => v !== null)) days[d] = f;
  }
  return days;
}

// Shape expected by the Google Sheets Apps Script upsert
export function toSheetRow(iso, f) {
  const v = x => (x === null || x === undefined ? '' : x);
  return {
    date: sheetDate(iso), day: 'auto', source: 'oura_auto', merge: true,
    steps: v(f.steps), sleep: v(f.totalSleep), hrv: v(f.hrv), readiness: v(f.readinessScore),
    sleepScore: v(f.sleepScore), activityScore: v(f.activityScore), rhr: v(f.rhr),
    deepSleep: v(f.deepSleep), remSleep: v(f.remSleep), sleepEfficiency: v(f.sleepEfficiency),
    bodyTemp: v(f.bodyTemp), activeCalories: v(f.activeCalories),
  };
}
