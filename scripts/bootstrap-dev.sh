#!/usr/bin/env bash
set -euo pipefail

TASK_VERSION="v3.50.0"
ACTIONLINT_VERSION="v1.7.12"
GITLEAKS_VERSION="v8.30.1"
OSV_SCANNER_VERSION="v2.3.8"
PNPM_VERSION="10.34.1"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DEPS="false"
INSTALL_HOOKS="false"

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap-dev.sh [--install-deps] [--hooks]

Checks the Fovux developer toolchain and installs the Go-based helper tools
when Go is available:

  - go-task/task v3.50.0
  - actionlint v1.7.12
  - gitleaks v8.30.1
  - OSV-Scanner v2.3.8
  - pnpm 10.34.1 via Corepack

Options:
  --install-deps  Run task install after the toolchain check.
  --hooks         Run task hooks after dependency installation.
  -h, --help      Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-deps) INSTALL_DEPS="true" ;;
    --hooks) INSTALL_HOOKS="true" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    return 1
  fi
}

install_go_tool() {
  local command_name="$1"
  local module="$2"
  local version="$3"
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "OK: $command_name -> $(command -v "$command_name")"
    return 0
  fi
  need go
  echo "Installing $command_name@$version with go install..."
  go install "${module}@${version}"
  export PATH="$(go env GOPATH)/bin:${PATH}"
  command -v "$command_name" >/dev/null 2>&1
}

echo "== Fovux developer bootstrap =="
cd "$ROOT"

need python3
need node
need npm
need go

if ! command -v uv >/dev/null 2>&1; then
  if command -v curl >/dev/null 2>&1; then
    echo "Installing uv with the official standalone installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  else
    echo "ERROR: uv is missing and curl is unavailable. Install uv from https://docs.astral.sh/uv/." >&2
    exit 1
  fi
fi

install_go_tool task github.com/go-task/task/v3/cmd/task "$TASK_VERSION"
install_go_tool actionlint github.com/rhysd/actionlint/cmd/actionlint "$ACTIONLINT_VERSION"
install_go_tool gitleaks github.com/zricethezav/gitleaks/v8 "$GITLEAKS_VERSION"
install_go_tool osv-scanner github.com/google/osv-scanner/v2/cmd/osv-scanner "$OSV_SCANNER_VERSION"

if command -v corepack >/dev/null 2>&1; then
  corepack enable
  corepack prepare "pnpm@${PNPM_VERSION}" --activate
else
  echo "ERROR: corepack is missing. Install Node.js >=22 with Corepack enabled." >&2
  exit 1
fi

printf '\nTool versions:\n'
python3 --version
uv --version
node --version
npm --version
pnpm --version
task --version
actionlint --version
gitleaks version
osv-scanner --version

if [[ "$INSTALL_DEPS" == "true" ]]; then
  task install
fi

if [[ "$INSTALL_HOOKS" == "true" ]]; then
  task hooks
fi

echo "Bootstrap check complete. Run: task ci"
