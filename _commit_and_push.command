#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
# 2026-09-07: message used to be hardcoded to an old palette change, so every
# push was mislabelled. Now it takes an argument, or falls back to a dated one.
# A Cowork session can commit but CANNOT push (no SSH host keys in the sandbox),
# so "nothing to commit" here is normal - the push below is the point.
MSG="${1:-site: manual update $(date +%Y-%m-%d)}"
git commit -m "$MSG" || true
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Netlify auto-deploys from main; wait ~30-60s, then hard-refresh"
echo "(Cmd+Shift+R) and verify the change at:"
echo "  https://allcitygreens.com/"
echo ""
read -n 1
