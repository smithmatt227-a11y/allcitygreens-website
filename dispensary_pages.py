#!/usr/bin/env python3
"""
AC Greens — per-dispensary page builder.

Called from update_site.py's main() during the 6 AM run. Writes:
    Website/dispensaries/<slug>/index.html   one page per tracked store
    Website/dispensaries/index.html          the hub that links them all
and rewrites the homepage's .disp-card hrefs, because a page nothing links to is
a page nothing crawls.

Pages are built from the SITE'S OWN components (.section-header, .deal-card,
.cat-tabs, .faq-item, .trust-bar, .hero-stats) and link the real style.css, so
they inherit every future change to the site's design rather than drifting.

Prototyped 2026-09-12 as Archive/dispensary-preview/gen_dispensary_pages.py.
"""
import json, os, re, sys, html, datetime as dt, statistics as st
from collections import defaultdict

# ── Manual exclusions ────────────────────────────────────────────────────
# Empty as of 2026-09-12: The Garden Sycamore was excluded while Weedmaps served
# it Camp Washington's catalogue. Both stores now come from their own Dutchie
# menus (dutchie_scraper.py) and return genuinely different inventory, so the
# hardcoded exclusion is gone — replaced by the automatic check below, which
# catches this whole class of fault rather than one instance of it.
EXCLUDE = set()

# A page needs enough flower SKUs for the headline comparison to mean anything.
THIN_FLOWER_SKUS = 20
STALE_DAYS = 7          # matches deal_rules.py's stale-sale demotion

CAT_ICON = {
 "flower":'<path d="M12 22v-9"/><path d="M12 13C10 10 7 9 5 5c3 0 6 2 7 8z"/><path d="M12 13C14 10 17 9 19 5c-3 0-6 2-7 8z"/><path d="M12 13C9.5 10 8 7 4 7c0 3 3 5 8 6z"/><path d="M12 13C14.5 10 16 7 20 7c0 3-3 5-8 6z"/><line x1="12" y1="13" x2="12" y2="4"/>',
 "concentrates":'<path d="M12 2S6 8 6 13a6 6 0 0012 0c0-5-6-11-6-11z"/><path d="M12 12s-2 2-2 4a2 2 0 004 0c0-2-2-4-2-4z"/>',
 "edibles":'<path d="M12 3a4 4 0 00-4 4c0 1.3.5 2.4 1.4 3.2L8 20h8l-1.4-9.8A4 4 0 0016 7a4 4 0 00-4-4z"/><circle cx="10" cy="9" r=".5" fill="currentColor"/><circle cx="14" cy="9" r=".5" fill="currentColor"/>',
 "pre_rolls":'<path d="M4 20L20 4"/><path d="M4 20s0-3 2-4L18 4c1.5-1.5 3.5.5 2 2"/><path d="M16 3l3 3"/><path d="M2 22l2-2"/>',
 "vapes":'<rect x="9" y="3" width="6" height="13" rx="2"/><path d="M9 8h6"/><path d="M12 16v2"/><circle cx="12" cy="21" r="1"/><path d="M7 5c-1 1.2-1 3.8 0 5"/><path d="M17 5c1 1.2 1 3.8 0 5"/>',
 "topicals":'<path d="M9 3h6v3H9z"/><rect x="7" y="6" width="10" height="15" rx="2"/><path d="M10 11h4"/>',
 "tinctures":'<path d="M10 2h4v5l3 12a2 2 0 01-2 2H9a2 2 0 01-2-2l3-12z"/><path d="M10 7h4"/>',
}
ALL_ICON = '<path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>'
CAT_LABEL = {"flower":"Flower","concentrates":"Concentrates","edibles":"Edibles",
             "pre_rolls":"Pre-Rolls","vapes":"Vapes","topicals":"Topicals",
             "tinctures":"Tinctures","accessories":"Accessories","apparel":"Apparel",
             "wellness":"Wellness","gear":"Gear","infused pre-rolls":"Infused Pre-Rolls"}
TAB_ORDER = ["flower","vapes","edibles","concentrates","pre_rolls","topicals","tinctures"]
CAT_ALIAS = {"vape pens": "vapes", "vape": "vapes", "pre-rolls": "pre_rolls",
             "prerolls": "pre_rolls", "pre rolls": "pre_rolls", "edible": "edibles",
             "concentrate": "concentrates", "topical": "topicals"}
norm_cat = lambda c: CAT_ALIAS.get((c or "").strip().lower(), (c or "flower").strip().lower())

e = lambda s: html.escape(str(s), quote=True)
slugify = lambda s: re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


# Set by build_all() before each page is rendered — a store page sits two levels
# below Website/, the hub one. Cache-bust values are read off index.html so they
# never drift from whatever the site is currently serving.
CSS = "../../style.css"
LOGO = "../../logo.png"


def locality(store) -> str:
    """Matt's own location labelling where the name carries one, else the city
    from the address. Deliberately NOT a guessed neighbourhood."""
    if " - " in store["name"]:
        return store["name"].split(" - ", 1)[1].strip()
    parts = [p.strip() for p in (store.get("address") or "").split(",")]
    return parts[1] if len(parts) >= 2 else "Cincinnati"


# Deal links: Weedmaps-sourced deals carry no product_url — Matt's standing call is
# no Weedmaps links, so those cards point at the dispensary's own site. The map
# already exists in update_site.py; import it rather than keeping a second copy.
try:
    from update_site import DISPENSARY_URLS, FALLBACK_URL, trends_brand_key
except Exception:                                            # pragma: no cover
    DISPENSARY_URLS, FALLBACK_URL = {}, ""
    def trends_brand_key(name):
        s = (name or "").lower().strip().split(" - ")[0].strip()
        for suf in (" cincinnati", " forest park", " sycamore", " milford",
                    " mount orab", " harrison", " oxford", " goshen", " lebanon",
                    " monroe", " dayton", " camp washington", " superstore",
                    " seven mile", " 5 mile", " five mile", " west", " east",
                    " north", " south", " northern"):
            if s.endswith(suf):
                s = s[: -len(suf)].strip()
        return s

# ⚠️ brand_key MUST be update_site.trends_brand_key, NOT update_site.brand_key.
# The two disagree on purpose: brand_key() collapses every Shangri-La into one
# (right for deal dedupe); this one keeps "shangri-la" and "shangri-la monroe"
# apart — which is what /trends/ plots and what these pages rank against.
brand_key = trends_brand_key


def deal_link(deal, store):
    """Per-product link where the source gives one (Dutchie), else the store's own
    site (Weedmaps). Never a Weedmaps URL."""
    return (deal.get("product_url")
            or DISPENSARY_URLS.get(store["name"])
            or FALLBACK_URL
            or store.get("url", ""))


def smooth(series, day):
    """7-day trailing mean on a real calendar axis; needs >=3 scrapes in the
    window, so a genuine outage stays a hole instead of being drawn through."""
    w = [v for d, v in series.items() if 0 <= (day - dt.date.fromisoformat(d)).days < 7]
    return round(sum(w) / len(w), 2) if len(w) >= 3 else None


