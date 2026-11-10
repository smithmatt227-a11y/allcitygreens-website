#!/usr/bin/env python3
"""
update_site.py — AC Greens website auto-updater
Reads the latest scraper JSON and injects fresh deal cards into index.html.

Designed for the Perplexity-built design (single deal-cards grid + cat-tab JS filtering).

Usage:
  cd ~/Desktop/AC\ Greens/Website && python3 update_site.py

After running, commit and push:
  git add -A && git commit -m "data: refresh $(date +%Y-%m-%d)" && git push
"""

import json
import re
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
INDEX_HTML = SCRIPT_DIR / "index.html"
DATA_DIR   = SCRIPT_DIR.parent / "Price Scraper" / "Data"

# Max deal cards to inject into the deals grid
CARDS_TOTAL = 20

SUBSCRIBE_URL = "https://allcitygreens.beehiiv.com/subscribe"

# Map every scraper dispensary name → direct website URL
DISPENSARY_URLS = {
    "Therapy Cannabis - Cincinnati":           "https://www.therapycannabis.com/dispensaries/cincinnati/",
    "Story Cincinnati":                        "https://storycannabis.com",
    "Story Forest Park":                       "https://storycannabis.com",
    "Zen Leaf - Cincinnati":                   "https://zenleafdispensaries.com/locations/cincinnati/",
    "Shangri-La Cincinnati":                   "https://shangriladispensaries.com",
    "Shangri-La Monroe West":                  "https://shangriladispensaries.com",
    "Shangri-La Monroe Superstore":            "https://shangriladispensaries.com",
    # 2026-09-07: thegardendispo.com/menu/ started returning 404 (site moved to
    # per-store paths). Verified live: both /stores/... URLs return the real menu.
    "The Garden Dispensary - Camp Washington": "https://thegardendispo.com/stores/camp-washington-cincinnati",
    "The Garden Dispensary - Sycamore":        "https://thegardendispo.com/stores/sycamore-township-cincinnati",
    "Garden Club Dispensary":                  "https://gardenclubdispensaries.com",
    # 2026-09-12: Saphyre/Zips Central Parkway. LeafBridge products carry their own
    # product_url, so this is only the fallback for anything that doesn't.
    "Zips - Central Parkway":                  "https://saphyredispensary.com/shop/cincinnati-central-parkway/non-medical/",
    "Trulieve - Cincinnati":                   "https://www.trulieve.com",
    "The Landing - Cincinnati":                "https://www.thelandingdispensaries.com",
    "The Landing - Monroe":                    "https://www.thelandingdispensaries.com",
    "Nectar - Cincinnati":                     "https://nectarohio.com",
    "Nectar - 5 Mile":                         "https://nectarohio.com",
    "Nectar - Harrison":                       "https://nectarohio.com",
    "Sunnyside - Cincinnati":                  "https://www.sunnyside.shop",
    # 2026-09-07: verilife.com/oh/* now 302s to verilifeoh.com (Ohio split to its
    # own domain), landing on a generic homepage. Verified live: this is the store page.
    "Verilife - Cincinnati":                   "https://verilifeoh.com/locations/cincinnati",
    "Beyond Hello - Cincinnati":               "https://beyond-hello.com",
    "Beyond Hello - Northern Cincinnati":      "https://beyond-hello.com",
    "Beyond Hello - Oxford":                   "https://beyond-hello.com",
    "AYR Wellness - Goshen":                   "https://ayrdispensaries.com",
    "Queen City Cannabis - Harrison":          "https://queenccanna.com",
    "Queen City Cannabis - Norwood":           "https://queenccanna.com/norwood/",
    "Queen City Cannabis - Suspension Bridge": "https://queenccanna.com/harrison-suspension-bridge/",
    "Ethos Dispensary - Lebanon":              "https://ethoscannabis.com",
    "UpLift - Milford":                        "https://www.upliftohio.com/milford/",
    "UpLift - Mount Orab":                     "https://www.upliftohio.com",
    # 2026-09-07: columbia.care/locations/ohio returned 404. Ohio lives on the
    # oh.columbia.care subdomain now; verified live.
    "Columbia Care - Monroe":                  "https://www.oh.columbia.care/stores/ohio/monroe",
    "Bloom - Seven Mile":                      "https://bloommarijuana.com",
    "Green Releaf - Dayton":                   "https://greenreleafdispensary.com",
    "Locals Cannabis":                         "https://localscannabis.com/stores/locals-dispensary-cincinnati",
    "Locals Cannabis - Cincinnati":            "https://localscannabis.com/stores/locals-dispensary-cincinnati",
}

FALLBACK_URL = "https://allcitygreens.com"

# Category SVG icons (from Perplexity design)
CAT_ICONS = {
    "flower": '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22v-9"/><path d="M12 13C10 10 7 9 5 5c3 0 6 2 7 8z"/><path d="M12 13C14 10 17 9 19 5c-3 0-6 2-7 8z"/><path d="M12 13C9.5 10 8 7 4 7c0 3 3 5 8 6z"/><path d="M12 13C14.5 10 16 7 20 7c0 3-3 5-8 6z"/><line x1="12" y1="13" x2="12" y2="4"/></svg>',
    "vapes": '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="13" rx="2"/><path d="M9 8h6"/><path d="M12 16v2"/><circle cx="12" cy="21" r="1"/><path d="M7 5c-1 1.2-1 3.8 0 5"/><path d="M17 5c1 1.2 1 3.8 0 5"/></svg>',
    "edibles": '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a4 4 0 00-4 4c0 1.3.5 2.4 1.4 3.2L8 20h8l-1.4-9.8A4 4 0 0016 7a4 4 0 00-4-4z"/><circle cx="10" cy="9" r=".5" fill="currentColor"/><circle cx="14" cy="9" r=".5" fill="currentColor"/><circle cx="12" cy="12" r=".5" fill="currentColor"/></svg>',
    "concentrates": '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2S6 8 6 13a6 6 0 0012 0c0-5-6-11-6-11z"/><path d="M12 12s-2 2-2 4a2 2 0 004 0c0-2-2-4-2-4z"/></svg>',
    "pre_rolls": '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20L20 4"/><path d="M4 20s0-3 2-4L18 4c1.5-1.5 3.5.5 2 2"/><path d="M16 3l3 3"/><path d="M2 22l2-2"/></svg>',
}
DEFAULT_ICON = '<svg class="cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>'

