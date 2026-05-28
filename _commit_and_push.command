#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
git commit -m "site: chart-wrapper height fix, '9 dispensaries' replaces stale '14' across copy, strip Perplexity attribution"
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Wait ~30-60s for Netlify deploy, then verify:"
echo "  https://allcitygreens.com/trends/  — chart + legend layout"
echo "  https://allcitygreens.com/         — hero stat reads '9 dispensaries tracked'"
echo ""
read -n 1