def city_median(day):
    """Median of each day's cross-dispensary median OF THE SMOOTHED values."""
    vals = [v for v in (smooth(s, day) for s in fresh.values()) if v is not None]
    return round(st.median(vals), 2) if vals else None


def _prepare(data, trends):
    """Compute everything the pages share, as module globals so build() and the
    fragment helpers below can stay exactly as prototyped."""
    global summary, live, stores, brand_members, raw, last, fresh
    global CAL, CITY, MED, MED30, RANK, PRETTY

    summary = data
    # ⚠️ 38 records / 14 live stores — a store that moved from Weedmaps to Dutchie
    # has BOTH a dead `inactive` record (0 products, empty price_index) and a live
    # one. Filtering on status is mandatory, or the dead record wins and the page
    # renders blank.
    live = [d for d in data["dispensaries"] if d.get("status") == "live"]
    stores = [d for d in live if d["name"] not in EXCLUDE]

    # ⚠️ Automatic duplicate guard. Two "stores" reporting the same product count
    # AND the same flower price_index are one menu counted twice — which is what
    # Weedmaps did to The Garden for months. Unchecked it would ship two identical
    # pages under different names, and duplicate content is precisely what sinks
    # the SEO these pages exist for. Drop the later one, loudly.
    seen, dupes = {}, []
    for d in list(stores):
        fp = (d.get("price_index") or {}).get("flower") or {}
        fingerprint = (d.get("product_count"), fp.get("avg"), fp.get("count"),
                       fp.get("min"), fp.get("max"))
        if fingerprint[0] and fingerprint in seen:
            dupes.append((d["name"], seen[fingerprint]))
            stores.remove(d)
        else:
            seen[fingerprint] = d["name"]
    if dupes:
        print("  !! DUPLICATE MENUS — identical figures to another store, SKIPPED.")
        print("  !! The site's dispensary/product counts double-count them too.")
        for dup, orig in dupes:
            print(f"  !!   {dup}  ==  {orig}")

    brand_members = defaultdict(list)
    for d in live:                                  # siblings counted from LIVE,
        brand_members[brand_key(d["name"])].append(d["name"])   # not the filtered set

    # ── shared metric definitions — must match /trends/ (STATUS §0w) ──────
    raw = {k: {p["date"]: p["avg"] for p in v if p.get("avg")}
           for k, v in trends["dispensaries"].items()}
    last = dt.date.fromisoformat(max(dd for srs in raw.values() for dd in srs))
    fresh = {k: srs for k, srs in raw.items()       # 30-day freshness gate
             if (last - dt.date.fromisoformat(max(srs))).days <= 30}

    CAL   = [last - dt.timedelta(days=90 - i) for i in range(91)]
    CITY  = [city_median(d) for d in CAL]
    MED   = CITY[-1]
    MED30 = CITY[-31]
    RANK  = sorted(((smooth(srs, last), k) for k, srs in fresh.items()
                    if smooth(srs, last)))

    # Display name per brand. Taking the first member's name breaks for brands whose
    # members carry the distinguishing word INSIDE the name rather than after a
    # " - " — the Monroe pair would head the hub as "Shangri-La Monroe Superstore".
    # The longest common prefix across a brand's members is the brand itself:
    # Superstore + West -> "Shangri-La Monroe"; "UpLift - Milford" + "- Mount Orab"
    # -> "UpLift" (and keeps the capital L that title-casing would destroy).
    PRETTY = {}
    for bk, members in brand_members.items():
        heads = [n.split(" - ")[0].strip() for n in members]
        pre = heads[0]
        for h in heads[1:]:
            while pre and not h.startswith(pre):
                pre = pre[:-1]
        pre = pre.strip(" -–·")
        PRETTY[bk] = pre if len(pre) >= 3 else heads[0]


# ─────────────────────────────────────────────────────────────────────────
# SHARED CHROME — the nav masthead and footer, copied from index.html so every
# generated page carries the same header and footer as the rest of the site.
# `prefix` is the relative path back to Website/ (".." from the hub, "../.." from
# a store page); site links stay absolute so they work from any depth.
# ─────────────────────────────────────────────────────────────────────────

SITE = "https://allcitygreens.com"


def chrome_nav(prefix, logo_v=""):
    logo = "%s/logo.png%s" % (prefix, logo_v)
    return (
        '  <header class="nav" id="nav">\n'
        '    <div class="nav-inner">\n'
        '      <div class="nav-masthead">\n'
        '        <a href="{site}/" class="nav-logo-center" aria-label="All City Greens home">\n'
        '          <img src="{logo}" alt="All City Greens badge logo" class="nav-logo-img-lg">\n'
        '          <span class="nav-logo-wordmark">All City Greens</span>\n'
        '        </a>\n'
        '      </div>\n'
        '      <nav class="nav-links" aria-label="Main navigation">\n'
        '        <a href="{site}/#deals">Deals</a>\n'
        '        <a href="{site}/brands/">Brands</a>\n'
        '        <a href="{site}/trends/">Trends</a>\n'
        '        <a href="/dispensaries/">Dispensaries</a>\n'
        '      </nav>\n'
        '      <button class="nav-theme-toggle" data-theme-toggle aria-label="Switch theme">\n'
        '        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>\n'
        '      </button>\n'
        '    </div>\n'
        '  </header>'
    ).format(site=SITE, logo=logo)


def chrome_footer(prefix, logo_v=""):
    logo = "%s/logo.png%s" % (prefix, logo_v)
    return (
        '  <footer class="footer footer-has-watermark">\n'
        '    <img src="{logo}" alt="" class="footer-watermark" aria-hidden="true">\n'
        '    <div class="container">\n'
        '      <div class="footer-inner">\n'
        '        <div class="footer-brand">\n'
        '          <a href="{site}/" class="nav-logo" aria-label="All City Greens home">\n'
        '            <img src="{logo}" alt="All City Greens badge logo" class="nav-logo-img">\n'
        '            <span class="nav-logo-text">All City Greens</span>\n'
        '          </a>\n'
        '          <p class="footer-tagline">Straightforward. Reliable. Free.</p>\n'
        '          <p class="footer-disclaimer">Prices shown may vary. Always verify in-store before purchase. All City Greens is an independent price tracking service and is not affiliated with any dispensary.</p>\n'
        '        </div>\n'
        '        <div class="footer-links">\n'
        '          <a href="https://newsletter.allcitygreens.com" target="_blank" rel="noopener">Newsletter archive</a>\n'
        '          <a href="/dispensaries/">Dispensaries</a>\n'
        '          <a href="{site}/about/">About</a>\n'
        '          <a href="{site}/privacy/">Privacy</a>\n'
        '          <a href="{site}/terms/">Terms</a>\n'
        '          <a href="{site}/faq/">FAQ</a>\n'
        '          <a href="mailto:hello@allcitygreens.com">Contact</a>\n'
        '        </div>\n'
        '      </div>\n'
        '      <div class="footer-bottom">\n'
        '        <p class="footer-disclaimer">Prices change frequently. Always verify with the dispensary before visiting. Must be 21+ with valid ID. Ohio recreational cannabis rules apply.</p>\n'
        '      </div>\n'
        '    </div>\n'
        '  </footer>'
    ).format(site=SITE, logo=logo)


