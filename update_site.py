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


def clean_product_name(raw_name: str) -> str:
    if "|" in raw_name:
        raw_name = raw_name.rsplit("|", 1)[-1].strip()
    return raw_name


def deduplicate(deals: list) -> list:
    """Remove rec+medical duplicates. Key = (name, dispensary). Prefer recreational."""
    seen = {}
    for deal in deals:
        key = (deal["name"].lower(), deal["dispensary"].lower())
        if key not in seen or deal.get("license_type") == "recreational":
            seen[key] = deal
    return list(seen.values())


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
      - Today's Best Deals: up to 3 ON-SALE items, one per dispensary
      - Best Value Eighths: top 2 lowest $/g flower items
    """
    # TODAY'S BEST DEALS — on-sale items only, one per dispensary
    sale_deals = best_highlight_per_dispensary(dispensaries)
    sale_only  = [d for d in sale_deals if d.get("on_sale")]
    featured   = one_per_dispensary(sale_only)[:3]
    if not featured:
        featured = one_per_dispensary(sale_deals)[:3]

    # BEST VALUE EIGHTHS — lowest $/g flower
    bv_items   = [i for i in best_value if _meaningful_weight(i)]
    bv_sorted  = sorted(bv_items, key=lambda x: calc_ppg(x) or 9999)
    bv_diverse = one_per_dispensary(bv_sorted)[:2]

    deals_rows = "\n".join(mockup_row(d) for d in featured)
    value_rows = "\n".join(mockup_row(d) for d in bv_diverse)

    disp_count = len([d for d in dispensaries if d.get("highlights")])

    return (
        f'            <div class="mockup-section">\n'
        f'              <div class="mockup-section-label">🔥 TODAY\'S BEST DEALS</div>\n'
        f'{deals_rows}\n'
        f'            </div>\n'
        f'            <div class="mockup-section">\n'
        f'              <div class="mockup-section-label">💰 BEST VALUE EIGHTHS</div>\n'
        f'{value_rows}\n'
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
    dispensary_count = 14  # fixed: advertise only Cincinnati-area dispensaries with active coverage
    total_products   = data.get("total_products", 0)
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

    deals_content = "\n".join(deal_card_html(d) for d in combined_deals[:CARDS_TOTAL])
    html = replace_between_markers(html, "deals", deals_content)

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"\n✅  index.html updated from {json_path.name}")
    print("\nNext steps:")
    print("  git add -A")
    print(f'  git commit -m "data: refresh {report_date}"')
    print("  git push origin main")


if __name__ == "__main__":
    main()
