// Netlify Function — proxies subscribe requests to the newsletter provider.
// Keeps the API key server-side; never exposed to the browser.
//
// 2026-10-10: provider is EmailOctopus (API v2, POST /lists/{id}/contacts).
// Front-end contract unchanged: POST JSON { email } to /api/subscribe →
// { ok: true[, already_subscribed: true] } or { ok: false, error }.
//
// Env vars (Netlify → Site configuration → Environment variables):
//   EMAILOCTOPUS_API_KEY  — EmailOctopus API key (Account → Integrations & API)
//   EMAILOCTOPUS_LIST_ID  — the list sign-ups join
// Fallback: if those are unset but BEEHIIV_API_KEY + BEEHIIV_PUB_ID are, sign-ups
// go to Beehiiv as before. The error code stays 'beehiiv_error' on purpose: every
// page's inline script maps that value to "Our newsletter provider rejected that".

export const config = {
  path: '/api/subscribe',  // also reachable at /.netlify/functions/subscribe
};

export default async (req, context) => {
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

  // .trim(): a pasted key often carries a stray space/newline.
  const eoKey  = (process.env.EMAILOCTOPUS_API_KEY || '').trim().replace(/^Bearer\s+/i, '');
  const eoList = (process.env.EMAILOCTOPUS_LIST_ID || '').trim();
  if (eoKey && eoList) return subscribeEmailOctopus(email, eoKey, eoList);

  if (process.env.BEEHIIV_API_KEY && process.env.BEEHIIV_PUB_ID) {
    return subscribeBeehiiv(email, req);
  }
  return json({ ok: false, error: 'server_misconfigured' }, 500);
};

// 2026-10-10: EmailOctopus API v2. 201 = added; 409 = already on the list.
// Never resubscribes someone who unsubscribed (POST, not the PUT upsert).
async function subscribeEmailOctopus(email, key, listId) {
  let upstream, text;
  try {
    upstream = await fetch(
      `https://api.emailoctopus.com/lists/${encodeURIComponent(listId)}/contacts`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${key}`,
          'Content-Type':  'application/json',
          'Accept':        'application/json',
        },
        body: JSON.stringify({ email_address: email, status: 'subscribed' }),
      },
    );
    text = await upstream.text();
  } catch {
    return json({ ok: false, error: 'upstream_unreachable' }, 502);
  }
  if (upstream.status === 201 || upstream.status === 200) return json({ ok: true, provider: 'emailoctopus' });
  if (upstream.status === 409) return json({ ok: true, already_subscribed: true });
  console.error('subscribe: EmailOctopus rejected', upstream.status, (text || '').slice(0, 300));
  return json({ ok: false, error: 'beehiiv_error', status: upstream.status },
              upstream.status >= 500 ? 502 : 400);
}

// Older provider, used only while the EmailOctopus env vars are unset.
async function subscribeBeehiiv(email, req) {
  const referrer = req.headers.get('referer') || 'https://allcitygreens.com';
  let upstream, text;
  try {
    upstream = await fetch(
      `https://api.beehiiv.com/v2/publications/${process.env.BEEHIIV_PUB_ID}/subscriptions`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${process.env.BEEHIIV_API_KEY}`,
          'Content-Type':  'application/json',
          'Accept':        'application/json',
        },
        body: JSON.stringify({
          email,
          reactivate_existing: true,
          send_welcome_email: true,
          double_opt_override: 'on',
          utm_source: 'allcitygreens.com',
          utm_medium: 'website-form',
          referring_site: referrer,
        }),
      },
    );
    text = await upstream.text();
  } catch {
    return json({ ok: false, error: 'upstream_unreachable' }, 502);
  }
  if (upstream.ok) return json({ ok: true, provider: 'beehiiv' });
  const msg = (text || '').toLowerCase();
  if (msg.includes('already') || msg.includes('exists')) {
    return json({ ok: true, already_subscribed: true });
  }
  return json({ ok: false, error: 'beehiiv_error', status: upstream.status },
              upstream.status >= 500 ? 502 : 400);
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
