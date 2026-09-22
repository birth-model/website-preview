#!/usr/bin/env bash
#
# Deploy the site to S3 + CloudFront with correct caching.
#
#   BUCKET=my-bucket DISTRIBUTION_ID=E123ABC ./deploy.sh
#   DRY_RUN=1 BUCKET=my-bucket DISTRIBUTION_ID=E123ABC ./deploy.sh   # show only
#
# Why two passes: S3 has no per-directory header config, so Cache-Control has to
# be set as object metadata at upload time, and it differs by file type.
#
#   HTML    -> no-store. Page URLs are permanent, so a cached copy would keep
#              pointing at old asset URLs. This is the setting that prevents the
#              "why am I still seeing the old version" class of bug.
#   Assets  -> one year, immutable. Safe because cache-bust.py fingerprints every
#              asset URL, so changed files arrive under a new URL.
#
set -euo pipefail

: "${BUCKET:?set BUCKET to the S3 bucket name}"
: "${DISTRIBUTION_ID:?set DISTRIBUTION_ID to the CloudFront distribution id}"
DRY_RUN="${DRY_RUN:-}"

run() {
  if [[ -n "$DRY_RUN" ]]; then printf '  [dry-run] %s\n' "$*"; else "$@"; fi
}

echo "==> Fingerprinting assets"
python3 cache-bust.py

echo
echo "==> Verifying every stamped asset resolves"
python3 cache-bust.py --check

echo
echo "==> Uploading fingerprinted assets (cache forever)"
run aws s3 sync . "s3://${BUCKET}" \
  --exclude "*" \
  --include "*.css" --include "*.js" \
  --include "*.png" --include "*.jpg" --include "*.jpeg" \
  --include "*.webp" --include "*.avif" --include "*.svg" \
  --include "*.gif" --include "*.ico" \
  --include "*.woff" --include "*.woff2" \
  --cache-control "public, max-age=31536000, immutable" \
  --delete

echo
echo "==> Uploading HTML (never cached)"
run aws s3 sync . "s3://${BUCKET}" \
  --exclude "*" --include "*.html" \
  --cache-control "no-store, must-revalidate" \
  --content-type "text/html; charset=utf-8" \
  --delete

echo
echo "==> Invalidating CloudFront HTML at the edge"
# Only the HTML needs invalidating. Fingerprinted assets never need it, which
# keeps invalidations small and well under the free monthly allowance.
run aws cloudfront create-invalidation \
  --distribution-id "${DISTRIBUTION_ID}" \
  --paths "/" "/*.html"

echo
echo "Done."
