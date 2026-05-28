#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
git commit -m "site: brand-matched og:image, /trends/ price-history chart page, daily trends-data.json regeneration"
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Wait ~30-60s for Netlify deploy."
echo ""
echo "Then visit:"
echo "  https://allcitygreens.com/trends/   — the new chart page"
echo "  https://allcitygreens.com/og-image.png — the social preview"
echo ""
read -n 1
