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
    "The Garden Dispensary - Camp Washington": "https://thegardendispo.com/menu/",
    "The Garden Dispensary - Sycamore":        "https://thegardendispo.com/menu/",
    "Garden Club Dispensary":                  "https://gardenclubdispensaries.com",
    "Trulieve - Cincinnati":                   "https://www.trulieve.com",
    "The Landing - Cincinnati":                "https://www.thelandingdispensaries.com",
    "The Landing - Monroe":                    "https://www.thelandingdispensaries.com",
    "Nectar - Cincinnati":                     "https://nectarohio.com",
    "Nectar - 5 Mile":                         "https://nectarohio.com",
    "Nectar - Harrison":                       "https://nectarohio.com",
    "Sunnyside - Cincinnati":                  "https://www.sunnyside.shop",
    "Verilife - Cincinnati":                   "https://www.verilife.com/oh/locations/cincinnati",
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
    "Columbia Care - Monroe":                  "https://www.columbia.care/locations/ohio",
    "Bloom - Seven Mile":                      "https://bloommarijuana.com",
    "Green Releaf - Dayton":                   "https://greenreleafdispensary.com",
    "Locals Cannabis":                         "https://localscannabis.com/shop/",
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
            # Convert to US Eastern. EDT (UTC-4) is correct late Mar–early Nov;
            # the scrape runs in summer months, so -4 is a safe fixed offset.
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
        "Queen City Cannabis":   "Queen City",
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


def clean_product_name(raw_name: str) -> str:
    """
    Make a pipe-separated scraper name display-worthy.
    Strategy:
      1. Trim trailing per-unit weight/dose tokens (1g, 10mg/ea, .84g…). Pack
         counts (10pk, 60pk) are preserved — they're real product info.
      2. Drop a leading recognized brand prefix.
      3. Join remaining pipe-segments with ' — '.
    Always returns a usable product identity — never just '10mg/ea' or '60pk'.
    """
    if not raw_name:
        return ""
    s = raw_name.strip()
    if "|" not in s:
        return s
    parts = [p.strip() for p in s.split("|") if p.strip()]
    if len(parts) <= 1:
        return s
    # 1. Trim trailing weight-only tokens
    while len(parts) > 1 and _WEIGHT_OR_DOSE.match(parts[-1]):
        parts.pop()
    # 2. Drop leading brand if recognized
    if len(parts) > 1 and parts[0].lower().strip().rstrip(":") in _BRAND_PREFIXES:
        parts = parts[1:]
    return " — ".join(parts).strip() or s


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
    collapse into one. Mirrors the same helper in Newsletter/newsletter.py.
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

def deal_card_html(deal: dict) -> str:
    """Generate a deal card in the Perplexity design format with data-cat for JS filtering."""
    url       = disp_url(deal["dispensary"])
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

    if on_sale and orig and orig > price:
        pct_text = f"-{discount}%" if discount else "Top deal"
        prices_html = (
            f'<span class="deal-card-orig">${orig:.2f}</span>'
            f'<span class="deal-card-sale">${price:.2f}</span>'
            f'<span class="deal-card-pct">{pct_text}</span>'
        )
    else:
        ppg_str = f' · ${ppg:.2f}/g' if ppg else ''
        prices_html = f'<span class="deal-card-sale">${price:.2f}</span>'

    return (
        f'          <a class="deal-card deal-card-link" data-cat="{raw_cat}"'
        f' href="{url}" target="_blank" rel="noopener">\n'
        f'            <div class="deal-card-cat">{icon} {cat_label}</div>\n'
        f'            <div class="deal-card-name">{name}</div>\n'
        f'            <div class="deal-card-disp">{disp_detail}</div>\n'
        f'            <div class="deal-card-prices">\n'
        f'              {prices_html}\n'
        f'            </div>\n'
        f'          </a>'
    )


def mockup_row(deal: dict) -> str:
    """Generate a single row in the hero mockup card (Perplexity anchor format)."""
    name    = clean_product_name(deal["name"])
    url     = disp_url(deal["dispensary"])
    disp    = display_disp_name(deal["dispensary"])
    price   = deal["price"]
    orig    = deal.get("original_price", price)
    on_sale = deal.get("on_sale", False)
    disc    = deal.get("discount_pct", 0)
    ppg     = calc_ppg(deal)
    cat     = CAT_DISPLAY.get(deal.get("category", ""), "Product")

    ppg_str = f' · ${ppg:.2f}/g' if ppg else ''

    if on_sale and orig and orig > price:
        badge_text = f"Top deal"
        price_html = (
            f'<span class="deal-original">${orig:.2f}</span> '
            f'<span class="deal-sale">${price:.2f} '
            f'<span class="deal-badge">{badge_text}</span></span>'
        )
    else:
        price_html = f'<span class="deal-sale">${price:.2f}</span>'

    return (
        f'              <a class="mockup-deal mockup-deal-link" href="{url}" target="_blank" rel="noopener">\n'
        f'                <div class="deal-type">{cat}</div>\n'
        f'                <div class="deal-name">{name}</div>\n'
        f'                <div class="deal-disp">{disp}{ppg_str}</div>\n'
        f'                <div class="deal-price">{price_html}</div>\n'
        f'              </a>'
    )


