#!/usr/bin/env bash
# Spec 33 C14: the web app sends its six security headers on a page and on /healthz.
# Usage: bash headers-check.sh http://localhost:3000   (or the staging URL)
set -euo pipefail
base="${1:?usage: headers-check.sh <base url>}"
required=(
  "strict-transport-security: max-age=31536000; includeSubDomains"
  "x-content-type-options: nosniff"
  "referrer-policy: strict-origin-when-cross-origin"
  "permissions-policy: camera=(), microphone=(), geolocation=()"
  "x-frame-options: DENY"
  "content-security-policy-report-only: "
)
status=0
for path in /sign-in /healthz; do
  headers="$(curl -sS -I "$base$path" | tr -d '\r' | tr 'A-Z' 'a-z')"
  for want in "${required[@]}"; do
    needle="$(echo "$want" | tr 'A-Z' 'a-z')"
    if ! grep -qF "$needle" <<<"$headers"; then
      echo "MISSING on $path: $want"
      status=1
    fi
  done
  if grep -q "^content-security-policy:" <<<"$headers"; then
    echo "ENFORCING CSP on $path: the policy must stay report-only"
    status=1
  fi
done
[ "$status" -eq 0 ] && echo "ok: all six headers on /sign-in and /healthz"
exit "$status"
