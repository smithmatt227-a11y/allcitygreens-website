#!/bin/bash
# One-click commit + push for the site cleanup.
# Double-click this in Finder to run it.

cd "$(dirname "$0")"
echo "==> Clearing any stale git locks..."
rm -f .git/HEAD.lock .git/index.lock .git/index.lock.removed

echo "==> Staging changes..."
git add -A
git status --short

echo ""
echo "==> Committing..."
git commit -m "site: collapse same-product sister locations into one card across hero mockup + lower deals grid"

echo ""
echo "==> Pushing to GitHub (Netlify auto-deploys from main)..."
git push origin main

echo ""
echo "==> Done. Watch deploy at: https://app.netlify.com (site: 015aa9c8-79d8-4c55-baa8-1a29737120bd)"
echo "==> Live URL: https://allcitygreens.com"
echo ""
echo "Press any key to close..."
read -n 1
