#!/usr/bin/env python3
"""
update_site.py — AC Greens website auto-updater
Reads the latest scraper JSON and injects fresh deal cards into index.html.

Usage:
  cd ~/Desktop/AC\ Greens/Website && python3 update_site.py

After running, commit and push:
  git add -A && git commit -m "data: refresh $(date +%Y-%m-%d)" && git push
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).parent
INDEX_HTML   = SCRIPT_DIR / "index.html"
DATA_DIR     = SCRIPT_DIR.parent / "Price Scraper" / "Data"

# Map every scraper dispensary name → direct website URL
DISPENSARY_URLS = {
    "Therapy Cannabis - Cincinnati":        "https://www.therapycannabis.com",
    "Story Cincinnati":                     "https://storycannabis.com",
    "Story Forest Park":                    "https://storycannabis.com",
    "Zen Leaf - Cincinnati":                "https://zenleaf.com",
    "Shangri-La Cincinnati":                "https://shangriladispensaries.com",
    "Shangri-La Monroe West":               "https://shangriladispensaries.com",
    "Shangri-La Monroe Superstore":         "https://shangriladispensaries.com",
    "The Garden Dispensary - Camp Washington": "https://thegardendispo.com",
    "The Garden Dispensary - Sycamore":     "https://thegardendispo.com",
    "Garden Club Dispensary":               "https://gardenclubdispensaries.com",
    "Trulieve - Cincinnati":                "https://www.trulieve.com",
    "The Landing - Cincinnati":             "https://www.thelandingdispensaries.com",
    "The Landing - Monroe":                 "https://www.thelandingdispensaries.com",
    "Nectar - Cincinnati":                  "https://nectarohio.com",
    "Nectar - 5 Mile":                      "https://nectarohio.com",
    "Nectar - Harrison":                    "https://nectarohio.com",
    "Sunnyside - Cincinnati":               "https://www.sunnyside.shop",
    "Verilife - Cincinnati":                "https://www.verilife.com/oh/locations/cincinnati",
    "Beyond Hello - Cincinnati":            "https://beyond-hello.com",
    "Beyond Hello - Northern Cincinnati":   "https://beyond-hello.com",
    "Beyond Hello - Oxford":               "https://beyond-hello.com",
    "AYR Wellness - Goshen":               "https://ayrdispensaries.com",
    "Queen City Cannabis - Harrison":       "https://queenccanna.com",
    "Ethos Dispensary - Lebanon":           "https://ethoscannabis.com",
    "UpLift - Milford":                     "https://www.upliftohio.com",
    "UpLift - Mount Orab":                  "https://www.upliftohio.com",
    "Columbia Care - Monroe":               "https://www.columbia.care/locations/ohio",
    "Bloom - Seven Mile":                   "https://bloommarijuana.com",
    "Green Releaf - Dayton":               "https://greenreleafdispensary.com",
    "Locals Cannabis":                      "https://localscannabis.com/shop/",
}

FALLBACK_URL = "https://allcitygreens.com"

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def find_latest_json() -> Path:
    """Return the most-recently-dated summary JSON file."""
    files = sorted(DATA_DIR.glob("summary_*.json"))
    if not files:
        sys.exit(f"ERROR: no summary_*.json found in {DATA_DIR}")
    return files[-1]


def parse_weight_grams(weight_label: str) -> float | None:
    """Convert a weight_label string to grams, or None if not parseable."""
    if not weight_label:
        return None
    w = weight_label.strip().lower()

    # Plain gram values: "2 g", "2.83 g", "1g", "3.5g"
    m = re.match(r'^([\d.]+)\s*g$', w)
    if m:
        return float(m.group(1))

    # Ounce fractions: "1/8 oz", "1/4 oz", "1/2 oz", "1 oz"
    m = re.match(r'^(\d+)/(\d+)\s*oz$', w)
    if m:
        return (int(m.group(1)) / int(m.group(2))) * 28.3495

    m = re.match(r'^(\d+)\s*oz$', w)
    if m:
        return int(m.group(1)) * 28.3495

    return None


def calc_price_per_gram(deal: dict) -> float | None:
    """Return a correctly computed price-per-gram, or None."""
    grams = parse_weight_grams(deal.get("weight_label", ""))
    if grams and grams > 0:
        return deal["price"] / grams
    return None


def fmt_thc(deal: dict) -> str:
    """Return a display string for THC, or empty string for edibles with mg values."""
    thc = deal.get("thc_pct", 0)
    cat = deal.get("category", "")
    if thc is None or thc <= 0:
        return ""
    # Edibles store mg as a percentage — skip display if >100
    if cat == "edibles" and thc > 100:
        return ""
    return f"{thc:.1f}% THC"


def display_disp_name(scraper_name: str) -> str:
    """
    Turn a scraper dispensary name into a short, pretty display string.
    "The Garden Dispensary - Camp Washington" → "The Garden · Camp Washington"
    "Verilife - Cincinnati"                   → "Verilife · Cincinnati"
    """
    # Strip common suffixes from the base name
    replacements = {
        "The Garden Dispensary": "The Garden",
        "Ethos Dispensary": "Ethos",
        "AYR Wellness": "AYR Wellness",
        "Queen City Cannabis": "Queen City",
        "Green Releaf": "Green Releaf",
    }
    name = scraper_name
    for long, short in replacements.items():
        if name.startswith(long):
            name = short + name[len(long):]
            break

    if " - " in name:
        parts = name.split(" - ", 1)
        return f"{parts[0].strip()} · {parts[1].strip()}"
    return name


def clean_product_name(raw_name: str, brand: str) -> str:
    """
    Strip brand/qualifier prefixes from product names.
    "King City Gardens | Gold | Fire Tropical Kush - Flower 2.83g"
    → "Fire Tropical Kush - Flower 2.83g"
    """
    if "|" in raw_name:
        # Take everything after the last pipe
        raw_name = raw_name.rsplit("|", 1)[-1].strip()
    return raw_name


def deduplicate(deals: list) -> list:
    """
    Remove duplicate products that appear as both recreational & medical.
    Key = (name, dispensary). Prefer recreational; keep first occurrence.
    """
    seen: dict[tuple, dict] = {}
    for deal in deals:
        key = (deal["name"].lower(), deal["dispensary"].lower())
        if key not in seen:
            seen[key] = deal
        else:
            # Prefer recreational over medical
            if deal.get("license_type") == "recreational":
                seen[key] = deal
    return list(seen.values())


def disp_url(scraper_name: str) -> str:
    return DISPENSARY_URLS.get(scraper_name, FALLBACK_URL)


# ─────────────────────────────────────────────────────────────────────────────
# HTML GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def deal_card_html(deal: dict) -> str:
    """Render a single <a class="deal-card"> block."""
    url        = disp_url(deal["dispensary"])
    cat        = deal.get("category", "").replace("_", " ").title()
    strain     = deal.get("strain_type", "")
    on_sale    = deal.get("on_sale", False)
    discount   = deal.get("discount_pct", 0)

    cat_line = cat
    if strain:
        cat_line += f" · {strain}"
    if on_sale and discount:
        cat_line += f" · {discount}% OFF"
    elif not on_sale:
        cat_line += " · Not on sale"

    product_name = clean_product_name(deal["name"], deal.get("brand", ""))
    disp_display = display_disp_name(deal["dispensary"])
    thc_str      = fmt_thc(deal)
    disp_detail  = disp_display
    if thc_str:
        disp_detail += f" · {thc_str}"

    price     = deal["price"]
    orig      = deal.get("original_price", price)
    ppg       = calc_price_per_gram(deal)

    price_html = f'<span class="deal-card-now">${price:.2f}</span>'
    if on_sale and orig and orig > price:
        price_html += f' <span class="deal-card-was">${orig:.2f}</span>'
    if ppg:
        price_html += f' <span class="deal-card-disp">${ppg:.2f}/g</span>'

    return (
        f'            <a class="deal-card" href="{url}" target="_blank" rel="noopener">\n'
        f'              <div class="deal-card-cat">{cat_line}</div>\n'
        f'              <div class="deal-card-name">{product_name}</div>\n'
        f'              <div class="deal-card-disp">{disp_detail}</div>\n'
        f'              <div class="deal-card-prices">\n'
        f'                {price_html}\n'
        f'              </div>\n'
        f'            </a>'
    )


def deals_grid_html(deals: list, cta_text: str) -> str:
    """Wrap deal cards in a .deals-grid + CTA line."""
    cards = "\n".join(deal_card_html(d) for d in deals)
    return (
        f'          <div class="deals-grid">\n'
        f'{cards}\n'
        f'          </div>\n'
        f'          <p class="deals-cta-line">{cta_text} — '
        f'<a href="https://allcitygreens.beehiiv.com/subscribe" target="_blank">subscribe free</a>.</p>'
    )


def stats_html(dispensary_count: int, total_products: int) -> str:
    """Render the three hero stats."""
    disp_str    = f"{dispensary_count}+"
    prod_k      = total_products // 100 * 100   # round down to nearest 100
    prod_str    = f"{prod_k:,}+"
    return (
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{disp_str}</span>\n'
        f'              <span class="stat-label">dispensaries tracked</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{prod_str}</span>\n'
        f'              <span class="stat-label">products monitored daily</span>\n'
        f'            </div>\n'
        f'            <div class="stat-divider" aria-hidden="true"></div>\n'
        f'            <div class="stat">\n'
        f'              <span class="stat-num">8 AM</span>\n'
        f'              <span class="stat-label">in your inbox every day</span>\n'
        f'            </div>'
    )


def best_value_html(items: list) -> str:
    """Render best-value flower cards (recalc price_per_gram)."""
    deduped = deduplicate(items)
    # Sort by computed price_per_gram ascending
    sortable = []
    for item in deduped:
        ppg = calc_price_per_gram(item)
        if ppg:
            sortable.append((ppg, item))
    sortable.sort(key=lambda x: x[0])
    top = [item for _, item in sortable[:8]]

    cards = "\n".join(deal_card_html(d) for d in top)
    cta = "Lowest prices per gram updated daily"
    return (
        f'          <div class="deals-grid">\n'
        f'{cards}\n'
        f'          </div>\n'
        f'          <p class="deals-cta-line">{cta} — '
        f'<a href="https://allcitygreens.beehiiv.com/subscribe" target="_blank">subscribe free</a> '
        f'to get them in your inbox.</p>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# INJECTION
# ─────────────────────────────────────────────────────────────────────────────

def replace_between_markers(html: str, section: str, new_content: str) -> str:
    """
    Replace everything between <!-- AUTO:section --> and <!-- /AUTO:section -->
    with new_content (preserving the markers themselves).
    """
    pattern = (
        rf'(<!-- AUTO:{re.escape(section)} -->)'
        rf'.*?'
        rf'(<!-- /AUTO:{re.escape(section)} -->)'
    )
    replacement = rf'\1\n{new_content}\n          \2'
    result, count = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if count == 0:
        print(f"  WARNING: marker AUTO:{section} not found — skipped")
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
    dispensary_count = data.get("dispensary_count", 30)
    total_products   = data.get("total_products", 0)
    top_deals        = deduplicate(data.get("top_deals", []))
    best_value       = data.get("best_value_flower", [])
    by_cat           = data.get("deals_by_category", {})

    # Slice to 6 cards per panel (good grid size)
    all_deals       = top_deals[:6]
    flower_deals    = deduplicate(by_cat.get("flower",       []))[:5]
    conc_deals      = deduplicate(by_cat.get("concentrates", []))[:5]
    edible_deals    = deduplicate(by_cat.get("edibles",      []))[:5]
    preroll_deals   = deduplicate(by_cat.get("pre_rolls",    []))[:5]

    print(f"  {dispensary_count} dispensaries · {total_products:,} products · report date {report_date}")
    print(f"  top_deals={len(all_deals)}  flower={len(flower_deals)}  conc={len(conc_deals)}  "
          f"edibles={len(edible_deals)}  pre_rolls={len(preroll_deals)}  best_value={len(best_value)}")

    html = INDEX_HTML.read_text(encoding="utf-8")

    print("Injecting sections …")

    html = replace_between_markers(html, "stats",
        stats_html(dispensary_count, total_products))

    # panel-all has a custom CTA suffix
    all_cards = "\n".join(deal_card_html(d) for d in all_deals)
    all_html = (
        '          <div class="deals-grid">\n'
        + all_cards + '\n'
        + '          </div>\n'
        '          <p class="deals-cta-line">Full deals land in your inbox every morning at 8 AM — '
        '<a href="https://allcitygreens.beehiiv.com/subscribe" target="_blank">subscribe free</a>'
        ' to see them all.</p>'
    )
    html = replace_between_markers(html, "panel-all", all_html)

    html = replace_between_markers(html, "panel-flower",
        deals_grid_html(flower_deals, "More flower deals in your daily email"))

    html = replace_between_markers(html, "panel-concentrates",
        deals_grid_html(conc_deals, "More concentrate deals in your daily email"))

    html = replace_between_markers(html, "panel-edibles",
        deals_grid_html(edible_deals, "More edible deals in your daily email"))

    html = replace_between_markers(html, "panel-prerolls",
        deals_grid_html(preroll_deals, "More pre-roll deals in your daily email"))

    html = replace_between_markers(html, "panel-bestvalue",
        best_value_html(best_value))

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"✅  index.html updated from {json_path.name}")
    print()
    print("Next steps:")
    print("  git add -A")
    print(f'  git commit -m "data: refresh {report_date}"')
    print("  git push")


if __name__ == "__main__":
    main()
