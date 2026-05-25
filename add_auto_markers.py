#!/usr/bin/env python3
"""
add_auto_markers.py
Adds AUTO: comment markers to index.html so update_site.py can inject daily deals.
Run ONCE from ~/Desktop/AC Greens/Website/ — then run update_site.py.
"""
import re
from pathlib import Path

HTML_FILE = Path("index.html")
html = HTML_FILE.read_text(encoding="utf-8")
print(f"Read {len(html):,} chars from {HTML_FILE}")

# ── Helpers ──────────────────────────────────────────────────────────────────

def find_closing_div(html, start_pos):
    """Return position of the </div> that closes the div whose opening tag ended at start_pos."""
    depth = 1
    pos   = start_pos
    while pos < len(html) and depth > 0:
        nxt_open  = html.find('<div', pos)
        nxt_close = html.find('</div>', pos)
        if nxt_close == -1:
            return -1
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            pos = nxt_open + 4
        else:
            depth -= 1
            if depth == 0:
                return nxt_close
            pos = nxt_close + 6
    return -1


def wrap_by_id(html, div_id, marker_name, indent="          "):
    """Wrap the interior of <div id="div_id"> with AUTO markers."""
    pattern = rf'(<div[^>]*\bid="{re.escape(div_id)}"[^>]*>)'
    m = re.search(pattern, html)
    if not m:
        print(f"  ❌  {marker_name}: div id='{div_id}' not found")
        return html
    after_open = m.end()
    close_pos  = find_closing_div(html, after_open)
    if close_pos == -1:
        print(f"  ❌  {marker_name}: closing </div> not found")
        return html
    # Insert from end → start so positions stay valid
    html = (html[:close_pos]
            + f"\n{indent}<!-- /AUTO:{marker_name} -->\n{indent}"
            + html[close_pos:])
    html = (html[:after_open]
            + f"\n{indent}<!-- AUTO:{marker_name} -->"
            + html[after_open:])
    print(f"  ✅  {marker_name}")
    return html


def wrap_by_class(html, div_class, marker_name, indent="            ", nth=0):
    """Wrap the interior of the nth <div class="div_class"> with AUTO markers."""
    pattern = rf'(<div class="{re.escape(div_class)}")'
    matches = list(re.finditer(pattern, html))
    if not matches or nth >= len(matches):
        print(f"  ❌  {marker_name}: div class='{div_class}' not found (match #{nth})")
        return html
    m = matches[nth]
    # Advance past the full opening tag (may have more attrs — find the '>')
    tag_end = html.index('>', m.start()) + 1
    close_pos = find_closing_div(html, tag_end)
    if close_pos == -1:
        print(f"  ❌  {marker_name}: closing </div> not found")
        return html
    html = (html[:close_pos]
            + f"\n{indent}<!-- /AUTO:{marker_name} -->\n{indent}"
            + html[close_pos:])
    html = (html[:tag_end]
            + f"\n{indent}<!-- AUTO:{marker_name} -->"
            + html[tag_end:])
    print(f"  ✅  {marker_name}")
    return html

# ── Add markers ───────────────────────────────────────────────────────────────
print("\nAdding markers…")

# 1. stats — inside <div class="hero-stats">
html = wrap_by_class(html, "hero-stats", "stats", indent="            ")

# 2. mockup — inside <div class="hero-deals-card"> wrap just the dynamic area:
#    from the "Top 3 deals preview" comment through before hdc-footer.
#    We insert a targeted open/close pair using unique anchor strings.
MOCK_OPEN_ANCHOR  = '            <!-- Top 3 deals preview -->'
MOCK_CLOSE_ANCHOR = '\n\n            <div class="hdc-footer">'
idx_open  = html.find(MOCK_OPEN_ANCHOR)
idx_close = html.find('<div class="hdc-footer">')
if idx_open != -1 and idx_close != -1:
    # close marker goes on the line before hdc-footer
    newline_before_footer = html.rfind('\n', 0, idx_close)
    html = (html[:newline_before_footer]
            + "\n            <!-- /AUTO:mockup -->"
            + html[newline_before_footer:])
    # Re-find open anchor after close insertion
    idx_open = html.find(MOCK_OPEN_ANCHOR)
    html = (html[:idx_open]
            + "            <!-- AUTO:mockup -->\n"
            + html[idx_open:])
    print("  ✅  mockup")
else:
    print(f"  ❌  mockup: anchor(s) not found  open={idx_open}  close={idx_close}")

# 3. deals-header — the section-header div inside #deals
deals_pos = html.find('id="deals"')
if deals_pos != -1:
    pattern = r'<div class="section-header">'
    m = re.search(pattern, html[deals_pos:])
    if m:
        abs_start  = deals_pos + m.start()
        tag_end    = html.index('>', abs_start) + 1
        close_pos  = find_closing_div(html, tag_end)
        if close_pos != -1:
            html = (html[:close_pos]
                    + "\n          <!-- /AUTO:deals-header -->\n          "
                    + html[close_pos:])
            html = (html[:tag_end]
                    + "\n          <!-- AUTO:deals-header -->"
                    + html[tag_end:])
            print("  ✅  deals-header")
        else:
            print("  ❌  deals-header: closing </div> not found")
    else:
        print("  ❌  deals-header: section-header not found in #deals")
else:
    print("  ❌  deals-header: #deals section not found")

# 4–10. Deal panels (by id)
for div_id, marker in [
    ("panel-all",          "panel-all"),
    ("panel-flower",       "panel-flower"),
    ("panel-concentrates", "panel-concentrates"),
    ("panel-edibles",      "panel-edibles"),
    ("panel-prerolls",     "panel-prerolls"),
    ("panel-bestvalue",    "panel-bestvalue"),
    ("panel-everyday",     "panel-everyday"),
]:
    html = wrap_by_id(html, div_id, marker, indent="          ")

# ── Verify ────────────────────────────────────────────────────────────────────
count = html.count("<!-- AUTO:")
print(f"\nMarkers inserted: {count} opening tags found (expect 10)")

HTML_FILE.write_text(html, encoding="utf-8")
print(f"Saved {HTML_FILE}\n")
print("Next steps:")
print("  python3 update_site.py")
print("  git add index.html && git commit -m 'fix: add AUTO markers + inject today data' && git push origin main")