HUB_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cincinnati Dispensary Prices — Every Store We Track | All City Greens</title>
  <meta name="description" content="Average flower price at every Cincinnati-area dispensary we track, updated every morning. Compare {n} dispensaries, then open any store for today's deals and 90 days of price history.">
  <link rel="canonical" href="https://allcitygreens.com/dispensaries/">
  <meta property="og:title" content="Cincinnati Dispensary Prices — Every Store We Track">
  <meta property="og:description" content="Compare average flower prices across every Cincinnati dispensary we track. Updated every morning.">
  <meta property="og:type" content="website">
  <meta property="og:image" content="https://allcitygreens.com/og-image.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700&amp;family=Inter:wght@400;500;600;700&amp;family=Oswald:wght@400;500&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css{css}">
  <link rel="icon" type="image/png" href="../logo.png{logo}">
  <style>{hub_css}  </style>
</head>
<body>
{nav}

  <main>
    <section class="section">
      <div class="container">
        <div class="section-header">
          <h1 class="section-title">Cincinnati dispensary prices</h1>
          <p class="section-sub">Average flower price at every dispensary we track, cheapest first. Open any store for today's deals, its full category pricing and 90 days of history. Last checked the morning of {date}.</p>
        </div>
        <div class="dp-hub">
{body}
        </div>
      </div>
    </section>
  </main>

{footer}
</body>
</html>"""


def chart_svg(series, label):
    L, R, T, B = 56, 828, 20, 250
    vals = [v for v in series + CITY if v is not None]
    lo, hi = min(vals), max(vals)
    pad = max(3.0, (hi - lo) * 0.12)
    YMIN, YMAX = lo - pad, hi + pad
    xp = lambda i: L + (R - L) * i / (len(CAL) - 1)
    yp = lambda v: B - (B - T) * (v - YMIN) / (YMAX - YMIN)

    def path(vs, close=False):
        pts = [(xp(i), yp(v)) for i, v in enumerate(vs) if v is not None]
        if not pts:
            return ""
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        return d + f" L {pts[-1][0]:.1f} {B} L {pts[0][0]:.1f} {B} Z" if close else d

    step  = max(1, round((YMAX - YMIN) / 5 / 5) * 5) or 5
    ticks = [t for t in range(int(YMIN // step * step), int(YMAX) + step, step) if YMIN < t < YMAX]
    grid = "".join(f'<line x1="{L}" y1="{yp(t):.1f}" x2="{R}" y2="{yp(t):.1f}" class="dp-grid"/>' for t in ticks)
    ylab = "".join(f'<text x="{L-10}" y="{yp(t)+4:.1f}" class="dp-ax dp-ax--y">${t}</text>' for t in ticks)
    xlab = "".join(f'<text x="{xp(i):.1f}" y="{B+24}" class="dp-ax dp-ax--x">{CAL[i].strftime("%b %-d")}</text>'
                   for i in (0, 22, 45, 68, 90))
    me_end, city_end = series[-1], CITY[-1]
    ends = ""
    if me_end is not None:
        ends += (f'<circle cx="{xp(90):.1f}" cy="{yp(me_end):.1f}" r="4.5" class="dp-dot dp-dot--me"/>'
                 f'<text x="{xp(90)+11:.1f}" y="{yp(me_end)+5:.1f}" class="dp-ax dp-ax--me">${me_end:.2f}</text>')
    ends += (f'<circle cx="{xp(90):.1f}" cy="{yp(city_end):.1f}" r="4" class="dp-dot dp-dot--city"/>'
             f'<text x="{xp(90)+11:.1f}" y="{yp(city_end)+5:.1f}" class="dp-ax dp-ax--city">${city_end:.2f}</text>')
    return f'''<svg viewBox="0 0 900 300" class="dp-chart" role="img"
  aria-label="Ninety days of average flower price. {e(label)} ends at ${me_end:.2f}; the citywide median ends at ${city_end:.2f}.">
  <defs><linearGradient id="dpf" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="var(--color-primary)" stop-opacity=".20"/>
    <stop offset="100%" stop-color="var(--color-primary)" stop-opacity="0"/></linearGradient></defs>
  {grid}
  <path d="{path(series, True)}" fill="url(#dpf)" stroke="none"/>
  <path d="{path(CITY)}" class="dp-line dp-line--city" fill="none"/>
  <path d="{path(series)}" class="dp-line dp-line--me" fill="none"/>
  {ends}{ylab}{xlab}
</svg>'''


TABLE_CSS = """
  .dp-table tbody th { font-family: var(--font-display); font-weight: 700;
    font-size: calc(var(--text-sm) + 1px); letter-spacing: -0.01em; }
  .dp-table .dp-strong { font-family: var(--font-display); font-weight: 700;
    font-size: calc(var(--text-sm) + 2px); color: var(--color-primary); }
  .dp-table td { font-family: var(--font-body); }
"""

SCRIPTS = """<script>
  /* Theme toggle — same behaviour as index.html. */
  (function(){
    var t=document.querySelector('[data-theme-toggle]'), r=document.documentElement;
    var d=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    r.setAttribute('data-theme',d);
    function u(){ if(!t)return;
      t.setAttribute('aria-label','Switch to '+(d==='dark'?'light':'dark')+' mode');
      t.innerHTML = d==='dark'
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'; }
    u(); t&&t.addEventListener('click',function(){d=d==='dark'?'light':'dark';r.setAttribute('data-theme',d);u();});
  })();

  /* Scroll reveal. REQUIRED, not decoration: style.css L1246 sets .deal-card to
     opacity:0 and only .acg-visible brings it back, so without this script every
     deal card renders invisible. Lifted from index.html. */
  (function(){
    var selector='.deal-card, a.deal-card-link';
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.querySelectorAll(selector).forEach(function(el){ el.classList.add('acg-visible'); });
      return;
    }
    var observer=new IntersectionObserver(function(entries){
      entries.filter(function(x){return x.isIntersecting;}).forEach(function(entry,i){
        var el=entry.target;
        setTimeout(function(){ el.classList.add('acg-visible'); }, i*60);
        observer.unobserve(el);
      });
    },{ threshold:0.08, rootMargin:'0px 0px -30px 0px' });
    document.querySelectorAll(selector).forEach(function(el){ observer.observe(el); });

    // Re-observe after a category switch. Filtering toggles display, and a card
    // never scrolled into view has never been revealed — without this it comes
    // back at opacity:0. Same hook index.html uses.
    document.querySelectorAll('.cat-tab').forEach(function(tab){
      tab.addEventListener('click', function(){
        setTimeout(function(){
          document.querySelectorAll(selector + ':not(.acg-visible)').forEach(function(el){
            observer.observe(el);
          });
        }, 50);
      });
    });
  })();

  /* Category filter — index.html's applyDeals() minus the dispensary select and
     the sort select. On a single-store page the dispensary filter is meaningless
     and the cards are already in the site's default order. */
  (function(){
    var catTabs=document.querySelectorAll('.cat-tab');
    var cards=Array.prototype.slice.call(document.querySelectorAll('.deal-card'));
    var empty=document.getElementById('deal-empty');
    var active='all';
    function apply(){
      var shown=0;
      cards.forEach(function(c){
        var ok=(active==='all'||c.dataset.cat===active);
        c.style.display=ok?'':'none'; if(ok) shown++;
      });
      if(empty) empty.style.display = shown ? 'none' : '';
    }
    catTabs.forEach(function(tab){
      tab.addEventListener('click', function(){
        catTabs.forEach(function(t){ t.classList.remove('active'); t.setAttribute('aria-selected','false'); });
        tab.classList.add('active'); tab.setAttribute('aria-selected','true');
        active=tab.dataset.cat; apply();
      });
    });
  })();