CAT_DISPLAY = {
    "flower": "Flower", "concentrates": "Concentrates",
    "edibles": "Edibles", "pre_rolls": "Pre-Rolls", "vapes": "Vapes",
}

# Set in main() from the scrape's generated_at — e.g. "7:06 AM". Surfaced as a
# trust line on every deal card ("✓ Verified 7:06 AM today").
VERIFIED_TIME = ""


def format_verified_time(data: dict) -> str:
    """Return a friendly Eastern-time label like '7:06 AM' from the scrape's
    generated_at timestamp. Empty string if unavailable."""
    from datetime import datetime, timedelta, timezone
    ts = data.get("generated_at") or ""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is not None:
            # 2026-11-09: was a fixed UTC-4, which reads an hour late from
            # November to March (6:13 AM EST showed as 7:13 AM). Use the real
            # zone; fall back to the old fixed offset only if zoneinfo is missing.
            try:
                from zoneinfo import ZoneInfo
                dt = dt.astimezone(ZoneInfo("America/New_York"))
            except Exception:
                dt = dt.astimezone(timezone(timedelta(hours=-4)))
        return dt.strftime("%-I:%M %p")
    except Exception:
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def find_latest_json() -> Path:
    files = sorted(DATA_DIR.glob("summary_*.json"))
    if not files:
        sys.exit(f"ERROR: no summary_*.json found in {DATA_DIR}")
    return files[-1]


def parse_weight_grams(weight_label: str):
    """Convert a weight_label string to grams, or None."""
    if not weight_label:
        return None
    w = weight_label.strip().lower()
    m = re.match(r'^([\d.]+)\s*g$', w)
    if m:
        return float(m.group(1))
    m = re.match(r'^(\d+)/(\d+)\s*oz$', w)
    if m:
        return (int(m.group(1)) / int(m.group(2))) * 28.3495
    m = re.match(r'^(\d+)\s*oz$', w)
    if m:
        return int(m.group(1)) * 28.3495
    return None


def calc_ppg(deal: dict):
    grams = parse_weight_grams(deal.get("weight_label", ""))
    if grams and grams > 0:
        return deal["price"] / grams
    return None


def fmt_thc(deal: dict) -> str:
    thc = deal.get("thc_pct", 0) or 0
    if thc <= 0:
        return ""
    if deal.get("category") == "edibles" and thc > 100:
        return ""
    return f"{thc:.1f}% THC"


def display_disp_name(scraper_name: str) -> str:
    replacements = {
        "The Garden Dispensary": "The Garden",
        "Ethos Dispensary":      "Ethos",
        # "Queen City Cannabis" no longer shortened (2026-11-06): the cards, store
        # pages and hub all use the full name, so the deal lines now match.
    }
    name = scraper_name
    for long, short in replacements.items():
        if name.startswith(long):
            name = short + name[len(long):]
            break
    if " - " in name:
        parts = name.split(" - ", 1)
        return f"{parts[0].strip()} - {parts[1].strip()}"
    return name


_WEIGHT_OR_DOSE = re.compile(
    r'^\s*(?:'
    r'[\d.]+\s*(?:g|oz|mg/ea|mg/each)|'   # 1g, 0.5oz, 10mg/ea — drop, useless on its own
    r'\.\d+\s*g|'                          # .84g
    r'\d+/\d+\s*(?:g|oz)'                  # 7/10 g, 1/8 oz
    r')\s*$',
    re.IGNORECASE,
)

# Known brand prefixes — first pipe-segment is the brand, drop it
_BRAND_PREFIXES = {
    "redbud roots", "riviera creek", "certified cultivators", "klutch", "josh d",
    "kynd", "the essence", "(the) essence", "g", "g:", "k.i.n.d.",
}


# 2026-11-06: menus also separate name parts with " - " ("Josh D - Flower -
# MotorBreath (I)", "Modern Flower- Apples & Bananas"). A segment that is only a
# category word repeats the category label shown right above the name, so it goes.
_CATEGORY_SEGMENTS = {
    "flower", "flowers", "concentrate", "concentrates", "vape", "vapes",
    "edible", "edibles", "pre-roll", "pre-rolls", "preroll", "prerolls",
    "pre roll", "pre rolls",
}
# " - ", " – ", " — " anywhere, or "word- " (missing space before the dash).
# A hyphen inside a word ("Pre-Roll", "Live-Resin") is never split.
_DASH_SEP = re.compile(r"\s+[-\u2013\u2014]\s+|(?<=[A-Za-z0-9)\]])[-\u2013\u2014]\s+")


def clean_product_name(raw_name: str) -> str:
    """
    Make a scraper product name display-worthy.
    Strategy:
      1. Pipe-separated names: trim trailing per-unit weight/dose tokens (1g,
         10mg/ea, .84g…; pack counts like 10pk are kept), drop a leading
         recognized brand prefix, drop a segment already contained in an
         earlier one.
      2. Split on dash separators too, and drop segments that are only a
         category word ("Flower", "Concentrate").
      3. Join what's left with single spaces (2026-11-06: was " — ", which
         made names read like "Grow Ohio — Blueberry Vintage — Indica").
    Always returns a usable product identity — never just '10mg/ea' or '60pk'.
    """
    if not raw_name:
        return ""
    s = raw_name.strip()
    parts = [s]
    if "|" in s:
        parts = [p.strip() for p in s.split("|") if p.strip()]
        if len(parts) > 1:
            # 1a. Trim trailing weight-only tokens
            while len(parts) > 1 and _WEIGHT_OR_DOSE.match(parts[-1]):
                parts.pop()
            # 1b. Drop leading brand if recognized
            if len(parts) > 1 and parts[0].lower().strip().rstrip(":") in _BRAND_PREFIXES:
                parts = parts[1:]
            # 1c. Drop a segment already contained in an earlier one (fixes
            #    "Peach + CBC Gummies | Gummies | 28pk" -> "... Gummies Gummies 28pk")
            kept = []
            for part in parts:
                if part.lower() in " — ".join(kept).lower():
                    continue
                kept.append(part)
            parts = kept or parts
    # 2. Dash separators, then category-only segments
    segs = [x.strip() for part in parts for x in _DASH_SEP.split(part) if x.strip()]
    kept = [x for x in segs if x.lower() not in _CATEGORY_SEGMENTS] or segs
    out = re.sub(r"\s{2,}", " ", " ".join(kept)).strip()
    return out or s


