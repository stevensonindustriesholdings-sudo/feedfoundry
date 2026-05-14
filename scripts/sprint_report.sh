#!/usr/bin/env bash
# sprint_report.sh — quick sprint context for PRs and REPORT_TEMPLATE.md
# Usage: ./scripts/sprint_report.sh [base-ref]
#   base-ref defaults to origin/main if present, else main, else HEAD~1

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE="${1:-}"
if [[ -z "$BASE" ]]; then
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    BASE="origin/main"
  elif git rev-parse --verify main >/dev/null 2>&1; then
    BASE="main"
  else
    BASE="HEAD~1"
  fi
fi

echo "=== FeedFoundry sprint_report ==="
echo "Date (local): $(date -u +%Y-%m-%dT%H:%MZ 2>/dev/null || date)"
echo "Branch: $(git branch --show-current 2>/dev/null || echo '(detached)')"
echo "Latest commit: $(git log -1 --oneline)"
echo "Merge-base with ${BASE}: $(git merge-base HEAD "$BASE" 2>/dev/null || echo 'n/a')"
echo ""
echo "--- git status -sb ---"
git status -sb
echo ""
echo "--- Recent commits (last 10) ---"
git log -10 --oneline --decorate
echo ""
echo "--- Diff stat vs ${BASE} ---"
if git merge-base HEAD "$BASE" >/dev/null 2>&1; then
  git diff --stat "$(git merge-base HEAD "$BASE")"..HEAD
  echo ""
  echo "--- Changed files (name-only) vs merge-base ---"
  git diff --name-only "$(git merge-base HEAD "$BASE")"..HEAD
else
  echo "(could not diff vs $BASE)"
fi
echo ""
echo "=== Reminders (fill in REPORT_TEMPLATE.md) ==="
echo "- Forbidden areas: billing/Stripe/wallet/ledger/processing-minutes; Railway mutations; secrets."
echo "- Secret/key scan (example): rg -n 'sk-[a-zA-Z0-9]{10,}' --glob '!**/node_modules/**' <paths>"
echo "- Provider: confirm mock default; real calls only if sprint-approved."
echo "- Tests: pytest / npm test as applicable (optional for doc-only sprints — state in report)."
echo "Done."
