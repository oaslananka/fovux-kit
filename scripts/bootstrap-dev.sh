#!/usr/bin/env bash
set -euo pipefail

TASK_VERSION="v3.50.0"
ACTIONLINT_VERSION="v1.7.12"
GITLEAKS_VERSION="v8.30.1"
OSV_SCANNER_VERSION="v2.3.8"
TRIVY_VERSION="v0.70.0"
PNPM_VERSION="10.34.1"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DEPS="false"
INSTALL_HOOKS="false"

mkdir -p "${HOME}/.local/bin"
export PATH="${HOME}/.local/bin:${PATH}"

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap-dev.sh [--install-deps] [--hooks]

Checks the Fovux developer toolchain and installs the Go-based helper tools
when Go is available:

  - go-task/task v3.50.0
  - actionlint v1.7.12
  - gitleaks v8.30.1
  - OSV-Scanner v2.3.8
  - Trivy v0.70.0
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

install_gitleaks() {
  local expected="${GITLEAKS_VERSION#v}"
  local installed=""
  if command -v gitleaks >/dev/null 2>&1; then
    installed="$(gitleaks version 2>/dev/null | awk '/^[0-9]+\.[0-9]+\.[0-9]+$/ {print $1; exit}')"
    if [[ "$installed" == "$expected" ]]; then
      echo "OK: gitleaks $installed -> $(command -v gitleaks)"
      return 0
    fi
    echo "Replacing Gitleaks ${installed:-unknown} with pinned ${expected}..."
  fi

  need curl
  need tar
  local os arch asset checksums archive temp_dir expected_sha actual_sha
  case "$(uname -s)" in
    Linux) os="linux" ;;
    Darwin) os="darwin" ;;
    *)
      echo "ERROR: automatic Gitleaks installation supports Linux and macOS only." >&2
      return 1
      ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64) arch="x64" ;;
    arm64|aarch64) arch="arm64" ;;
    *)
      echo "ERROR: unsupported Gitleaks architecture: $(uname -m)" >&2
      return 1
      ;;
  esac

  asset="gitleaks_${expected}_${os}_${arch}.tar.gz"
  temp_dir="$(mktemp -d)"
  checksums="${temp_dir}/gitleaks_${expected}_checksums.txt"
  archive="${temp_dir}/${asset}"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
    "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/gitleaks_${expected}_checksums.txt" \
    --output "$checksums"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
    "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/${asset}" \
    --output "$archive"
  expected_sha="$(awk -v asset="$asset" '$2 == asset {print $1}' "$checksums")"
  if [[ -z "$expected_sha" ]]; then
    echo "ERROR: no checksum found for ${asset}" >&2
    rm -rf "$temp_dir"
    return 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    actual_sha="$(sha256sum "$archive" | awk '{print $1}')"
  else
    actual_sha="$(shasum -a 256 "$archive" | awk '{print $1}')"
  fi
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "ERROR: Gitleaks checksum mismatch for ${asset}" >&2
    rm -rf "$temp_dir"
    return 1
  fi
  tar -xzf "$archive" -C "$temp_dir" gitleaks
  install -m 0755 "$temp_dir/gitleaks" "${HOME}/.local/bin/gitleaks"
  rm -rf "$temp_dir"
  hash -r
}

install_trivy() {
  local expected="${TRIVY_VERSION#v}"
  local installed=""
  if command -v trivy >/dev/null 2>&1; then
    installed="$(trivy --version 2>/dev/null | awk '/^Version:/ {print $2; exit}')"
    if [[ "$installed" == "$expected" ]]; then
      echo "OK: trivy $installed -> $(command -v trivy)"
      return 0
    fi
    echo "Replacing Trivy ${installed:-unknown} with pinned ${expected}..."
  fi

  need curl
  need tar
  local os arch asset checksums archive temp_dir expected_sha actual_sha
  case "$(uname -s)" in
    Linux) os="Linux" ;;
    Darwin) os="macOS" ;;
    *)
      echo "ERROR: automatic Trivy installation supports Linux and macOS only." >&2
      return 1
      ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64) arch="64bit" ;;
    arm64|aarch64) arch="ARM64" ;;
    *)
      echo "ERROR: unsupported Trivy architecture: $(uname -m)" >&2
      return 1
      ;;
  esac

  asset="trivy_${expected}_${os}-${arch}.tar.gz"
  temp_dir="$(mktemp -d)"
  checksums="${temp_dir}/trivy_${expected}_checksums.txt"
  archive="${temp_dir}/${asset}"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
    "https://github.com/aquasecurity/trivy/releases/download/${TRIVY_VERSION}/trivy_${expected}_checksums.txt" \
    --output "$checksums"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
    "https://github.com/aquasecurity/trivy/releases/download/${TRIVY_VERSION}/${asset}" \
    --output "$archive"
  expected_sha="$(awk -v asset="$asset" '$2 == asset {print $1}' "$checksums")"
  if [[ -z "$expected_sha" ]]; then
    echo "ERROR: no checksum found for ${asset}" >&2
    rm -rf "$temp_dir"
    return 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    actual_sha="$(sha256sum "$archive" | awk '{print $1}')"
  else
    actual_sha="$(shasum -a 256 "$archive" | awk '{print $1}')"
  fi
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "ERROR: Trivy checksum mismatch for ${asset}" >&2
    rm -rf "$temp_dir"
    return 1
  fi
  tar -xzf "$archive" -C "$temp_dir" trivy
  install -m 0755 "$temp_dir/trivy" "${HOME}/.local/bin/trivy"
  rm -rf "$temp_dir"
}

installed_go_tool_version() {
  local command_name="$1"
  case "$command_name" in
    task) task --version 2>/dev/null ;;
    actionlint) actionlint --version 2>/dev/null ;;
    osv-scanner) osv-scanner --version 2>/dev/null ;;
    *) return 1 ;;
  esac | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

install_go_tool() {
  local command_name="$1"
  local module="$2"
  local version="$3"
  local expected="${version#v}"
  local installed=""
  if command -v "$command_name" >/dev/null 2>&1; then
    installed="$(installed_go_tool_version "$command_name" || true)"
    if [[ "$installed" == "$expected" ]]; then
      echo "OK: $command_name $installed -> $(command -v "$command_name")"
      return 0
    fi
    echo "Replacing $command_name ${installed:-unknown} with pinned ${expected}..."
  fi
  need go
  echo "Installing $command_name@$version with go install..."
  go install "${module}@${version}"
  local built_binary
  built_binary="$(go env GOPATH)/bin/${command_name}"
  install -m 0755 "$built_binary" "${HOME}/.local/bin/${command_name}"
  hash -r
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
install_gitleaks
install_go_tool osv-scanner github.com/google/osv-scanner/v2/cmd/osv-scanner "$OSV_SCANNER_VERSION"
install_trivy

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
trivy --version

if [[ "$INSTALL_DEPS" == "true" ]]; then
  task install
fi

if [[ "$INSTALL_HOOKS" == "true" ]]; then
  task hooks
fi

echo "Bootstrap check complete. Run: task verify:required"
