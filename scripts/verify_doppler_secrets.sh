#!/usr/bin/env bash
set -euo pipefail
: "${DOPPLER_PROJECT:=all}"
: "${DOPPLER_CONFIG:=main}"

if [ ! -f ".doppler/secrets.txt" ]; then
  echo ".doppler/secrets.txt not found." >&2; exit 1
fi

if [ -z "${DOPPLER_TOKEN:-}" ]; then
  echo "DOPPLER_TOKEN is not set." >&2
  exit 1
fi

if ! command -v doppler >/dev/null 2>&1; then
  echo "doppler CLI is not installed or not on PATH. Install the CLI before release verification." >&2
  exit 1
fi

missing=()
while IFS= read -r line; do
  case "$line" in ""|\#*) continue ;; esac
  if ! doppler secrets get "$line" --plain \
       --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" >/dev/null 2>&1; then
    missing+=("$line")
  fi
done < .doppler/secrets.txt

if [ "${#missing[@]}" -gt 0 ]; then
  printf 'Missing Doppler secrets in %s/%s:\n' "$DOPPLER_PROJECT" "$DOPPLER_CONFIG" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi
echo "All Doppler secrets are present in ${DOPPLER_PROJECT}/${DOPPLER_CONFIG}."