</script>"""


def build(store):
    name  = store["name"]
    slug  = slugify(name)
    bkey  = brand_key(name)
    sibs  = [n for n in brand_members[bkey] if n != name and n not in EXCLUDE]
    multi = len(sibs) > 0
    # What the brand-level series actually covers, said plainly.
    scope = (f"across {'both' if len(sibs)==1 else 'all'} "
             f"{len(sibs)+1} {PRETTY[bkey]} locations") if multi else ""

    # Deals for THIS store come from two places and must be merged:
    #   • deals_by_category — only the top 5 per category CITYWIDE, so most stores
    #     contribute nothing. Shangri-La Cincinnati looked rich only because it
    #     dominates those lists; six other stores came out with zero deals.
    #   • the store's own `highlights` — 5 per store, every store has them.
    # Dedupe on name+price, since a store's headline deal appears in both.
    deals, seen = [], set()
    for it in (summary["deals_by_category"].get(c, []) for c in summary["deals_by_category"]):
        for d in it:
            if d["dispensary"] != name:
                continue
            k = (d["name"], d["price"])
            if k in seen:
                continue
            seen.add(k)
            deals.append(dict(d, _cat=norm_cat(d.get("category"))))
    for d in (store.get("highlights") or []):
        k = (d["name"], d["price"])
        if k in seen:
            continue
        seen.add(k)
        deals.append(dict(d, _cat=norm_cat(d.get("category"))))
    deals.sort(key=lambda d: (-d.get("discount_pct", 0), d["price"]))

    # Not every highlight is a discount. Zen Leaf's five are all on_sale=False with
    # price == original_price — it simply had nothing on sale this morning. Calling
    # those "deals" would be a lie, so the section adapts: real discounts if there
    # are any, otherwise the same cards as plain menu picks with no strikethrough.
    sales = [d for d in deals if d.get("on_sale") and (d.get("discount_pct") or 0) > 0]
    picks = [d for d in deals if d not in sales]
    shown_deals = sales if sales else picks[:8]
    on_sale_mode = bool(sales)

    pi     = store.get("price_index") or {}
    flower = pi.get("flower") or {}
    thin   = (flower.get("count") or 0) < THIN_FLOWER_SKUS

    series = [smooth(fresh[bkey], d) for d in CAL] if bkey in fresh else [None]*91
    now    = series[-1]
    d30    = series[-31]
    rank_i = [k for _, k in RANK].index(bkey) + 1 if bkey in [k for _, k in RANK] else None
    delta  = ((now - MED) / MED * 100) if now else None
    band_word = ("well below" if delta <= -20 else "below" if delta <= -5 else
                 "level with" if abs(delta) < 5 else "above" if delta < 20 else
                 "well above") if delta is not None else ""

    # ── fragments ────────────────────────────────────────────────────────
    def icon(paths, w="1.8"):
        return (f'<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                f'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" '
                f'aria-hidden="true">{paths}</svg>')

    def cat_tabs():
        present = [c for c in TAB_ORDER if any(d["_cat"] == c for d in shown_deals)]
        present += [c for c in dict.fromkeys(d["_cat"] for d in shown_deals) if c not in present]
        all_label = "All Deals" if on_sale_mode else "Everything"
        out = [f'          <button class="cat-tab active" role="tab" aria-selected="true" '
               f'data-cat="all">{icon(ALL_ICON,"2")} {all_label}</button>']
        for c in present:
            out.append(f'          <button class="cat-tab" role="tab" aria-selected="false" '
                       f'data-cat="{e(c)}">{icon(CAT_ICON.get(c, CAT_ICON["flower"]))} '
                       f'{e(CAT_LABEL.get(c, c.replace("_"," ").title()))}</button>')
        return "\n".join(out)

    def deal_cards():
        out = []
        for d in shown_deals:
            sd = d.get("sale_days")
            bits = [e(d.get("brand") or ""), e(d.get("weight_label") or "")]
            if d.get("on_sale") and sd is not None:
                bits.append("New today" if sd <= 1 else f"on sale {sd} days")
            elif not d.get("on_sale"):
                bits.append("everyday price")
            meta = " · ".join(x for x in bits if x)
            if d.get("on_sale") and (d.get("discount_pct") or 0) > 0:
                prices = (f'<span class="deal-card-orig">${d["original_price"]:.2f}</span>'
                          f'<span class="deal-card-sale">${d["price"]:.2f}</span>'
                          f'<span class="deal-card-pct">-{d["discount_pct"]}%</span>')
            else:
                prices = f'<span class="deal-card-sale">${d["price"]:.2f}</span>'
            out.append(f'''          <a class="deal-card deal-card-link" data-cat="{e(d['_cat'])}" data-price="{d['price']:.2f}" data-pct="{d.get('discount_pct') or 0}" href="{e(deal_link(d, store))}" target="_blank" rel="noopener">
            <div class="deal-card-cat">{icon(CAT_ICON.get(d['_cat'], CAT_ICON['flower']))} {e(CAT_LABEL.get(d['_cat'], d['_cat'].replace("_"," ").title()))}</div>
            <div class="deal-card-name">{e(d['name'])}</div>
            <div class="deal-card-disp">{meta}</div>
            <div class="deal-card-prices">
              {prices}
            </div>
          </a>''')
        return "\n".join(out)

    def price_rows():
        order = ["flower","edibles","vapes","pre_rolls","concentrates","topicals","tinctures"]
        keys = [c for c in order if c in pi] + [c for c in pi if c not in order]
        return "\n          ".join(
            f'<tr><th scope="row">{e(CAT_LABEL.get(k, k.replace("_"," ").title()))}</th>'
            f'<td>{pi[k]["count"]}</td><td class="dp-strong">${pi[k]["avg"]:,.2f}</td>'
            f'<td>${pi[k]["min"]:,.2f}</td><td>${pi[k]["max"]:,.2f}</td></tr>' for k in keys)

    def rank_rows():
        out = []
        for i, (val, k) in enumerate(RANK, 1):
            me = k == bkey
            tr = '<tr class="dp-me">' if me else '<tr>'   # py3.9: no backslash in f-string exprs
            out.append(f'{tr}<td class="dp-rank">{i}</td>'
                       f'<th scope="row">{e(PRETTY.get(k, k.title()))}</th>'
                       f'<td class="dp-barcell"><span class="dp-bar" style="width:{max(2.0,(val-30)/(85-30)*100):.1f}%"></span></td>'
                       f'<td class="dp-strong">${val:,.2f}</td><td>{(val-MED)/MED*100:+.0f}%</td></tr>')
        return "\n          ".join(out)

    # ── generated prose, from the numbers only ───────────────────────────
    if now and d30:
        mv = now - d30
        move = (f"Over the last 30 days it has barely moved: <strong>{mv:+.2f}</strong>"
                if abs(mv) < 1 else
                f"Over the last 30 days it has {'fallen' if mv < 0 else 'risen'} "
                f"<strong>${abs(mv):.2f}</strong> ({mv/d30*100:+.1f}%)")
        readout = (f"{e(PRETTY[bkey])} averages <strong>${now:.2f}</strong> a flower item against a "
                   f"citywide median of <strong>${MED:.2f}</strong> — {band_word} the middle of the market. "
                   f"{move}. The citywide median over the same period went from ${MED30:.2f} to ${MED:.2f}.")
    else:
        readout = (f"Not enough scrape history yet to draw a reliable 90-day line for "
                   f"{e(PRETTY[bkey])}. The citywide median is <strong>${MED:.2f}</strong>.")

    # A store needs 3 daily scrapes before build_trends_data() will emit a series
    # for it, so a brand-new store has no rank, no headline figures and no chart.
    # Say that plainly rather than showing a citywide ranking it is absent from.
    new_store_note = ("" if rank_i else
                      f" {e(PRETTY[bkey])} joined recently and needs a few days of "
                      f"daily readings before it can be ranked here.")

    headline = (f"cheapest flower of the {len(RANK)} dispensaries we track" if rank_i == 1 else
                f"#{rank_i} of {len(RANK)} on flower price" if rank_i else
                "tracked daily")

    faq = []
    if rank_i == 1:
        faq.append((f"Is {name} the cheapest dispensary in Cincinnati?",
            f"On flower, yes — of the {len(RANK)} dispensaries we track daily it has the lowest "
            f"average menu price, ${now:.2f} an item against a ${MED:.2f} citywide median."))
    elif rank_i:
        faq.append((f"How does {name} compare on price?",
            f"It ranks #{rank_i} of the {len(RANK)} dispensaries we track, averaging ${now:.2f} a flower "
            f"item against a ${MED:.2f} citywide median — {band_word} the middle of the market."))
    if multi:
        faq.append(("Do these prices cover every location?",
            f"The deals, the menu count and the category table on this page are {name} only. The "
            f"90-day chart and the ranking are measured {scope}, the same way the /trends/ page "
            f"does it — prices between them differ by only a dollar or two."))
    if thin:
        faq.append(("Why are there so few flower prices here?",
            f"{name} listed only {flower.get('count', 0)} flower SKUs on its public menu this "
            f"morning, out of {store['product_count']} items overall. We report what the menu "
            f"shows, so its flower average is based on a small sample — read it as indicative."))
    faq.append(("How often do you check the prices?",
        f"Every morning. We read the store's own public menu around 6 AM and record every "
        f"in-stock item — {store['product_count']} of them today."))
    faq.append((f"Do you get paid by {PRETTY[bkey]}?",
        "No. All City Greens takes no money from any dispensary and sells no placement. "
        "We read public menus and report what they say."))

    LD = json.dumps({"@context":"https://schema.org","@type":"Store","name":name,
      "address":{"@type":"PostalAddress","streetAddress":(store.get("address") or "").split(",")[0],
                 "addressLocality":locality(store),"addressRegion":"OH","addressCountry":"US"},
      "url":store.get("url",""),
      "makesOffer":[{"@type":"Offer","name":d["name"],"price":f'{d["price"]:.2f}',
                     "priceCurrency":"USD","availability":"https://schema.org/InStock",
                     "priceValidUntil":(last+dt.timedelta(days=1)).isoformat()} for d in deals[:6]]})
    FAQ_LD = json.dumps({"@context":"https://schema.org","@type":"FAQPage",
      "mainEntity":[{"@type":"Question","name":q,
                     "acceptedAnswer":{"@type":"Answer","text":a}} for q, a in faq]})

    NAV = chrome_nav("../..", LOGO.split("logo.png")[-1])
    FOOTER = chrome_footer("../..", LOGO.split("logo.png")[-1])

    stat_price = (f'''          <div class="stat">
            <span class="stat-num">${now:.2f}</span>
            <span class="stat-label">average flower, per item{f" &mdash; {scope}" if multi else ""}</span>
          </div>
          <div class="stat-divider" aria-hidden="true"></div>''' if now else "")
    stat_rank = (f'''          <div class="stat">
            <span class="stat-num">#{rank_i} of {len(RANK)}</span>
            <span class="stat-label">cheapest flower in the city</span>
          </div>
          <div class="stat-divider" aria-hidden="true"></div>''' if rank_i else "")
    stat_delta = (f'''          <div class="stat">
            <span class="stat-num">{delta:+.1f}%</span>
            <span class="stat-label">{band_word} the ${MED:.2f} city median</span>
          </div>''' if delta is not None else "")

    if on_sale_mode:
        deals_head, deals_lede = "On sale today", (
            f'{len(shown_deals)} discounted item{"s" if len(shown_deals)!=1 else ""}. '
            "We show how long each sale has been running &mdash; a discount that has sat "
            "on the menu for two weeks is shelf pricing, not an event.")
    else:
        deals_head, deals_lede = "Today's picks from the menu", (
            f"Nothing on {e(name)}'s menu was discounted when we read it this morning. "
            "These are everyday prices; the full category breakdown is below.")

    deals_section = f'''    <section class="section section-alt" id="deals" aria-labelledby="deals-heading">
      <div class="container">
        <div class="section-header">
          <h2 id="deals-heading" class="section-title">{deals_head}</h2>
          <p class="section-sub dp-lede">{deals_lede}</p>
        </div>
        <div class="cat-tabs" role="tablist" aria-label="Filter by category">
{cat_tabs()}
        </div>
        <div class="deal-cards">
{deal_cards()}
          <div id="deal-empty" class="deal-empty" style="display:none">Nothing in that category today.</div>
        </div>
      </div>
    </section>''' if shown_deals else ""

    chart_section = f'''    <section class="section" aria-labelledby="trend-heading">
      <div class="container">
        <div class="section-header">
          <h2 id="trend-heading" class="section-title">Ninety days of flower prices</h2>
          <p class="section-sub dp-lede">Both lines are 7-day trailing averages on a real calendar axis, so a gap in the data stays a gap.{f" This series is measured {scope}, the same way the Trends page does it." if multi else ""}</p>
        </div>
        <p class="dp-legend"><span><span class="dp-key"></span>{e(PRETTY[bkey])}</span><span><span class="dp-key dp-key--city"></span>Citywide median</span></p>
        <div class="dp-chartwrap">{chart_svg(series, PRETTY[bkey])}</div>
        <p class="dp-readout">{readout}</p>
      </div>
    </section>''' if now else ""

    faq_items = "\n".join(
        f'''          <div class="faq-item">
            <dt class="faq-q">{e(q)}</dt>
            <dd class="faq-a">{e(a)}</dd>
          </div>''' for q, a in faq)

    page = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(name)} Deals &amp; Prices Today — All City Greens</title>
  <meta name="description" content="{e(name)} prices checked every morning. {f'Average flower ${now:.2f} an item, {abs(delta):.0f}% {band_word} the Cincinnati median. ' if now else ''}Today's deals, full category pricing and 90 days of price history.">
  <link rel="canonical" href="https://allcitygreens.com/dispensaries/{slug}/">
  <meta property="og:title" content="{e(name)} Deals &amp; Prices Today">
  <meta property="og:description" content="{f'Average flower ${now:.2f} an item — {abs(delta):.0f}% {band_word} the Cincinnati median. ' if now else ''}Checked every morning.">
  <meta property="og:type" content="website">
  <meta property="og:image" content="https://allcitygreens.com/og-image.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700&amp;family=Inter:wght@400;500;600;700&amp;family=Oswald:wght@400;500&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{CSS}">
  <link rel="icon" type="image/png" href="{LOGO}">
  <style>
  /* NEW classes only — everything else on this page is an existing site
     component. These blocks are what would move into style.css. */
  .dp-lede {{ max-width:60ch; margin-inline:auto; }}
  .dp-hero {{ padding-block: var(--space-10) !important; }}
  .dp-hero .section-header {{ margin-bottom: var(--space-6); }}
  .dp-hero .hero-stats {{ justify-content:center; align-items:flex-start;
    gap:var(--space-8); flex-wrap:wrap; padding-top:0; }}
  .dp-hero .stat {{ align-items:center; text-align:center; gap:var(--space-2); }}
  .dp-hero .stat-label {{ max-width:20ch; }}

  .dp-chartwrap {{ border:1px solid var(--color-border); border-radius:var(--radius-xl);
    background:var(--color-surface-2); padding:var(--space-5) var(--space-4) var(--space-3);
    overflow-x:auto; }}
  .dp-chart {{ display:block; width:100%; min-width:520px; height:auto; }}
  .dp-grid {{ stroke:var(--color-divider); stroke-width:1; }}
  .dp-line {{ stroke-linejoin:round; stroke-linecap:round; }}
  .dp-line--me {{ stroke:var(--color-primary); stroke-width:2.6; }}
  .dp-line--city {{ stroke:var(--color-text-muted); stroke-width:1.6; stroke-dasharray:5 4; opacity:.7; }}
  .dp-dot--me {{ fill:var(--color-primary); }}
  .dp-dot--city {{ fill:var(--color-text-muted); }}
  .dp-ax {{ font-family:var(--font-body); font-size:12px; fill:var(--color-text-muted); }}
  .dp-ax--y {{ text-anchor:end; }}
  .dp-ax--x {{ text-anchor:middle; }}
  .dp-ax--me {{ fill:var(--color-primary); font-weight:700; }}
  .dp-legend {{ display:flex; gap:var(--space-5); justify-content:center; flex-wrap:wrap;
    margin-bottom:var(--space-4); font-size:var(--text-xs); color:var(--color-text-muted); }}
  .dp-key {{ display:inline-block; width:20px; border-top:3px solid var(--color-primary);
    margin-right:6px; vertical-align:middle; }}
  .dp-key--city {{ border-top:2px dashed var(--color-text-muted); }}
  .dp-readout {{ max-width:66ch; margin:var(--space-5) auto 0; text-align:center;
    font-size:var(--text-sm); color:var(--color-text-muted); }}
  .dp-readout strong {{ color:var(--color-text); }}

  .dp-tablewrap {{ border:1px solid var(--color-border); border-radius:var(--radius-xl);
    background:var(--color-surface-2); overflow-x:auto; }}
  .dp-table {{ width:100%; border-collapse:collapse; font-size:var(--text-sm); min-width:520px; }}
  .dp-table th, .dp-table td {{ padding:var(--space-3) var(--space-4);
    border-bottom:1px solid var(--color-divider); text-align:right;
    font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .dp-table thead th {{ font-size:var(--text-xs); font-weight:700; text-transform:uppercase;
    letter-spacing:.08em; color:var(--color-text-muted); background:var(--color-surface-offset); }}
  .dp-table th:first-child, .dp-table thead th:first-child {{ text-align:left; }}
  .dp-table tbody th {{ text-align:left; color:var(--color-text); }}
  .dp-table tbody tr:last-child th, .dp-table tbody tr:last-child td {{ border-bottom:none; }}
  .dp-rank {{ text-align:right; color:var(--color-text-faint); width:3rem; }}
  .dp-barcell {{ width:40%; }}
  .dp-bar {{ display:block; height:8px; border-radius:2px;
    background:var(--color-text-faint); opacity:.55; }}
  .dp-me th, .dp-me td {{ background:color-mix(in srgb, var(--color-primary) 12%, transparent); }}
  .dp-me th {{ color:var(--color-primary) !important; }}
  .dp-me .dp-bar {{ background:var(--color-primary); opacity:1; }}
  @media (max-width:640px) {{ .dp-barcell {{ display:none; }} }}
  /* table typography — see TABLE_CSS */{TABLE_CSS}
  </style>
</head>
<body>
{NAV}

  <main>
    <section class="section dp-hero">
      <div class="container">
        <div class="section-header">
          <h1 class="section-title">{e(name)}</h1>
          <p class="section-sub dp-lede">{e(locality(store))} &middot; {store['product_count']} items on the menu, priced against the {len(RANK)} dispensaries we track across the city. Last checked the morning of {last.strftime('%B %-d, %Y')}.</p>
        </div>

        <div class="hero-stats">
{stat_price}
{stat_rank}
{stat_delta}
        </div>
      </div>
    </section>

    <section class="trust-bar" aria-label="About this dispensary">
      <div class="container">
        <ul class="trust-list" role="list">
          <li class="trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M21 10c0 7-9 12-9 12s-9-5-9-12a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>{e(store.get('address',''))}</li>
          <li class="trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Menu read daily, around 6&nbsp;AM</li>
          <li class="trust-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>Independent &mdash; we take no money from dispensaries</li>
        </ul>
      </div>
    </section>

{deals_section}

{chart_section}

    <section class="section section-alt" aria-labelledby="prices-heading">
      <div class="container">
        <div class="section-header">
          <h2 id="prices-heading" class="section-title">What everything costs here</h2>
          <p class="section-sub dp-lede">Every category on the menu this morning &mdash; all {store['product_count']} items, not just the discounted ones.</p>
        </div>
        <div class="dp-tablewrap">
          <table class="dp-table">
            <thead><tr><th scope="col">Category</th><th scope="col">Items</th><th scope="col">Average</th><th scope="col">Lowest</th><th scope="col">Highest</th></tr></thead>
            <tbody>
          {price_rows()}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section" aria-labelledby="rank-heading">
      <div class="container">
        <div class="section-header">
          <h2 id="rank-heading" class="section-title">How it compares across the city</h2>
          <p class="section-sub dp-lede">Average flower price per item at every dispensary we track, cheapest first, as of this morning. Sister locations are combined into one figure per dispensary, the same way the Trends page does it.{new_store_note}</p>
        </div>
        <div class="dp-tablewrap">
          <table class="dp-table">
            <thead><tr><th scope="col">#</th><th scope="col">Dispensary</th><th scope="col"></th><th scope="col">Avg flower</th><th scope="col">vs median</th></tr></thead>
            <tbody>
          {rank_rows()}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section section-alt section-faq" aria-labelledby="faq-heading">
      <div class="container container-narrow">
        <div class="section-header">
          <h2 id="faq-heading" class="section-title">Questions people ask</h2>
        </div>
        <dl class="faq-list">
{faq_items}
        </dl>
      </div>
    </section>

    <section class="section section-cta" id="subscribe">
      <div class="container cta-inner">
        <h2 class="cta-heading">Get the Cincinnati deals every morning</h2>
        <p class="cta-sub">One short email, every day, with the best prices across every dispensary we track. Free, no ads, unsubscribe whenever.</p>
        <form class="cta-form form-row" onsubmit="return false;">
          <input type="email" id="dp-email" name="email" class="form-input form-input-lg" placeholder="your@email.com" aria-label="Email address" required autocomplete="email">
          <button type="submit" class="btn btn-primary btn-lg">Subscribe free</button>
        </form>
        <p class="form-note">Free forever. No spam. Unsubscribe anytime.</p>
      </div>
    </section>
  </main>

{FOOTER}

{SCRIPTS}
<script type="application/ld+json">{LD}</script>
<script type="application/ld+json">{FAQ_LD}</script>
</body>
</html>'''
    return slug, page, dict(name=name, slug=slug, brand=bkey, multi=multi, thin=thin,
                            on_sale_mode=on_sale_mode,
                            deals=len(deals), items=store["product_count"],
                            flower_n=flower.get("count", 0), now=now, rank=rank_i,
                            delta=round(delta, 1) if delta is not None else None)


# ─────────────────────────────────────────────────────────────────────────
# HUB PAGE + HOMEPAGE WIRING
# ─────────────────────────────────────────────────────────────────────────

_BRANDS = {}          # brand key -> [page meta], set by build_all


def _cache_bust(website_dir):
    """Read the ?v= values off index.html so these pages never serve a different
    generation of style.css / logo.png than the rest of the site."""
    try:
        idx = open(os.path.join(website_dir, "index.html")).read()
    except OSError:
        return "", ""
    css = re.search(r"style\.css\?v=(\d+)", idx)
    logo = re.search(r"logo\.png\?v=(\d+)", idx)
    return (("?v=" + css.group(1)) if css else "",
            ("?v=" + logo.group(1)) if logo else "")


def _hub_row(bkey, members):
    members = sorted(members, key=lambda m: m["name"])
    first = members[0]
    locs = "\n".join(
        '            <li><a href="{slug}/">{loc}</a>'
        '<span class="dp-hub-meta">{items} items{sale}</span></li>'.format(
            slug=m["slug"], loc=e(m["locality"]), items=m["items"],
            sale=(" &middot; " + str(m["deals"]) + " on sale") if m["on_sale_mode"] else "")
        for m in members)
    if first["now"]:
        figs = ('<span class="dp-hub-price">${now:.2f}</span>'
                '<span class="dp-hub-vs">{delta:+.0f}% vs median</span>').format(
                    now=first["now"], delta=first["delta"])
    else:
        figs = '<span class="dp-hub-vs">no price history yet</span>'
    return (
        '        <div class="dp-hub-row" id="{anchor}">\n'
        '          <div class="dp-hub-brand">\n'
        '            <h2>{brand}</h2>\n'
        '            <p class="dp-hub-rankline">#{rank} of {total} on flower price</p>\n'
        '          </div>\n'
        '          <div class="dp-hub-figs">{figs}</div>\n'
        '          <ul class="dp-hub-locs">\n{locs}\n          </ul>\n'
        '        </div>'
    ).format(anchor=slugify(PRETTY.get(bkey, bkey)), brand=e(PRETTY.get(bkey, bkey.title())),
             rank=first["rank"] or "—", total=len(RANK), figs=figs, locs=locs)


HUB_CSS = """
  .dp-hub { display:flex; flex-direction:column; border-top:1px solid var(--color-border); }
  .dp-hub-row { display:grid; grid-template-columns:minmax(0,1.1fr) auto minmax(0,1.2fr);
    gap:var(--space-6); align-items:center; padding:var(--space-5) 0;
    border-bottom:1px solid var(--color-divider); scroll-margin-top:90px; }
  .dp-hub-brand h2 { font-family:var(--font-display); font-size:var(--text-lg);
    font-weight:700; margin:0; letter-spacing:-0.01em; }
  .dp-hub-rankline { margin:4px 0 0; font-size:var(--text-xs); color:var(--color-text-muted); }
  .dp-hub-figs { text-align:right; white-space:nowrap; }
  .dp-hub-price { display:block; font-family:var(--font-display); font-weight:700;
    font-size:var(--text-lg); color:var(--color-primary); font-variant-numeric:tabular-nums; }
  .dp-hub-vs { display:block; font-size:var(--text-xs); color:var(--color-text-muted); }
  .dp-hub-locs { list-style:none; margin:0; padding:0; display:flex;
    flex-direction:column; gap:7px; }
  .dp-hub-locs a { font-weight:600; text-decoration:none;
    border-bottom:1px solid var(--color-divider); }
  .dp-hub-locs a:hover { border-bottom-color:var(--color-primary); }
  .dp-hub-meta { font-size:var(--text-xs); color:var(--color-text-faint); margin-left:8px; }
  @media (max-width:720px) {
    .dp-hub-row { grid-template-columns:1fr; gap:var(--space-3); }
    .dp-hub-figs { text-align:left; }
  }