def deduplicate(deals: list) -> list:
    """Remove rec+medical duplicates. Key = (name, dispensary). Prefer recreational."""
    seen = {}
    for deal in deals:
        key = (deal["name"].lower(), deal["dispensary"].lower())
        if key not in seen or deal.get("license_type") == "recreational":
            seen[key] = deal
    return list(seen.values())


def brand_key(disp_name: str) -> str:
    """
    Normalize a dispensary name to its brand root so sister locations
    collapse into one. (Formerly mirrored Newsletter/newsletter.py, retired
    2026-09-12 to Archive/mailchimp-era-2026-09-12/ — this is now the only copy.)
    e.g. 'The Garden Dispensary - Sycamore' -> 'the garden dispensary'
         'UpLift - Mount Orab'              -> 'uplift'
    """
    name = disp_name.lower().strip()
    name = name.split(" - ")[0].strip()
    suffixes = (" cincinnati", " forest park", " monroe", " sycamore",
                " harrison", " oxford", " goshen", " milford", " lebanon",
                " mount orab", " five mile", " 5 mile", " northern",
                " camp washington", " seven mile", " dayton", " superstore",
                " west", " east", " north", " south")
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                changed = True
                break
    return name


def dedupe_sister_locations(deals: list) -> list:
    """
    Collapse same-product duplicates across sister dispensary locations.
    Keep the first occurrence (best one — caller is expected to have sorted).
    Key = (full product name lowercased, brand root).
    Two different products at the same brand stay. Same product at two
    sister locations collapses to one.
    """
    seen: set = set()
    result: list = []
    for d in deals:
        key = (d.get("name", "").strip().lower(), brand_key(d.get("dispensary", "")))
        if key in seen or not key[0]:
            continue
        seen.add(key)
        result.append(d)
    return result


def one_per_dispensary(deals: list) -> list:
    """Keep only the best deal per dispensary (first occurrence after dedup+sort)."""
    seen_disps = set()
    result = []
    for deal in deals:
        d = deal["dispensary"].lower()
        if d not in seen_disps:
            seen_disps.add(d)
            result.append(deal)
    return result


def best_highlight_per_dispensary(dispensaries: list, category: str = None) -> list:
    """
    Pull the single best product from each dispensary's highlights list.
    Prefer on_sale items; fall back to lowest price_per_gram.
    """
    results = []
    for disp in dispensaries:
        highlights = disp.get("highlights") or []
        if category:
            highlights = [h for h in highlights if h.get("category") == category]
        if not highlights:
            continue
        on_sale = [h for h in highlights if h.get("on_sale")]
        candidates = on_sale if on_sale else highlights
        with_ppg = [(calc_ppg(h) or 9999, h) for h in candidates]
        with_ppg.sort(key=lambda x: x[0])
        results.append(with_ppg[0][1])

    def sort_key(deal):
        return (0 if deal.get("on_sale") else 1, calc_ppg(deal) or 9999)
    results.sort(key=sort_key)
    return results


def disp_url(scraper_name: str) -> str:
    return DISPENSARY_URLS.get(scraper_name, FALLBACK_URL)


def _meaningful_weight(deal: dict) -> bool:
    grams = parse_weight_grams(deal.get("weight_label", ""))
    return grams is not None and grams >= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# HTML GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def badge_pct_text(pct) -> str:
    """
    Displayed discount badge, capped at "50%+" (credibility rule, 2026-06-12).
    Dispensaries' own marketing advertises at most ~20-50% off (verified on
    UpLift / Shangri-La / Zen Leaf sites), so deeper computed strike-through
    discounts (real, but clearance math) display as "50%+" and let the actual
    prices do the selling. Sorting still uses the true % via data-pct.
    """
    try:
        pct = int(pct or 0)
    except (TypeError, ValueError):
        return ""
    if pct <= 0:
        return ""
    return "50%+" if pct > 50 else f"{pct}%"


def deal_card_html(deal: dict) -> str:
    """Generate a deal card in the Perplexity design format with data-cat for JS filtering."""
    url       = deal.get("product_url") or disp_url(deal["dispensary"])
    raw_cat   = deal.get("category", "")
    cat_label = CAT_DISPLAY.get(raw_cat, raw_cat.replace("_", " ").title())
    icon      = CAT_ICONS.get(raw_cat, DEFAULT_ICON)
    on_sale   = deal.get("on_sale", False)
    discount  = deal.get("discount_pct", 0)

    name         = clean_product_name(deal["name"])
    disp_display = display_disp_name(deal["dispensary"])
    thc_str      = fmt_thc(deal)
    disp_detail  = disp_display + (f" · {thc_str}" if thc_str else "")

    price = deal["price"]
    orig  = deal.get("original_price", price)
    ppg   = calc_ppg(deal)

    save_html = ""
    if on_sale and orig and orig > price:
        badge = badge_pct_text(discount)
        pct_text = f"-{badge}" if badge else "Top deal"
        prices_html = (
            f'<span class="deal-card-orig">${orig:.2f}</span>'
            f'<span class="deal-card-sale">${price:.2f}</span>'
            f'<span class="deal-card-pct">{pct_text}</span>'
        )
        save_html = f'<span class="deal-card-save">Save {fmt_money(orig - price)}</span>'
    else:
        prices_html = f'<span class="deal-card-sale">${price:.2f}</span>'

    # 2026-11-09 refresh: the card now carries what the hero card and the store
    # pages already showed — price per gram, dollars saved, how long the sale has
    # run. THC moved down here with $/g so the store line stays one short line.
    age_html = ""
    age = sale_age_text(deal)
    if age:
        fresh_cls = " deal-card-age--new" if (deal.get("sale_days") or 99) <= 2 else ""
        age_html = f'<span class="deal-card-age{fresh_cls}">{age}</span>'
    facts = " · ".join(x for x in [(f"${ppg:.2f}/g" if ppg and raw_cat == "flower" and _meaningful_weight(deal) else ""),
                                   ("" if raw_cat == "edibles" else thc_str)] if x)
    meta_html = ""
    if facts or save_html:
        facts_html = f'<span>{facts}</span>' if facts else ''
        meta_html = (f'            <div class="deal-card-meta">{facts_html}'
                     f'{save_html}</div>\n')

    return (
        f'          <a class="deal-card deal-card-link" data-cat="{raw_cat}"'
        f' data-disp="{disp_display}" data-price="{price:.2f}"'
        f' data-pct="{discount or 0}"'
        f' href="{url}" target="_blank" rel="noopener">\n'
        f'            <div class="deal-card-top"><div class="deal-card-cat">{icon} {cat_label}</div>{age_html}</div>\n'
        f'            <div class="deal-card-name">{name}</div>\n'
        f'            <div class="deal-card-disp">{disp_display}</div>\n'
        f'            <div class="deal-card-prices">\n'
        f'              {prices_html}\n'
        f'            </div>\n'
        f'{meta_html}'
        f'          </a>'
    )


