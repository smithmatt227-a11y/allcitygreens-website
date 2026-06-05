#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
git commit -m "Enlarge top logo, restyle deals card (smaller title + accent border), move Common Questions to /faq/ page linked in footer"
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Wait ~30-60s for Netlify deploy, then verify:"
echo "  https://allcitygreens.com/      — bigger top logo, smaller 'Today's Best Deals' title with accent border"
echo "  https://allcitygreens.com/faq/  — Common Questions page (linked in footer next to Contact)"
echo ""
read -n 1