"""


def build_hub(rows, website_dir):
    """dispensaries/index.html — the crawlable index every store page hangs off.
    Grouped by brand so a multi-location chain reads as one entry with its
    locations beneath, matching how the homepage grid already talks about them."""
    by_brand = defaultdict(list)
    for m in rows:
        by_brand[m["brand"]].append(m)
    order = sorted(by_brand.items(),
                   key=lambda kv: min((x["now"] or 999) for x in kv[1]))
    body = "\n".join(_hub_row(k, v) for k, v in order)
    css_v, logo_v = _cache_bust(website_dir)

    hub = HUB_TEMPLATE.format(
        n=len(RANK), css=css_v, logo=logo_v, hub_css=HUB_CSS,
        nav=chrome_nav(".." , logo_v), footer=chrome_footer("..", logo_v),
        date=last.strftime("%B %-d, %Y"), body=body)
    out = os.path.join(website_dir, "dispensaries")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w").write(hub)


def link_homepage_cards(website_dir):
    """Point each homepage .disp-card at its store page, or at the hub anchor for
    a multi-location brand. Runs every morning and is idempotent, so the links
    cannot drift as stores come and go. Cards for dispensaries with no page (the
    paused ones) keep their outbound link to the dispensary's own site."""
    path = os.path.join(website_dir, "index.html")
    try:
        idx = open(path).read()
    except OSError:
        return 0, 0

    stats = {"linked": 0, "left": 0}

    def resolve(card_name):
        """Homepage cards use SHORT display names ("The Garden", "Garden Club")
        that do not equal the scraper's brand key ("the garden dispensary"). Try
        an exact brand match first, then a unique prefix match; anything ambiguous
        is left alone rather than guessed at."""
        key = brand_key(card_name)
        if key in _BRANDS:
            return _BRANDS[key]
        hits = [v for k, v in _BRANDS.items() if k.startswith(key + " ") or k == key]
        return hits[0] if len(hits) == 1 else None

    def repl(m):
        head, rest, inner = m.group(1), m.group(3), m.group(4)
        name = re.search(r'disp-name">([^<]*)', inner)
        if not name:
            stats["left"] += 1
            return m.group(0)
        members = resolve(name.group(1).strip())
        if not members:
            stats["left"] += 1          # paused / untracked — leave it pointing out
            return m.group(0)
        # A card whose disp-loc lists several locations (". . . · . . ." or "A & B")
        # covers more stores than one page — and for Shangri-La it even spans two
        # brand keys — so send those to the hub, where every location is listed.
        loc = re.search(r'disp-loc">([^<]*)', inner)
        spans_many = bool(loc and re.search(r"&middot;|·|&amp;| & ", loc.group(1)))
        if len(members) == 1 and not spans_many:
            target = "/dispensaries/" + members[0]["slug"] + "/"
        else:
            target = "/dispensaries/"
        rest = re.sub(r'\s*target="_blank"|\s*rel="noopener"', "", rest)
        stats["linked"] += 1
        return '<a class="disp-card%s" href="%s"%s>%s</a>' % (head, target, rest, inner)

    new = re.sub(r'<a class="disp-card([^"]*)" href="([^"]+)"([^>]*)>(.*?)</a>',
                 repl, idx, flags=re.S)
    if new != idx:
        open(path, "w").write(new)
    return stats["linked"], stats["left"]