def fmt_money(v) -> str:
    """$41 for whole dollars, $12.80 otherwise."""
    v = float(v or 0)
    return f"${v:.0f}" if abs(v - round(v)) < 0.005 else f"${v:.2f}"


def sale_age_text(deal: dict) -> str:
    """'New today' / 'On sale 4 days' from the scraper's sale_days (deal_rules.py).
    Empty when the item is not on sale or the scraper recorded no streak."""
    if not deal.get("on_sale"):
        return ""
    sd = deal.get("sale_days")
    if sd is None:
        return ""
    try:
        sd = int(sd)
    except (TypeError, ValueError):
        return ""
    return "New today" if sd <= 1 else f"On sale {sd} days"


# ─────────────────────────────────────────────────────────────────────────────
# 2026-11-09 HOMEPAGE REFRESH — hero "best deal" card, lowest-shelf-price
# section, price board, pulse strip. Mockups: the "AC Greens — Site & Newsletter
# Refresh" design canvas (STATUS.md §0zt).
# ─────────────────────────────────────────────────────────────────────────────

HERO_CATS = [("flower", "Flower"), ("vapes", "Vapes"), ("edibles", "Edibles"),
             ("concentrates", "Concentrates"), ("pre_rolls", "Pre-Rolls")]


def _hero_pick(dispensaries: list, cat: str):
    """Best on-sale highlight in a category for the hero card.
    Flower: lowest price per gram (what the old top-3 card led with).
    Everything else: biggest discount, then lowest price.
    No stale-sale filter, same as the card this replaced."""
    aliases = {cat} | ({"vape pens"} if cat == "vapes" else set())
    pool = []
    for disp in dispensaries:
        for h in (disp.get("highlights") or []):
            if h.get("category") in aliases and h.get("on_sale") \
                    and (h.get("original_price") or 0) > (h.get("price") or 0) > 0:
                h = dict(h)
                h.setdefault("dispensary", disp.get("name", ""))
                pool.append(h)
    if not pool:
        return None
    if cat == "flower":
        with_ppg = [h for h in pool if calc_ppg(h) and _meaningful_weight(h)]
        if with_ppg:
            return min(with_ppg, key=lambda h: (calc_ppg(h), h["price"]))
    return min(pool, key=lambda h: (-(h.get("discount_pct") or 0), h["price"]))


def hero_best_html(dispensaries: list, pretty_date: str = "", disp_count: int = 0,
                   top_deals: list = None) -> str:
    """Hero card: one best deal per category behind a row of tabs. The first
    category with a deal is shown; the rest are revealed by the tab script in
    index.html (and stay hidden, harmlessly, if that script never runs)."""
    # The scraper's top_deals list is already ordered by deal_rules.py (3-day
    # headline cooldown, 7+ day sales demoted). Use its first deal per category
    # so the hero never leads with a weeks-old markdown while a fresh one exists;
    # fall back to the highlights when a category is not in that list.
    ruled = {}
    for d in (top_deals or []):
        c = "vapes" if d.get("category") == "vape pens" else d.get("category")
        if c not in ruled and d.get("on_sale") and (d.get("original_price") or 0) > (d.get("price") or 0) > 0:
            ruled[c] = d
    picks = [(key, label, ruled.get(key) or _hero_pick(dispensaries, key)) for key, label in HERO_CATS]
    picks = [(k, l, d) for k, l, d in picks if d]
    updated = f'Updated {pretty_date}' if pretty_date else 'Updated today'
    if not picks:
        return (
            f'            <div class="mockup-header">\n'
            f'              <div class="mockup-title">Best deal today</div>\n'
            f'              <div class="mockup-rule"></div>\n'
            f'              <div class="mockup-updated">{updated}</div>\n'
            f'            </div>\n'
            f'            <div class="mockup-cta"><a href="#deals">See all of today\'s deals &rarr;</a></div>'
        )
    tabs, panels = [], []
    for i, (key, label, d) in enumerate(picks):
        on = (i == 0)
        tabs.append(
            f'              <button type="button" class="hero-tab{" active" if on else ""}"'
            f' data-hero-cat="{key}" aria-pressed="{"true" if on else "false"}">{label}</button>')
        url   = d.get("product_url") or disp_url(d["dispensary"])
        price, orig = d["price"], d.get("original_price", d["price"])
        ppg   = calc_ppg(d)
        thc   = fmt_thc(d)
        chips = [f"Save {fmt_money(orig - price)}"]
        if key == "flower" and ppg and _meaningful_weight(d):
            chips.append(f"${ppg:.2f} per gram")
        elif thc and key != "edibles":
            chips.append(thc)
        age = sale_age_text(d)
        if age:
            chips.append(age)
        chip_html = "".join(f'<span class="hero-best-chip">{c}</span>' for c in chips)
        panels.append(
            f'              <a class="hero-best"{"" if on else " hidden"} data-hero-cat="{key}"'
            f' href="{url}" target="_blank" rel="noopener">\n'
            f'                <div class="hero-best-top"><span class="deal-type">{label}</span>'
            f'<span class="hero-best-store">{display_disp_name(d["dispensary"])}</span></div>\n'
            f'                <div class="hero-best-name">{clean_product_name(d["name"])}</div>\n'
            f'                <div class="hero-best-prices"><span class="hero-best-now">{fmt_money(price)}</span>'
            f'<span class="deal-original">${orig:.2f}</span>'
            f'<span class="deal-chip">&minus;{badge_pct_text(d.get("discount_pct"))}</span></div>\n'
            f'                <div class="hero-best-chips">{chip_html}</div>\n'
            f'              </a>')
    return (
        f'            <div class="mockup-header">\n'
        f'              <div class="mockup-title">Best deal today</div>\n'
        f'              <div class="mockup-rule"></div>\n'
        f'              <div class="mockup-updated">{updated}</div>\n'
        f'            </div>\n'
        f'            <div class="hero-tabs" role="group" aria-label="Best deal by category">\n'
        + "\n".join(tabs) + '\n'
        f'            </div>\n'
        f'            <div class="hero-best-wrap">\n'
        + "\n".join(panels) + '\n'
        f'            </div>\n'
        f'            <div class="mockup-footer">✓ Prices verified this morning · {disp_count} stores checked</div>\n'
        f'            <div class="mockup-cta"><a href="#deals">See all of today\'s deals &rarr;</a></div>'
    )


