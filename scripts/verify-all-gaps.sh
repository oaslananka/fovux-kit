#!/usr/bin/env bash
set -euo pipefail

errors=0

check_local_file() {
  local path=$1
  local gap=$2
  if [ -f "$path" ]; then
    echo "  OK $gap: $path"
  else
    echo "  MISSING $gap: $path"
    errors=$((errors + 1))
  fi
}

check_remote_file() {
  local repo=$1
  local path=$2
  local gap=$3
  if gh api "repos/$repo/contents/$path" >/dev/null 2>&1; then
    echo "  OK $repo $gap: $path"
  else
    echo "  MISSING $repo $gap: $path"
    errors=$((errors + 1))
  fi
}

check_clean_github_queue() {
  local repo=$1
  local open_prs open_issues extra_branches issues_enabled
  open_prs="$(
    gh pr list --repo "$repo" --state open --limit 100 --json headRefName \
      --jq '[.[] | select(.headRefName != "release-please--branches--main")] | length'
  )"
  issues_enabled="$(gh repo view "$repo" --json hasIssuesEnabled --jq '.hasIssuesEnabled')"
  if [ "$issues_enabled" = "true" ]; then
    open_issues="$(gh issue list --repo "$repo" --state open --limit 100 --json number --jq 'length')"
  else
    open_issues="0"
  fi
  extra_branches="$(
    gh api "repos/$repo/branches" --paginate --jq '.[].name' \
      | awk '$0 != "main" && $0 != "gh-pages" && $0 != "release-please--branches--main" { count++ } END { print count + 0 }'
  )"

  if [ "$open_prs" = "0" ] && [ "$open_issues" = "0" ] && [ "$extra_branches" = "0" ]; then
    echo "  OK $repo queue: no stale PRs, open issues, or extra branches"
  else
    echo "  DIRTY $repo queue: PRs=$open_prs issues=$open_issues extra_branches=$extra_branches"
    errors=$((errors + 1))
  fi
}

required_common=(
  ".editorconfig:GAP-FV-01"
  "renovate.json:GAP-FV-02"
  ".github/ISSUE_TEMPLATE/bug_report.yml:GAP-FV-04"
  ".github/ISSUE_TEMPLATE/feature_request.yml:GAP-FV-04"
  ".github/PULL_REQUEST_TEMPLATE.md:GAP-FV-05"
  ".github/labels.yml:GAP-FV-06"
  ".github/labeler.yml:GAP-FV-06"
  ".github/rulesets/main.json:GAP-FV-07"
  ".github/rulesets/release-tags.json:GAP-FV-07"
  ".github/workflows/review-thread-gate.yml:GAP-FV-08"
  ".github/workflows/stale.yml:GAP-FV-09"
  ".github/workflows/lock.yml:GAP-FV-10"
  "mcp.json:GAP-FV-13"
  "docs/testing.md:GAP-FV-14"
  "docs/release.md:GAP-FV-15"
  ".github/workflows/pr-size.yml:GAP-FV-18"
)

echo "=== Local workspace ==="
for item in "${required_common[@]}"; do
  check_local_file "${item%%:*}" "${item##*:}"
done

if command -v gh >/dev/null 2>&1; then
  echo ""
  echo "=== oaslananka/fovux-kit ==="
  for item in "${required_common[@]}"; do
    check_remote_file "oaslananka/fovux-kit" "${item%%:*}" "${item##*:}"
  done
  check_clean_github_queue "oaslananka/fovux-kit"
fi

echo ""
if [ "$errors" -eq 0 ]; then
  echo "ALL GAPS RESOLVED - REPO FULLY COMPLIANT"
else
  echo "$errors gap(s) still open"
  exit 1
fi
