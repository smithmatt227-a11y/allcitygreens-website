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
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
INDEX_HTML = SCRIPT_DIR / "index.html"
DATA_DIR   = SCRIPT_DIR.parent / "Price Scraper" / "Data"

# How many cards to show before "Show more" button appears
CARDS_VISIBLE = 6
# Total cards to generate per panel (hidden ones revealed by Show More)
CARDS_TOTAL   = 12

SUBSCRIBE_URL = "https://allcitygreens.beehiiv.com/subscribe"

# Map every scraper dispensary name → direct website URL
DISPENSARY_URLS = {
    "Therapy Cannabis - Cincinnati":           "https://www.therapycannabis.com",
    "Story Cincinnati":                        "https://storycannabis.com",
    "Story Forest Park":                       "https://storycannabis.com",
    "Zen Leaf - Cincinnati":                   "https://zenleaf.com",
    "Shangri-La Cincinnati":                   "https://shangriladispensaries.com",
    "Shangri-La Monroe West":                  "https://shangriladispensaries.com",
    "Shangri-La Monroe Superstore":            "https://shangriladispensaries.com",
    "The Garden Dispensary - Camp Washington": "https://thegardendispo.com",
    "The Garden Dispensary - Sycamore":        "https://thegardendispo.com",
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
    "UpLift - Milford":                        "https://www.upliftohio.com",
    "UpLift - Mount Orab":                     "https://www.upliftohio.com",
    "Columbia Care - Monroe":                  "https://www.columbia.care/locations/ohio",
    "Bloom - Seven Mile":                      "https://bloommarijuana.com",
    "Green Releaf - Dayton":                   "https://greenreleafdispensary.com",
    "Locals Cannabis":                         "https://localscannabis.com/shop/",
}