def _esc(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def lowest_html(report_date: str) -> str:
    """'Lowest shelf price today' — cheapest in-stock item per standard size,
    sale or no sale. Empty string when the catalogue is missing or not today's
    (the section then keeps a plain fallback line rather than stale prices)."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR.parent))
        import lowest_prices
        result = lowest_prices.build_today(report_date)
    except Exception as exc:
        print(f"  ⚠️  lowest prices skipped: {type(exc).__name__}: {exc}")
        return ""
    if not result:
        print("  ⚠️  lowest prices skipped: no catalogue for today")
        return ""
    rows = []
    for r in result["rows"]:
        url   = r["url"] or disp_url(r["store"])
        store = display_disp_name(r["store"])
        if r["tied"]:
            heads = []
            for n in [r["store"]] + r["tied"]:
                h = display_disp_name(n).split(" - ")[0]
                if h not in heads:
                    heads.append(h)
            if len(heads) > 1:
                store = " / ".join(heads) + " (tied)"
            if len({brand_key(n) for n in [r["store"]] + r["tied"]}) == 1:
                store = display_disp_name(r["store"]) + f' +{len(r["tied"])} sister store' + ("s" if len(r["tied"]) > 1 else "")
        nxt = ""
        if r.get("next_price"):
            nxt = (f'<span class="low-next">Next: {_esc(display_disp_name(r["next_store"]).split(" - ")[0])}'
                   f' ${r["next_price"]:.2f}</span>')
        rows.append(
            f'          <a class="low-row" href="{_esc(url)}" target="_blank" rel="noopener">\n'
            f'            <span class="low-size">{_esc(r["label"])}</span>\n'
            f'            <span class="low-what"><span class="low-store">{_esc(store)}</span>'
            f'<span class="low-name">{_esc(clean_product_name(r["name"]))}</span></span>\n'
            f'            <span class="low-price"><span class="low-now">${r["price"]:.2f}</span>{nxt}</span>\n'
            f'          </a>')
    lead = ""
    if result["wins"]:
        # count ties as wins for the summary line, so "lowest in N of M" is fair
        tally = {}
        for r in result["rows"]:
            for s in [r["store"]] + r["tied"]:
                tally[s] = tally.get(s, 0) + 1
        top_store, top_n = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_n >= 2:
            lead = (f'          <p class="low-lead"><strong>{_esc(display_disp_name(top_store).split(" - ")[0])}</strong> has the lowest'
                    f' price in {top_n} of the {result["sizes"]} sizes we compare today.</p>\n')
    print(f"  lowest prices: {result['sizes']} sizes")
    return lead + '          <div class="low-list">\n' + "\n".join(rows) + '\n          </div>'


def board_and_pulse(html: str, data: dict, brand_count: int, dispensary_count: int,
                    total_products: int, pretty_date: str) -> str:
    """Second pass over index.html, run AFTER dispensary_pages.build_all() so the
    board uses the exact ranking the store pages and /trends/ use (7-day average
    flower price, 30-day freshness gate, city median)."""
    import datetime as _dt
    import dispensary_pages as dp
    rank = list(getattr(dp, "RANK", []) or [])
    if not rank:
        raise RuntimeError("dispensary_pages.RANK is empty")
    med  = dp.MED
    last = dp.last
    top  = max(v for v, _ in rank)
    scale = top * 1.06
    brands = getattr(dp, "_BRANDS", {}) or {}
    rows = []
    for i, (avg, bk) in enumerate(rank, 1):
        name = dp.PRETTY.get(bk) or bk.title()
        members = brands.get(bk) or []
        if len(members) == 1:
            href = "/dispensaries/" + members[0]["slug"] + "/"
        elif members:
            href = "/dispensaries/#" + dp.slugify(name)
        else:
            href = "/dispensaries/"
        series = dp.fresh.get(bk, {})
        vals = [dp.smooth(series, last - _dt.timedelta(days=29 - k)) for k in range(30)]
        pts = [(k, v) for k, v in enumerate(vals) if v is not None]
        spark = ""
        if len(pts) >= 7:
            lo, hi = min(v for _, v in pts), max(v for _, v in pts)
            span = max(hi - lo, 6.0)
            mid = (hi + lo) / 2
            coords = " ".join(f"{2 + k * (88 / 29):.1f},{14 - ((v - mid) / span) * 20:.1f}" for k, v in pts)
            spark = (f'<svg class="board-spark" viewBox="0 0 92 28" role="img"'
                     f' aria-label="Last 30 days"><polyline points="{coords}"/></svg>')
        else:
            spark = '<span class="board-spark" aria-hidden="true"></span>'
        below = " board-row--low" if (med and avg <= med) else ""
        rows.append(
            f'          <a class="board-row{below}" href="{href}">\n'
            f'            <span class="board-rank">{i}</span>\n'
            f'            <span class="board-name">{_esc(name)}</span>\n'
            f'            <span class="board-bar"><span class="board-fill" style="width:{avg / scale * 100:.1f}%"></span>'
            + (f'<span class="board-med" style="left:{med / scale * 100:.1f}%"></span>' if med else "")
            + f'</span>\n'
            f'            {spark}\n'
            f'            <span class="board-price">${avg:.2f}</span>\n'
            f'          </a>')
    foot = (f'          <p class="board-foot"><span class="board-key"></span>Orange mark = city median'
            + (f', ${med:.2f}' if med else '') + '. Average price per flower item, 7-day average.</p>')
    html = replace_between_markers(html, "board", "\n".join(rows) + "\n" + foot)

    cheapest_avg, cheapest_bk = rank[0]
    cheapest = dp.PRETTY.get(cheapest_bk) or cheapest_bk.title()
    when = pretty_date.rsplit(",", 1)[0] if pretty_date else "today"
    if VERIFIED_TIME:
        when += f", {VERIFIED_TIME}"
    bits = [f'            <span class="pulse-live"><span class="pulse-dot" aria-hidden="true"></span>Checked this morning · {when}</span>']
    if med:
        bits.append(f'            <span>City median flower <strong>${med:.2f}</strong></span>')
    bits.append(f'            <span>Cheapest flower <strong>{_esc(cheapest)} · ${cheapest_avg:.2f}</strong></span>')
    if brand_count:
        bits.append(f'            <span><strong>{brand_count}</strong> brands on sale</span>')
    bits.append(f'            <span><strong>{dispensary_count}</strong> stores · <strong>{total_products:,}</strong> products</span>')
    return replace_between_markers(html, "pulse", "\n".join(bits))


def mockup_row(deal: dict, rank: int = 0) -> str:
    """Generate a single ranked row in the hero 'Today's Best Deals' card."""
    name    = clean_product_name(deal["name"])
    url     = deal.get("product_url") or disp_url(deal["dispensary"])
    disp    = display_disp_name(deal["dispensary"])
    price   = deal["price"]
    orig    = deal.get("original_price", price)
    on_sale = deal.get("on_sale", False)
    ppg     = calc_ppg(deal)
    cat     = CAT_DISPLAY.get(deal.get("category", ""), "Product")

    ppg_str = f' · ${ppg:.2f}/g' if ppg else ''

    if on_sale and orig and orig > price:
        pct  = round((orig - price) / orig * 100)
        save = orig - price
        save_str = f'${save:.0f}' if abs(save - round(save)) < 0.005 else f'${save:.2f}'
        price_html = (
            f'<span class="deal-original">${orig:.2f}</span> '
            f'<span class="deal-now">${price:.2f}</span> '
            f'<span class="deal-chip">&minus;{badge_pct_text(pct)}</span> '
            f'<span class="deal-save">Save {save_str}</span>'
        )
    else:
        price_html = f'<span class="deal-now">${price:.2f}</span>'

    lead = ' mockup-deal--lead' if rank == 1 else ''
    return (
        f'              <a class="mockup-deal mockup-deal-link{lead}" href="{url}" target="_blank" rel="noopener">\n'
        f'                <div class="mockup-rank">{rank}</div>\n'
        f'                <div class="mockup-deal-body">\n'
        f'                  <div class="deal-type">{cat}</div>\n'
        f'                  <div class="deal-name">{name}</div>\n'
        f'                  <div class="deal-disp">{disp}{ppg_str}</div>\n'
        f'                  <div class="deal-price">{price_html}</div>\n'
        f'                </div>\n'
        f'              </a>'
    )


def mockup_html(dispensaries: list, best_value: list, pretty_date: str = "",
                disp_count: int = None) -> str:
    """
    Generate the hero 'Today's Best Deals' card (header + ranked rows + CTA):
      - Header: title + orange rule + dynamic "Updated <date>" stamp.
      - Up to 3 ON-SALE items, ranked #1–#3, deduped by product name so the
        same product doesn't appear twice when sister dispensaries run the
        same sale (e.g. Garden Camp Washington + Garden Sycamore).
      - Best Value Eighths section: removed per design refresh.
    """
    # TODAY'S BEST DEALS — on-sale items, one per dispensary, sister-collapsed
    sale_deals = best_highlight_per_dispensary(dispensaries)
    sale_only  = [d for d in sale_deals if d.get("on_sale")]
    candidates = one_per_dispensary(sale_only) or one_per_dispensary(sale_deals)
    featured   = dedupe_sister_locations(candidates)[:3]

    deals_rows = "\n".join(mockup_row(d, i + 1) for i, d in enumerate(featured))
    if disp_count is None:
        disp_count = len([d for d in dispensaries if d.get("highlights")])
    updated    = f'Updated {pretty_date}' if pretty_date else 'Updated today'

    # best_value retained as a function argument for backwards compat with the
    # caller, but no Best Value Eighths section is rendered any more.
    _ = best_value

    return (
        f'            <div class="mockup-header">\n'
        f'              <div class="mockup-title">Today\'s Best Deals</div>\n'
        f'              <div class="mockup-rule"></div>\n'
        f'              <div class="mockup-updated">{updated}</div>\n'
        f'            </div>\n'
        f'            <div class="mockup-section">\n'
        f'{deals_rows}\n'
        f'            </div>\n'
        f'            <div class="mockup-footer">✓ Prices verified this morning · {disp_count} stores checked</div>\n'
        f'            <div class="mockup-cta"><a href="#deals">See all of today\'s deals &rarr;</a></div>'
    )


def stats_html(dispensary_count: int, total_products: int) -> str:
    prod_k = total_products // 100 * 100
    return (
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{dispensary_count}</span>\n'
        f'              <span class="stat-label">stores tracked</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{prod_k:,}+</span>\n'
        f'              <span class="stat-label">products monitored daily</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">One</span>\n'
        f'              <span class="stat-label">email every morning</span>\n'
        f'            </div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# TRENDS DATA — builds /trends-data.json from all historical scrapes
# ─────────────────────────────────────────────────────────────────────────────

def trends_brand_key(name: str) -> str:
    """Brand root for the /trends/ series, the ranking and the per-dispensary pages.

    ⚠️ DELIBERATELY NOT the same as brand_key() above, and the two must not be
    merged. brand_key() loops until no suffix matches, so "Shangri-La Monroe West"
    collapses all the way to "shangri-la" — right for deal dedupe, where every
    Shangri-La should count once. This one strips each suffix at most once, so
    "Shangri-La Monroe West" stops at "shangri-la monroe" and the Cincinnati store
    stays a separate series from the Monroe pair — which is what /trends/ plots and
    what the dispensary pages rank against. Changing this changes the chart.
    """
    s = (name or "").lower().strip().split(" - ")[0].strip()
    for suf in (" cincinnati", " forest park", " sycamore", " milford", " mount orab",
                " harrison", " oxford", " goshen", " lebanon", " monroe", " dayton",
                " camp washington", " superstore", " seven mile", " 5 mile",
                " five mile", " west", " east", " north", " south", " northern"):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s


def build_trends_data() -> dict:
    """
    Walk every summary_*.json in Price Scraper/Data, extract per-dispensary
    flower price_index, collapse sister locations, and return a JSON-ready
    time-series payload that the /trends/ page renders with Chart.js.
    """
    from collections import defaultdict
    from datetime import datetime

    files = sorted(DATA_DIR.glob("summary_*.json"))
    series = defaultdict(list)
    dates_set = set()

    for f in files:
        date_str = f.stem.replace("summary_", "")
        dates_set.add(date_str)
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        by_brand = defaultdict(lambda: {"sum": 0.0, "weight": 0, "min": float("inf")})
        for d in data.get("dispensaries", []):
            bk = trends_brand_key(d.get("name", ""))
            pi = (d.get("price_index") or {}).get("flower") or {}
            n = pi.get("count") or 0
            avg = pi.get("avg")
            mn = pi.get("min")
            # Skip thin signal — fewer than 5 flower SKUs isn't a meaningful avg
            if n < 5 or avg is None or not bk:
                continue
            by_brand[bk]["sum"] += avg * n
            by_brand[bk]["weight"] += n
            if mn is not None:
                by_brand[bk]["min"] = min(by_brand[bk]["min"], mn)

        for bk, agg in by_brand.items():
            wavg = agg["sum"] / agg["weight"]
            series[bk].append({
                "date": date_str,
                "avg": round(wavg, 2),
                "min": round(agg["min"], 2) if agg["min"] != float("inf") else None,
            })

    # Only show dispensaries with at least 3 data points
    final = {bk: pts for bk, pts in series.items() if len(pts) >= 3}

    return {
        "generated_at": datetime.now().isoformat(),
        "dates": sorted(dates_set),
        "dispensaries": final,
    }


# ─────────────────────────────────────────────────────────────────────────────
# BRANDS DATA — builds /brands-data.json (brands on sale today, cheapest source)
# ─────────────────────────────────────────────────────────────────────────────

def _norm_brand(raw: str) -> str:
    """Light normalization so 'kynd' / 'Kynd Cannabis' style variants collapse."""
    return re.sub(r'\s+', ' ', (raw or "").strip()).strip(" -|").lower()


def build_brands_data(data: dict) -> dict:
    """
    Aggregate today's curated deals by brand. The daily summary only stores the
    highlight/category deals (not full menus), so this is intentionally framed
    as 'brands on sale today, and where each is cheapest right now'.

    Returns a JSON-ready payload the /brands/ page renders client-side.
    """
    from collections import defaultdict
    from datetime import datetime

    # Gather every available deal item, dedupe by (name, dispensary).
    items = []
    for cat_items in (data.get("deals_by_category") or {}).values():
        items.extend(cat_items or [])
    for disp in data.get("dispensaries", []):
        items.extend(disp.get("highlights") or [])

    seen = set()
    by_brand = defaultdict(list)
    for it in items:
        brand_raw = (it.get("brand") or "").strip()
        if not brand_raw:
            continue
        key = (it.get("name", "").strip().lower(), it.get("dispensary", "").strip().lower())
        if key in seen or not key[0]:
            continue
        seen.add(key)
        by_brand[_norm_brand(brand_raw)].append({**it, "_brand_display": brand_raw})

    brands = []
    for _, entries in by_brand.items():
        # Display name = most common original spelling
        display = max(set(e["_brand_display"] for e in entries),
                      key=lambda b: sum(1 for e in entries if e["_brand_display"] == b))

        def _price(e):
            return e.get("price") if isinstance(e.get("price"), (int, float)) else 9e9
        cheapest = min(entries, key=_price)

        dispensaries = sorted({display_disp_name(e.get("dispensary", "")) for e in entries})
        categories   = sorted({CAT_DISPLAY.get(e.get("category", ""),
                               (e.get("category", "") or "").replace("_", " ").title())
                               for e in entries if e.get("category")})
        best_disc = max((int(e.get("discount_pct") or 0) for e in entries), default=0)

        c_orig = cheapest.get("original_price")
        brands.append({
            "name": display,
            "deal_count": len(entries),
            "dispensaries": dispensaries,
            "categories": [c for c in categories if c],
            "best_discount": best_disc,
            "cheapest": {
                "product": clean_product_name(cheapest.get("name", "")),
                "price": cheapest.get("price"),
                "original_price": c_orig if (isinstance(c_orig, (int, float)) and c_orig and c_orig > (cheapest.get("price") or 0)) else None,
                "on_sale": bool(cheapest.get("on_sale")),
                "discount_pct": int(cheapest.get("discount_pct") or 0),
                "category": CAT_DISPLAY.get(cheapest.get("category", ""),
                            (cheapest.get("category", "") or "").replace("_", " ").title()),
                "dispensary": display_disp_name(cheapest.get("dispensary", "")),
                "url": disp_url(cheapest.get("dispensary", "")),
            },
        })

    # Sort: most deals first, then biggest discount, then name
    brands.sort(key=lambda b: (-b["deal_count"], -b["best_discount"], b["name"].lower()))

    return {
        "generated_at": data.get("generated_at"),
        "verified_time": format_verified_time(data),
        "report_date": data.get("report_date"),
        "brand_count": len(brands),
        "brands": brands,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INJECTION
# ─────────────────────────────────────────────────────────────────────────────

def replace_between_markers(html: str, section: str, new_content: str) -> str:
    pattern = (
        rf'(<!-- AUTO:{re.escape(section)} -->)'
        rf'.*?'
        rf'(<!-- /AUTO:{re.escape(section)} -->)'
    )
    replacement = rf'\1\n{new_content}\n          \2'
    result, count = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if count == 0:
        print(f"  WARNING: marker AUTO:{section} not found — skipped")
    else:
        print(f"  ✅  {section}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    json_path = find_latest_json()
    print(f"Loading {json_path.name} …")

    with open(json_path) as f:
        data = json.load(f)

    report_date      = data.get("report_date", "unknown")
    total_products   = data.get("total_products", 0)

    global VERIFIED_TIME
    VERIFIED_TIME = format_verified_time(data)

    best_value_raw   = data.get("best_value_flower", [])
    by_cat           = data.get("deals_by_category", {})
    dispensaries     = data.get("dispensaries", [])

    # Dispensary count — ONE source of truth for every count shown on the page
    # (hero stat AND the "N dispensaries checked" trust line), so the two can
    # never disagree. Prefers the scraper's live_count; falls back to counting
    # live records, then records with highlights.
    dispensary_count = (
        data.get("live_count")
        or len([d for d in dispensaries if d.get("status") == "live"])
        or len([d for d in dispensaries if d.get("highlights")])
    )

    # Per-category deals (best highlight per dispensary)
    flower_deals  = best_highlight_per_dispensary(dispensaries, "flower") \
                    or deduplicate(by_cat.get("flower", []))
    conc_deals    = best_highlight_per_dispensary(dispensaries, "concentrates") \
                    or deduplicate(by_cat.get("concentrates", []))
    edible_deals  = best_highlight_per_dispensary(dispensaries, "edibles") \
                    or deduplicate(by_cat.get("edibles", []))
    preroll_deals = best_highlight_per_dispensary(dispensaries, "pre_rolls") \
                    or deduplicate(by_cat.get("pre_rolls", []))
    vape_deals    = best_highlight_per_dispensary(dispensaries, "vapes") \
                    or deduplicate(by_cat.get("vapes", []))

    print(f"  {dispensary_count} dispensaries · {total_products:,} products · {report_date}")
    print(f"  flower={len(flower_deals)}  conc={len(conc_deals)}  "
          f"edibles={len(edible_deals)}  pre_rolls={len(preroll_deals)}  vapes={len(vape_deals)}")

    html = INDEX_HTML.read_text(encoding="utf-8")
    print("Injecting sections …")

    # Format the report date: "2026-03-28" → "March 28, 2026"
    try:
        from datetime import datetime
        rd = datetime.strptime(report_date, "%Y-%m-%d")
        pretty_date = rd.strftime("%B %-d, %Y")
    except Exception:
        pretty_date = report_date

    # 1. Stats
    html = replace_between_markers(html, "stats",
        stats_html(dispensary_count, total_products))

    # 2. Hero mockup card
    # 2026-11-09: one best deal per category behind tabs (hero_best_html),
    # replacing the fixed top-3 list (mockup_html, kept above for rollback).
    html = replace_between_markers(html, "mockup",
        hero_best_html(dispensaries, pretty_date, disp_count=dispensary_count,
                       top_deals=data.get("top_deals")))

    # 3. Date header
    html = replace_between_markers(html, "deals-header",
        f'          <span class="section-updated">Prices updated {pretty_date}</span>')

    # 4. Single deal-cards grid (all categories, filtered by JS tabs)
    combined_deals = []
    for cat_name, deals in [
        ("flower",       flower_deals),
        ("concentrates", conc_deals),
        ("edibles",      edible_deals),
        ("pre_rolls",    preroll_deals),
        ("vapes",        vape_deals),
    ]:
        for d in deals:
            d = dict(d)  # copy so we don't mutate original
            if not d.get("category"):
                d["category"] = cat_name
            combined_deals.append(d)

    # Sort: on-sale first, then by discount descending
    combined_deals.sort(key=lambda d: (
        0 if d.get("on_sale") else 1,
        -(d.get("discount_pct") or 0)
    ))

    # Collapse sister-location duplicates (same product at, e.g., Garden Camp
    # Washington and Garden Sycamore renders as a single card).
    combined_deals = dedupe_sister_locations(combined_deals)

    deals_content = "\n".join(deal_card_html(d) for d in combined_deals[:CARDS_TOTAL])
    html = replace_between_markers(html, "deals", deals_content)

    # 4b. Lowest shelf price per standard size (2026-11-09) — ranks on the real
    # price, sale or not, so an everyday-low store is not hidden by the
    # discount-first deal grid. Never fatal.
    low = lowest_html(report_date)
    html = replace_between_markers(html, "lowest", low if low else
        '          <p class="low-lead">Today\'s lowest shelf prices are not available yet. Check back after the morning scan.</p>')

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"\n✅  index.html updated from {json_path.name}")

    # 5. Refresh /trends-data.json for the /trends/ chart page
    trends_path = SCRIPT_DIR / "trends-data.json"
    trends_payload = build_trends_data()
    trends_path.write_text(json.dumps(trends_payload, indent=2), encoding="utf-8")
    n_disp = len(trends_payload.get("dispensaries", {}))
    n_dates = len(trends_payload.get("dates", []))
    print(f"✅  trends-data.json refreshed ({n_disp} dispensaries, {n_dates} days)")

    # 5b. Per-dispensary SEO pages + the /dispensaries/ hub, and rewire the
    # homepage cards to point at them. Must run AFTER trends-data.json is written
    # — the pages read it for the 90-day chart and the citywide ranking, so on a
    # first run of the day they would otherwise chart yesterday's numbers.
    # Non-fatal by design: a failure here must never cost Matt the site refresh
    # or the newsletter, so it warns and carries on.
    try:
        import dispensary_pages
        dispensary_pages.build_all(data, trends_payload, SCRIPT_DIR)
    except Exception as exc:
        print(f"⚠️  dispensary pages skipped: {type(exc).__name__}: {exc}")

    # 6. Refresh /brands-data.json for the /brands/ directory page
    brands_path = SCRIPT_DIR / "brands-data.json"
    brands_payload = build_brands_data(data)
    brands_path.write_text(json.dumps(brands_payload, indent=2), encoding="utf-8")
    print(f"✅  brands-data.json refreshed ({brands_payload.get('brand_count', 0)} brands)")

    # 7. Price board + pulse strip (2026-11-09). Needs the ranking that
    # dispensary_pages just computed, so it is a second pass over index.html.
    # Non-fatal: on any failure yesterday's board stays and the run carries on.
    try:
        idx = INDEX_HTML.read_text(encoding="utf-8")
        idx = board_and_pulse(idx, data, brands_payload.get("brand_count", 0),
                              dispensary_count, total_products, pretty_date)
        INDEX_HTML.write_text(idx, encoding="utf-8")
    except Exception as exc:
        print(f"⚠️  price board / pulse skipped: {type(exc).__name__}: {exc}")

    print("\nNext steps:")
    print("  git add -A")
    print(f'  git commit -m "data: refresh {report_date}"')
    print("  git push origin main")


if __name__ == "__main__":
    main()
