#!/bin/bash
# One-click commit + push.
# Double-click in Finder to run.

cd "$(dirname "$0")"
echo "==> Clearing any stale git locks..."
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed

echo "==> Staging changes..."
git add -A
git status --short

echo ""
echo "==> Committing..."
git commit -m "site: fix subscribe form (Netlify function → Beehiiv API), add /about /privacy /terms pages, smarter clean_product_name"

echo ""
echo "==> Pushing to GitHub (Netlify auto-deploys from main)..."
git push origin main

echo ""
echo "==> Done."
echo ""
echo "⚠️  ONE-TIME SETUP — set the Beehiiv credentials in Netlify so the subscribe function can talk to Beehiiv:"
echo ""
echo "   1. Open https://app.netlify.com/sites/<site>/configuration/env"
echo "      (or: app.netlify.com → All City Greens → Site configuration → Environment variables)"
echo ""
echo "   2. Add two variables:"
echo "        BEEHIIV_API_KEY = (paste the same key that's in run_daily.sh)"
echo "        BEEHIIV_PUB_ID  = pub_cfb7a725-b946-4662-8a9d-1e6d84a01a6d"
echo ""
echo "   3. Redeploy: Deploys → Trigger deploy → Deploy site"
echo "      (the env vars only take effect on the next deploy)"
echo ""
echo "   After that, subscribe forms on the site will actually capture emails."
echo ""
echo "Press any key to close..."
read -n 1
