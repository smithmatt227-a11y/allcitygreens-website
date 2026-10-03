// Netlify Function — proxies subscribe requests to MailerLite's API.
// Keeps the API token server-side; never exposed to the browser.
//
// 2026-10-02: switched from Beehiiv to MailerLite. Beehiiv locked Custom HTML on
// its Free plan, so the newsletter now goes out through MailerLite (STATUS.md
// §0zk). The front-end contract is unchanged: POST JSON { email } to
// /api/subscribe → { ok: true[, already_subscribed: true] } or { ok: false, error }.
//
// Env vars required in Netlify → Site configuration → Environment variables:
//   MAILERLITE_API_KEY     — MailerLite API token (Integrations → API)
//   MAILERLITE_GROUP_ID    — optional; the group new subscribers join. If unset,
//                            the group is looked up by MAILERLITE_GROUP_NAME.
//   MAILERLITE_GROUP_NAME  — optional; defaults to "Newsletter" — the group the
//                            daily campaign (mailerlite_publish.py) sends to.
//
// SAFETY FALLBACK: until MAILERLITE_API_KEY is set, sign-ups keep going to
// Beehiiv exactly as before (BEEHIIV_API_KEY + BEEHIIV_PUB_ID). The 6 AM run
// deploys whatever is in this folder, so this file must work whichever order the
// code deploy and the Netlify env-var change happen in. Once MailerLite is
// confirmed working, the Beehiiv branch and its env vars can be deleted.

export const config = {
  path: '/api/subscribe',  // also reachable at /.netlify/functions/subscribe
};

const API = 'https://connect.mailerlite.com/api';

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

  // .trim(): a pasted token often carries a stray space/newline (2026-10-02: the
  // first Netlify value came back 401 Unauthenticated).
  const apiKey = (process.env.MAILERLITE_API_KEY || '').trim().replace(/^Bearer\s+/i, '');
  if (!apiKey) {
    if (process.env.BEEHIIV_API_KEY && process.env.BEEHIIV_PUB_ID) {
      return subscribeBeehiiv(email, req);
    }
    return json({ ok: false, error: 'server_misconfigured' }, 500);
  }
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type':  'application/json',
    'Accept':        'application/json',
  };

  // Which group? Explicit ID wins; otherwise look it up by name each call
  // (one cheap GET — sign-ups are rare, so no caching needed).
  let groupId = process.env.MAILERLITE_GROUP_ID || null;
  if (!groupId) {
    const name = (process.env.MAILERLITE_GROUP_NAME || 'Newsletter').toLowerCase();
    try {
      const g = await fetch(`${API}/groups?limit=100`, { headers });
      if (g.ok) {
        const gj = await g.json();
        const hit = (gj.data || []).find(x => (x.name || '').trim().toLowerCase() === name);
        if (hit) groupId = hit.id;
      }
    } catch { /* fall through: subscriber is still added, just without a group */ }
    if (!groupId) console.warn(`subscribe: group "${name}" not found — adding subscriber without a group`);
  }

  const payload = { email, status: 'active' };
  if (groupId) payload.groups = [String(groupId)];

  let upstream, text;
  try {
    upstream = await fetch(`${API}/subscribers`, {
      method: 'POST', headers, body: JSON.stringify(payload),
    });
    text = await upstream.text();
  } catch (e) {
    return json({ ok: false, error: 'upstream_unreachable' }, 502);
  }

  let data;
  try { data = JSON.parse(text); } catch { data = { _raw: text }; }

  // MailerLite upserts: 201 = new subscriber, 200 = already existed (updated).
  if (upstream.status === 201) {
    return json({ ok: true, provider_status: data?.data?.status || null });
  }
  if (upstream.status === 200) {
    return json({ ok: true, already_subscribed: true });
  }

  // Error code kept as 'beehiiv_error' on purpose: the front-end on every page
  // maps that value to "Our newsletter provider rejected that". Renaming it
  // would mean editing every page's inline script for no user-visible gain.
  console.error('subscribe: MailerLite rejected', upstream.status, text.slice(0, 300));
  return json(
    { ok: false, error: 'beehiiv_error', status: upstream.status },
    upstream.status >= 500 ? 502 : 400,
  );
};

// Previous behaviour, kept verbatim in spirit — used only while MAILERLITE_API_KEY
// is unset (see SAFETY FALLBACK above).
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
