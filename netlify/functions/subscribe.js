// Netlify Function — proxies subscribe requests to Beehiiv's v2 API.
// Keeps BEEHIIV_API_KEY server-side; never exposed to the browser.
//
// Env vars required in Netlify → Site settings → Environment variables:
//   BEEHIIV_API_KEY  — Beehiiv API key (Settings → API)
//   BEEHIIV_PUB_ID   — pub_xxxxxxxx (Settings → API)
//
// Frontend POSTs JSON { email } to /.netlify/functions/subscribe.
// Response: { ok: true } on 2xx, { ok: false, error } on failure.

export const config = {
  path: '/api/subscribe',  // friendlier URL — also reachable at /.netlify/functions/subscribe
};

export default async (req, context) => {
  // CORS / method guard
  if (req.method !== 'POST') {
    return json({ ok: false, error: 'method_not_allowed' }, 405);
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: 'invalid_json' }, 400);
  }

  const email = (body?.email || '').trim().toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ ok: false, error: 'invalid_email' }, 400);
  }

  const apiKey = process.env.BEEHIIV_API_KEY;
  const pubId  = process.env.BEEHIIV_PUB_ID;
  if (!apiKey || !pubId) {
    return json({ ok: false, error: 'server_misconfigured' }, 500);
  }

  // Optional: capture the page they subscribed from (utm-ish attribution).
  const referrer = req.headers.get('referer') || 'https://allcitygreens.com';

  const upstream = await fetch(
    `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type':  'application/json',
        'Accept':        'application/json',
      },
      body: JSON.stringify({
        email,
        reactivate_existing: true,
        send_welcome_email: true,
        utm_source: 'allcitygreens.com',
        utm_medium: 'website-form',
        referring_site: referrer,
      }),
    },
  );

  const text = await upstream.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = { _raw: text }; }

  if (upstream.ok) {
    // Surface the Beehiiv subscription status so the client (and we) can see
    // what Beehiiv actually did with the request — active / pending / validating
    // etc. Useful for debugging double-opt-in vs. invalid-domain rejection.
    const sub = (payload && (payload.data || payload)) || {};
    return json({
      ok: true,
      beehiiv_status:  sub.status || null,
      beehiiv_id:      sub.id || null,
      upstream_status: upstream.status,
    });
  }

  // Beehiiv sometimes returns 400 "email already subscribed" — treat as success
  // so the UI stays friendly. Adjust check if the response shape differs.
  const msg = JSON.stringify(payload).toLowerCase();
  if (msg.includes('already') || msg.includes('exists')) {
    return json({ ok: true, already_subscribed: true });
  }

  return json(
    { ok: false, error: 'beehiiv_error', status: upstream.status, detail: payload },
    upstream.status >= 500 ? 502 : 400,
  );
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
      // Allow same-origin POSTs from the site itself
      'Access-Control-Allow-Origin': '*',
    },
  });
}