def mockup_html(dispensaries: list, best_value: list) -> str:
    """
    Generate the hero mockup panel:
      - Today's Best Deals: up to 3 ON-SALE items, deduped by product name
        so the same product doesn't appear twice when sister dispensaries
        run the same sale (e.g. Garden Camp Washington + Garden Sycamore).
      - Best Value Eighths section: removed per design refresh.
    """
    # TODAY'S BEST DEALS — on-sale items, one per dispensary, sister-collapsed
    sale_deals = best_highlight_per_dispensary(dispensaries)
    sale_only  = [d for d in sale_deals if d.get("on_sale")]
    candidates = one_per_dispensary(sale_only) or one_per_dispensary(sale_deals)
    featured   = dedupe_sister_locations(candidates)[:3]

    deals_rows = "\n".join(mockup_row(d) for d in featured)
    disp_count = len([d for d in dispensaries if d.get("highlights")])

    # best_value retained as a function argument for backwards compat with the
    # caller, but no Best Value Eighths section is rendered any more.
    _ = best_value

    return (
        f'            <div class="mockup-section">\n'
        f'{deals_rows}\n'
        f'            </div>\n'
        f'            <div class="mockup-footer">✓ Prices verified this morning · {disp_count} dispensaries checked</div>'
    )


def stats_html(dispensary_count: int, total_products: int) -> str:
    prod_k = total_products // 100 * 100
    return (
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{dispensary_count}</span>\n'
        f'              <span class="stat-label">dispensaries tracked</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{prod_k:,}+</span>\n'
        f'              <span class="stat-label">products monitored daily</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">8 AM</span>\n'
        f'              <span class="stat-label">in your inbox every day</span>\n'
        f'            </div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# TRENDS DATA — builds /trends-data.json from all historical scrapes
# ─────────────────────────────────────────────────────────────────────────────

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

    def _brand_key(name: str) -> str:
        s = (name or "").lower().strip().split(" - ")[0].strip()
        for suf in (" cincinnati"," forest park"," sycamore"," milford"," mount orab",
                    " harrison"," oxford"," goshen"," lebanon"," monroe"," dayton",
                    " camp washington"," superstore"," seven mile"," 5 mile",
                    " five mile"," west"," east"," north"," south"," northern"):
            if s.endswith(suf):
                s = s[: -len(suf)].strip()
        return s

    for f in files:
        date_str = f.stem.replace("summary_", "")
        dates_set.add(date_str)
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        by_brand = defaultdict(lambda: {"sum": 0.0, "weight": 0, "min": float("inf")})
        for d in data.get("dispensaries", []):
            bk = _brand_key(d.get("name", ""))
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

    # Dispensary count for the hero stat row. Must match the count of brand
    # cards in the <section id="dispensaries"> grid below, since users will
    # see both numbers on the same page. Today's scrape can fluctuate
    # (some sites return 0 products on a given day), so we pin this to the
    # grid count and update it manually when a new brand card is added.
    dispensary_count = 9
    best_value_raw   = data.get("best_value_flower", [])
    by_cat           = data.get("deals_by_category", {})
    dispensaries     = data.get("dispensaries", [])

    # Per-category deals (best highlight per dispensary)
    flower_deals  = best_highlight_per_dispensary(dispensaries, "flower") \
                    or deduplicate(by_cat.get("flower", []))
    conc_deals    = best_highlight_per_dispensary(dispensaries, "concentrates") \
                    or deduplicate(by_cat.get("concentrates", []))
    edible_deals  = best_highlight_per_dispensary(dispensaries, "edibles") \
                    or deduplicate(by_cat.get("edibles", []))
    preroll_deals = best_highlight_per_dispensary(dispensaries, "pre_rolls") \
                    or deduplicate(by_cat.get("pre_rolls", []))

    print(f"  {dispensary_count} dispensaries · {total_products:,} products · {report_date}")
    print(f"  flower={len(flower_deals)}  conc={len(conc_deals)}  "
          f"edibles={len(edible_deals)}  pre_rolls={len(preroll_deals)}")

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
    html = replace_between_markers(html, "mockup",
        mockup_html(dispensaries, best_value_raw))

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

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"\n✅  index.html updated from {json_path.name}")

    # 5. Refresh /trends-data.json for the /trends/ chart page
    trends_path = SCRIPT_DIR / "trends-data.json"
    trends_payload = build_trends_data()
    trends_path.write_text(json.dumps(trends_payload, indent=2), encoding="utf-8")
    n_disp = len(trends_payload.get("dispensaries", {}))
    n_dates = len(trends_payload.get("dates", []))
    print(f"✅  trends-data.json refreshed ({n_disp} dispensaries, {n_dates} days)")

    # 6. Refresh /brands-data.json for the /brands/ directory page
    brands_path = SCRIPT_DIR / "brands-data.json"
    brands_payload = build_brands_data(data)
    brands_path.write_text(json.dumps(brands_payload, indent=2), encoding="utf-8")
    print(f"✅  brands-data.json refreshed ({brands_payload.get('brand_count', 0)} brands)")

    print("\nNext steps:")
    print("  git add -A")
    print(f'  git commit -m "data: refresh {report_date}"')
    print("  git push origin main")


if __name__ == "__main__":
    main()
