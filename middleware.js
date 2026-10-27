// Protege jorgesanchez.me/subastas con una contraseña (sin usuario).
// La contraseña vive en Vercel: Settings → Environment Variables → SUBASTAS_PASSWORD.

// También: energycheck.jorgesanchez.me → jorgesanchez.me/energycheck/ (y /host → pantalla del host).

export const config = { matcher: ['/', '/host', '/subastas', '/subastas/:path*'] };

const COOKIE = 'subastas_auth';

async function token(password) {
  const data = new TextEncoder().encode(`subastas-v1:${password}`);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
}

function cookieValue(request) {
  const m = (request.headers.get('cookie') || '').match(new RegExp(`(?:^|;\\s*)${COOKIE}=([a-f0-9]{64})`));
  return m ? m[1] : null;
}

function page(error = '') {
  return new Response(`<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Subastas RGV</title>
<style>
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:#141414;color:#F5F4F0;
       font-family:system-ui,-apple-system,'Segoe UI',sans-serif;padding:16px}
  form{width:100%;max-width:320px;text-align:center}
  h1{font-size:40px;letter-spacing:1px;margin:0 0 24px}
  h1 span{color:#D4A843}
  input{width:100%;box-sizing:border-box;padding:14px;border-radius:10px;border:1px solid #333;
        background:#1f1f1f;color:#F5F4F0;font-size:16px;text-align:center}
  button{width:100%;margin-top:12px;padding:14px;border:0;border-radius:10px;background:#D4A843;
         color:#141414;font-size:16px;font-weight:600;cursor:pointer}
  p{color:#E5675B;font-size:14px;min-height:20px;margin:12px 0 0}
</style></head><body>
<form method="POST" action="/subastas/entrar">
  <h1>Subastas <span>RGV</span></h1>
  <input type="password" name="password" placeholder="Contraseña" autofocus autocomplete="current-password" required>
  <button type="submit">Entrar</button>
  <p>${error}</p>
</form></body></html>`, {
    status: error ? 401 : 200,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' },
  });
}

export default async function middleware(request) {
  const host = (request.headers.get('host') || new URL(request.url).hostname).toLowerCase();
  if (host.startsWith('energycheck.')) {
    const u = new URL(request.url);
    const dest = u.pathname.startsWith('/host')
      ? 'https://jorgesanchez.me/energycheck/#host'
      : 'https://jorgesanchez.me/energycheck/' + u.search;
    return new Response(null, { status: 307, headers: { location: dest, 'cache-control': 'no-store' } });
  }
  if (!new URL(request.url).pathname.startsWith('/subastas')) return; // resto del sitio: sin cambios

  const password = process.env.SUBASTAS_PASSWORD;
  if (!password) {
    return new Response('Falta configurar SUBASTAS_PASSWORD en Vercel.', { status: 503 });
  }
  const valid = await token(password);
  const url = new URL(request.url);

  if (url.pathname === '/subastas/entrar' && request.method === 'POST') {
    const form = await request.formData();
    if ((form.get('password') || '') === password) {
      return new Response(null, {
        status: 303,
        headers: {
          location: '/subastas/',
          'set-cookie': `${COOKIE}=${valid}; Path=/subastas; Max-Age=2592000; HttpOnly; Secure; SameSite=Lax`,
        },
      });
    }
    return page('Contraseña incorrecta');
  }

  if (url.pathname === '/subastas/salir') {
    return new Response(null, {
      status: 303,
      headers: { location: '/subastas/', 'set-cookie': `${COOKIE}=; Path=/subastas; Max-Age=0` },
    });
  }

  if (cookieValue(request) === valid) return; // contraseña correcta: deja pasar
  return page();
}
