#!/bin/bash
cd "$(dirname "$0")"
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed 2>/dev/null

git add -A
git status --short

echo ""
git commit -m "subscribe fn: add double_opt_override=on so API subs land as Active (Beehiiv defaults to 'validating')"
echo ""
echo "==> Pushing..."
git push origin main
echo ""
echo "Done. Wait ~30-60s for Netlify deploy, then test."
echo ""
read -n 1
