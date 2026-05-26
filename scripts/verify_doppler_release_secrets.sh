#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DOPPLER_TOKEN:-}" ]; then
  echo "ERROR: DOPPLER_TOKEN is not set. Cannot verify release secrets."
  exit 1
fi

DOPPLER_PROJECT="${DOPPLER_PROJECT:-all}"
DOPPLER_CONFIG="${DOPPLER_CONFIG:-main}"

# Required secrets for release
REQUIRED_SECRETS=(
  "PYPI_TOKEN"
  "VSCE_PAT"
  "OVSX_PAT"
  "DOPPLER_GITHUB_SERVICE_TOKEN"
)

# Optional secrets
OPTIONAL_SECRETS=(
  "TEST_PYPI_TOKEN"
  "CODECOV_TOKEN"
  "NPM_TOKEN"
  "SAFETY_API_KEY"
)

echo "Verifying Doppler release secrets for project: $DOPPLER_PROJECT, config: $DOPPLER_CONFIG"

MISSING_REQUIRED=0

for secret in "${REQUIRED_SECRETS[@]}"; do
  if doppler secrets get "$secret" --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" --plain &>/dev/null; then
    echo "OK: $secret"
  else
    echo "MISSING (Required): $secret"
    MISSING_REQUIRED=1
  fi
done

for secret in "${OPTIONAL_SECRETS[@]}"; do
  if doppler secrets get "$secret" --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" --plain &>/dev/null; then
    echo "OK: $secret"
  else
    echo "MISSING (Optional): $secret"
  fi
done

if [ "$MISSING_REQUIRED" -eq 1 ]; then
  echo "ERROR: One or more required release secrets are missing from Doppler."
  exit 1
fi

echo "All required release secrets are present."
exit 0