FALLBACK_URL = "https://allcitygreens.com"

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
        return f"{parts[0].strip()} · {parts[1].strip()}"
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
    If category is given, filter highlights to that category first.
    Returns one deal per dispensary, sorted: on_sale first then by ppg.
    """
    results = []
    for disp in dispensaries:
        highlights = disp.get("highlights") or []
        if category:
            highlights = [h for h in highlights if h.get("category") == category]
        if not highlights:
            continue
        # Prefer on_sale
        on_sale = [h for h in highlights if h.get("on_sale")]
        candidates = on_sale if on_sale else highlights
        # Within candidates, pick lowest ppg (or first if none computable)
        with_ppg = [(calc_ppg(h) or 9999, h) for h in candidates]
        with_ppg.sort(key=lambda x: x[0])
        results.append(with_ppg[0][1])

    # Sort results: on_sale first, then by ppg
    def sort_key(deal):
        return (0 if deal.get("on_sale") else 1, calc_ppg(deal) or 9999)
    results.sort(key=sort_key)
    return results


def disp_url(scraper_name: str) -> str:
    return DISPENSARY_URLS.get(scraper_name, FALLBACK_URL)


# ─────────────────────────────────────────────────────────────────────────────
# HTML GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def deal_card_html(deal: dict, hidden: bool = False) -> str:
    url      = disp_url(deal["dispensary"])
    cat      = deal.get("category", "").replace("_", " ").title()
    strain   = deal.get("strain_type", "")
    on_sale  = deal.get("on_sale", False)
    discount = deal.get("discount_pct", 0)

    raw_cat   = deal.get("category", "")
    cat_label = raw_cat.replace("_", " ").title()
    strain    = deal.get("strain_type", "")

    # Category color pill
    pill_html = (
        f'<span class="deal-cat-pill deal-cat-pill--{raw_cat}">'
        f'{cat_label}</span>'
    )

    # Strain type + sale badge inline after pill
    strain_text = f" {strain}" if strain else ""
    sale_badge  = (
        f' <span class="deal-sale-badge">{discount}% OFF</span>'
        if on_sale and discount else ""
    )
    cat_html = f'{pill_html}{strain_text}{sale_badge}'

    name         = clean_product_name(deal["name"])
    brand        = deal.get("brand", "").strip()
    disp_display = display_disp_name(deal["dispensary"])
    thc_str      = fmt_thc(deal)
    disp_detail  = disp_display + (f" · {thc_str}" if thc_str else "")

    price = deal["price"]
    orig  = deal.get("original_price", price)
    ppg   = calc_ppg(deal)
    save  = round(orig - price, 2) if on_sale and orig and orig > price else 0

    price_html = f'<span class="deal-card-now">${price:.2f}</span>'
    if on_sale and orig and orig > price:
        price_html += f' <span class="deal-card-was">${orig:.2f}</span>'
    if ppg:
        price_html += f' <span class="deal-card-disp">${ppg:.2f}/g</span>'
    if save:
        price_html += f' <span class="deal-card-save">save ${save:.2f}</span>'

    hidden_attr  = ' data-hidden="true"' if hidden else ''
    hidden_class = " deal-card--hidden" if hidden else ""
    sale_attr    = ' data-sale="true"' if on_sale else ''

    # Brand line (skip if empty or same as dispensary name)
    brand_html = ""
    if brand and brand.lower() not in name.lower():
        brand_html = f'              <div class="deal-card-brand">{brand}</div>\n'

    return (
        f'            <a class="deal-card{hidden_class}" href="{url}" '
        f'target="_blank" rel="noopener"{hidden_attr}{sale_attr}>\n'
        f'              <div class="deal-card-cat">{cat_html}</div>\n'
        f'              <div class="deal-card-name">{name}</div>\n'
        f'{brand_html}'
        f'              <div class="deal-card-disp">{disp_detail}</div>\n'
        f'              <div class="deal-card-prices">\n'
        f'                {price_html}\n'
        f'              </div>\n'
        f'            </a>'
    )


def deals_panel_html(deals: list, cta_text: str,
                     visible: int = CARDS_VISIBLE,
                     total: int = CARDS_TOTAL) -> str:
    """
    Generate a deals-grid with up to `total` cards.
    Cards beyond `visible` get class deal-card--hidden and are revealed
    by the Show More button.
    """
    shown  = deals[:visible]
    hidden = deals[visible:total]

    cards = "\n".join(deal_card_html(d, hidden=False) for d in shown)
    if hidden:
        cards += "\n" + "\n".join(deal_card_html(d, hidden=True) for d in hidden)

    show_more = ""
    if hidden:
        show_more = (
            '\n          <button class="show-more-btn" '
            'onclick="showMore(this)" aria-expanded="false">'
            f'Show {len(hidden)} more deals ▾</button>'
        )

    return (
        f'          <div class="deals-grid">\n'
        f'{cards}\n'
        f'          </div>'
        f'{show_more}\n'
        f'          <p class="deals-cta-line">{cta_text} — '
        f'<a href="{SUBSCRIBE_URL}" target="_blank">subscribe free</a>.</p>'
    )


def mockup_html(top_deals: list, best_value: list) -> str:
    """
    Generate the hero mockup panel content — 2 featured deals + 1 best value item.
    Picks from different dispensaries, prefers on-sale items for the deals section.
    """
    def mockup_deal_row(deal: dict, show_ppg: bool = False) -> str:
        name    = clean_product_name(deal["name"])
        disp    = display_disp_name(deal["dispensary"])
        price   = deal["price"]
        orig    = deal.get("original_price", price)
        on_sale = deal.get("on_sale", False)
        disc    = deal.get("discount_pct", 0)
        ppg     = calc_ppg(deal)

        meta = disp
        if show_ppg and ppg:
            meta += f" · ${ppg:.2f}/g"

        price_html = ""
        if on_sale and orig and orig > price:
            price_html = (
                f'<span class="deal-original">${orig:.2f}</span> '
                f'<span class="deal-sale">${price:.2f} '
                f'<span class="deal-badge">-{disc}%</span></span>'
            )
        elif show_ppg and ppg:
            price_html = (
                f'<span class="deal-sale">${price:.2f} '
                f'<span class="deal-badge deal-badge--value">${ppg:.2f}/g</span></span>'
            )
        else:
            price_html = f'<span class="deal-sale">${price:.2f}</span>'

        return (
            f'              <div class="mockup-deal">\n'
            f'                <div class="deal-name">{name}</div>\n'
            f'                <div class="deal-meta">{meta}</div>\n'
            f'                <div class="deal-price">{price_html}</div>\n'
            f'              </div>'
        )

    # Pick 2 featured deals: prioritise on-sale, one per dispensary
    featured = []
    seen = set()
    for deal in top_deals:
        d = deal["dispensary"].lower()
        if d not in seen:
            seen.add(d)
            featured.append(deal)
        if len(featured) == 2:
            break

    # Best value: top item from best_value list (already sorted by $/g)
    bv_items = [i for i in best_value if _meaningful_weight(i)]
    bv_diverse = one_per_dispensary(
        sorted(bv_items, key=lambda x: calc_ppg(x) or 9999)
    )
    best = bv_diverse[0] if bv_diverse else None

    deals_rows = "\n".join(mockup_deal_row(d) for d in featured)
    best_row   = mockup_deal_row(best, show_ppg=True) if best else ""

    return (
        f'            <div class="mockup-section">\n'
        f'              <div class="mockup-section-label">🔥 Today\'s Best Deals</div>\n'
        f'{deals_rows}\n'
        f'            </div>\n'
        f'            <div class="mockup-section">\n'
        f'              <div class="mockup-section-label">💰 Best Value Eighths</div>\n'
        f'{best_row}\n'
        f'            </div>\n'
        f'            <div class="mockup-footer">✓ Prices verified this morning · 30+ dispensaries checked</div>'
    )


def stats_html(dispensary_count: int, total_products: int) -> str:
    prod_k = total_products // 100 * 100
    return (
        f'            <div class="stat">\n'
        f'              <span class="stat-num">{dispensary_count}+</span>\n'
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


def _meaningful_weight(deal: dict) -> bool:
    """True if this product has a parseable weight of at least 1g — filters out infused pre-rolls etc."""
    grams = parse_weight_grams(deal.get("weight_label", ""))
    return grams is not None and grams >= 1.0


def best_value_panel_html(items: list) -> str:
    """Flower sorted by price/gram ascending, one per dispensary, with Show More."""
    deduped = [i for i in deduplicate(items) if _meaningful_weight(i)]
    sortable = [(calc_ppg(i), i) for i in deduped if calc_ppg(i)]
    sortable.sort(key=lambda x: x[0])
    ranked = [item for _, item in sortable]
    diverse = one_per_dispensary(ranked)

    shown  = diverse[:CARDS_VISIBLE]
    hidden = diverse[CARDS_VISIBLE:CARDS_TOTAL]

    cards = "\n".join(deal_card_html(d, hidden=False) for d in shown)
    if hidden:
        cards += "\n" + "\n".join(deal_card_html(d, hidden=True) for d in hidden)

    show_more = ""
    if hidden:
        show_more = (
            '\n          <button class="show-more-btn" '
            'onclick="showMore(this)" aria-expanded="false">'
            f'Show {len(hidden)} more deals ▾</button>'
        )

    cta = "Lowest prices per gram updated daily"
    return (
        f'          <div class="deals-grid">\n'
        f'{cards}\n'
        f'          </div>'
        f'{show_more}\n'
        f'          <p class="deals-cta-line">{cta} — '
        f'<a href="{SUBSCRIBE_URL}" target="_blank">subscribe free</a> '
        f'to get them in your inbox.</p>'
    )


def everyday_value_panel_html(dispensaries: list) -> str:
    """
    Lowest everyday (non-sale) flower prices, one per dispensary.
    Drawn from each dispensary's highlights — no sales, just cheap.
    """
    # Get all flower highlights that are NOT on sale
    not_on_sale = []
    for disp in dispensaries:
        for h in (disp.get("highlights") or []):
            if h.get("category") == "flower" and not h.get("on_sale") and _meaningful_weight(h):
                not_on_sale.append(h)

    deduped = deduplicate(not_on_sale)
    sortable = [(calc_ppg(i), i) for i in deduped if calc_ppg(i)]
    sortable.sort(key=lambda x: x[0])
    ranked = [item for _, item in sortable]
    diverse = one_per_dispensary(ranked)

    shown  = diverse[:CARDS_VISIBLE]
    hidden = diverse[CARDS_VISIBLE:CARDS_TOTAL]

    cards = "\n".join(deal_card_html(d, hidden=False) for d in shown)
    if hidden:
        cards += "\n" + "\n".join(deal_card_html(d, hidden=True) for d in hidden)

    show_more = ""
    if hidden:
        show_more = (
            '\n          <button class="show-more-btn" '
            'onclick="showMore(this)" aria-expanded="false">'
            f'Show {len(hidden)} more deals ▾</button>'
        )

    cta = "No gimmicks — just dispensaries with low everyday prices"
    return (
        f'          <div class="deals-grid">\n'
        f'{cards}\n'
        f'          </div>'
        f'{show_more}\n'
        f'          <p class="deals-cta-line">{cta} — '
        f'<a href="{SUBSCRIBE_URL}" target="_blank">subscribe free</a>.</p>'
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
    best_value_raw   = data.get("best_value_flower", [])
    by_cat           = data.get("deals_by_category", {})
    dispensaries     = data.get("dispensaries", [])

    # All Deals: one highlight per dispensary = true variety
    all_deals = best_highlight_per_dispensary(dispensaries)

    # Category panels: best highlight per dispensary for that category
    # Fall back to deals_by_category (deduped) if highlights don't cover a category
    flower_deals  = best_highlight_per_dispensary(dispensaries, "flower") \
                    or deduplicate(by_cat.get("flower", []))
    conc_deals    = best_highlight_per_dispensary(dispensaries, "concentrates") \
                    or deduplicate(by_cat.get("concentrates", []))
    edible_deals  = best_highlight_per_dispensary(dispensaries, "edibles") \
                    or deduplicate(by_cat.get("edibles", []))
    preroll_deals = best_highlight_per_dispensary(dispensaries, "pre_rolls") \
                    or deduplicate(by_cat.get("pre_rolls", []))

    print(f"  {dispensary_count} dispensaries · {total_products:,} products · report {report_date}")
    print(f"  all={len(all_deals)}  flower={len(flower_deals)}  conc={len(conc_deals)}  "
          f"edibles={len(edible_deals)}  pre_rolls={len(preroll_deals)}  "
          f"best_value={len(best_value_raw)}")

    html = INDEX_HTML.read_text(encoding="utf-8")
    print("Injecting sections …")

    # Format the report date nicely: "2026-03-28" → "March 28, 2026"
    try:
        from datetime import datetime
        rd = datetime.strptime(report_date, "%Y-%m-%d")
        pretty_date = rd.strftime("%B %-d, %Y")
    except Exception:
        pretty_date = report_date

    html = replace_between_markers(html, "mockup",
        mockup_html(all_deals, best_value_raw))

    html = replace_between_markers(html, "deals-header",
        f'          <span class="section-updated">Prices updated {pretty_date}</span>')

    html = replace_between_markers(html, "stats",
        stats_html(dispensary_count, total_products))

    # panel-all: one per dispensary, custom CTA
    all_shown  = all_deals[:CARDS_VISIBLE]
    all_hidden = all_deals[CARDS_VISIBLE:CARDS_TOTAL]
    all_cards  = "\n".join(deal_card_html(d) for d in all_shown)
    if all_hidden:
        all_cards += "\n" + "\n".join(deal_card_html(d, hidden=True) for d in all_hidden)
    show_more_all = ""
    if all_hidden:
        show_more_all = (
            '\n          <button class="show-more-btn" '
            'onclick="showMore(this)" aria-expanded="false">'
            f'Show {len(all_hidden)} more deals ▾</button>'
        )
    all_html = (
        '          <div class="deals-grid">\n'
        + all_cards + '\n'
        + '          </div>'
        + show_more_all + '\n'
        + '          <p class="deals-cta-line">Full deals land in your inbox every morning at 8 AM — '
        + f'<a href="{SUBSCRIBE_URL}" target="_blank">subscribe free</a> to see them all.</p>'
    )
    html = replace_between_markers(html, "panel-all", all_html)

    html = replace_between_markers(html, "panel-flower",
        deals_panel_html(flower_deals, "More flower deals in your daily email"))

    html = replace_between_markers(html, "panel-concentrates",
        deals_panel_html(conc_deals, "More concentrate deals in your daily email"))

    html = replace_between_markers(html, "panel-edibles",
        deals_panel_html(edible_deals, "More edible deals in your daily email"))

    html = replace_between_markers(html, "panel-prerolls",
        deals_panel_html(preroll_deals, "More pre-roll deals in your daily email"))

    html = replace_between_markers(html, "panel-bestvalue",
        best_value_panel_html(best_value_raw))

    html = replace_between_markers(html, "panel-everyday",
        everyday_value_panel_html(dispensaries))

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"✅  index.html updated from {json_path.name}")
    print()
    print("Next steps:")
    print("  git add -A")
    print(f'  git commit -m "data: refresh {report_date}"')
    print("  git push")


if __name__ == "__main__":
    main()
