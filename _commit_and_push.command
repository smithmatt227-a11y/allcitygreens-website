#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
git commit -m "design: revert to Fjallraven palette + hunter green logo" || true
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Wait ~30-60s for Netlify deploy, then verify:"
echo "  https://allcitygreens.com/  — hunter green logo, olive/burnt-orange/sand palette (hard refresh: Cmd+Shift+R)"
echo ""
read -n 1