def build_sitemap(rows, website_dir):
    """Regenerate sitemap.xml every morning.

    The hand-written one had gone stale: lastmod frozen at 2026-05-28, /about/,
    /privacy/ and /terms/ missing entirely, and of course none of the dispensary
    pages. Generating it means it can't drift again.

    lastmod is honest per page rather than "today" for everything — Google uses it
    to schedule crawls, and a site that claims its terms page changed this morning
    teaches it to ignore the field. Data-driven pages get the scrape date; static
    pages get their file's own mtime.
    """
    site = "https://allcitygreens.com"
    scrape_date = last.isoformat()

    def mtime(rel):
        try:
            ts = os.path.getmtime(os.path.join(website_dir, rel))
            return dt.date.fromtimestamp(ts).isoformat()
        except OSError:
            return None

    entries = [
        ("/", scrape_date, "daily", "1.0"),
        ("/dispensaries/", scrape_date, "daily", "0.9"),
    ]
    for m in sorted(rows, key=lambda r: r["slug"]):
        entries.append(("/dispensaries/%s/" % m["slug"], scrape_date, "daily", "0.8"))

    # Static pages: include them only if they actually exist, and date them by
    # their own file rather than by the scrape.
    for path, freq, pri in (("brands", "daily", "0.8"), ("trends", "daily", "0.7"),
                            ("faq", "monthly", "0.5"), ("about", "monthly", "0.5"),
                            ("privacy", "yearly", "0.3"), ("terms", "yearly", "0.3")):
        rel = os.path.join(path, "index.html")
        md = mtime(rel)
        if md:
            entries.append(("/%s/" % path, md, freq, pri))

    body = "\n".join(
        "  <url>\n"
        "    <loc>%s%s</loc>\n"
        "    <lastmod>%s</lastmod>\n"
        "    <changefreq>%s</changefreq>\n"
        "    <priority>%s</priority>\n"
        "  </url>" % (site, loc, md, freq, pri)
        for loc, md, freq, pri in entries)

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<!-- Generated by Website/dispensary_pages.py on every run. Do not hand-edit. -->\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + body + "\n</urlset>\n")
    open(os.path.join(website_dir, "sitemap.xml"), "w").write(xml)
    return len(entries)


def build_all(data, trends, website_dir):
    """Entry point, called from update_site.main(). Returns the metadata rows."""
    global CSS, LOGO, _BRANDS
    _prepare(data, trends)
    css_v, logo_v = _cache_bust(website_dir)
    out_root = os.path.join(website_dir, "dispensaries")
    os.makedirs(out_root, exist_ok=True)

    CSS, LOGO = "../../style.css" + css_v, "../../logo.png" + logo_v
    rows = []
    for store in stores:
        slug, page, meta = build(store)
        d = os.path.join(out_root, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(page)
        meta["locality"] = locality(store)
        rows.append(meta)

    _BRANDS = defaultdict(list)
    for m in rows:
        _BRANDS[m["brand"]].append(m)

    build_hub(rows, website_dir)
    n_urls = build_sitemap(rows, website_dir)
    linked, left = link_homepage_cards(website_dir)
    print("✅  %d dispensary pages + hub written to dispensaries/" % len(rows))
    print("    homepage cards: %d linked to a page, %d left pointing outward" % (linked, left))
    print("    sitemap.xml regenerated (%d urls)" % n_urls)
    return rows


if __name__ == "__main__":
    import glob
    here = os.path.dirname(os.path.abspath(__file__))
    newest = sorted(glob.glob(os.path.join(here, "..", "Price Scraper", "Data", "summary_*.json")))[-1]
    print("Loading %s …" % os.path.basename(newest))
    rows = build_all(json.load(open(newest)),
                     json.load(open(os.path.join(here, "trends-data.json"))), here)
    print()
    print("%-38s %5s %6s %7s %5s %7s  flags" % ("slug", "deals", "items", "avg", "rank", "vs med"))
    for m in rows:
        flags = " ".join(f for f, on in (("MULTI-LOC", m["multi"]), ("THIN-FLOWER", m["thin"])) if on)
        print("%-38s %5d %6d %7s %5s %7s  %s" % (
            m["slug"], m["deals"], m["items"],
            ("$" + str(m["now"])) if m["now"] else "—",
            m["rank"] or "—",
            (str(m["delta"]) + "%") if m["delta"] is not None else "—", flags))
