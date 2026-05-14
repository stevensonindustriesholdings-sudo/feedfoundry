#!/usr/bin/env bash
# sprint_runner.sh — checkpoint / guard / tests / report (no network; no pip)
#
# checkpoint: current branch, "git status --short", latest commit one-liner,
#   "git log --oneline --decorate -8", and changed paths vs HEAD:
#   unstaged: git diff --name-only ; staged: git diff --cached --name-only
#
# guard: fail on branch main|master; fail if combined diff/show contains
#   sk-[a-zA-Z0-9]{20,} (OpenAI-style key material); print forbidden hints for
#   https://api DOT openai DOT com style URLs and OPENAI_API_KEY=sk-* tails;
#   warn on touched paths (unstaged/staged/untracked) if they mention
#   credit_ledger|railway|stripe.
#
# tests: if apps/api/.venv exists, import stripe + import app.main, then
#   full `python -m pytest -q` under apps/api; then worker tests with
#   PYTHONPATH=apps/api:apps/worker using the same interpreter. If venv or
#   stripe is missing, prints WARN and skips pytest (install per apps/api/requirements.txt).
#   Web (npm) checks are optional and not run here.
#
# report: runs scripts/sprint_report.sh when executable; else minimal echo.
# all: checkpoint, guard, tests, report in order.
#
# Usage: ./scripts/sprint_runner.sh checkpoint|guard|tests|report|all

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

scan_body() {
  local unst cached
  unst=$(git diff 2>/dev/null || true)
  cached=$(git diff --cached 2>/dev/null || true)
  if [[ -z "$unst" && -z "$cached" ]]; then
    git show HEAD -p --format= 2>/dev/null || true
  else
    printf '%s%s' "$unst" "$cached"
  fi
}

do_checkpoint() {
  echo "=== checkpoint ==="
  echo "Branch: $(git branch --show-current 2>/dev/null || echo '(detached)')"
  echo "Latest: $(git log -1 --oneline 2>/dev/null || echo 'n/a')"
  echo ""
  echo "--- git status --short ---"
  git status --short
  echo ""
  echo "--- git log -8 ---"
  git log -8 --oneline --decorate 2>/dev/null || true
  echo ""
  echo "--- names: unstaged vs HEAD ---"
  git diff --name-only 2>/dev/null || true
  echo "--- names: staged vs HEAD ---"
  git diff --cached --name-only 2>/dev/null || true
  echo "=== end checkpoint ==="
}

do_guard() {
  echo "=== guard ==="
  local b
  b="$(git branch --show-current 2>/dev/null || echo '')"
  if [[ "$b" == "main" || "$b" == "master" ]]; then
    echo "FAIL: refuse guard on branch $b" >&2
    exit 2
  fi
  echo "Branch OK: $b"
  echo "--- changed names (unstaged / staged) ---"
  git diff --name-only 2>/dev/null || true
  git diff --cached --name-only 2>/dev/null || true
  local body
  body="$(scan_body)"
  if echo "$body" | grep -E -q 'sk-[a-zA-Z0-9]{20,}'; then
    echo "FAIL: diff/show matched sk- key-like pattern (redacted)" >&2
    exit 3
  fi
  if echo "$body" | grep -E -q 'https://api\.openai\.com'; then
    echo "WARN: OpenAI HTTPS API host URL appears in diff/show — confirm doc-only / intentional."
  fi
  if echo "$body" | grep -E -q 'OPENAI_API_KEY=sk-[a-zA-Z0-9]{10,}'; then
    echo "WARN: suspected OpenAI sk- assignment in diff/show — remove before commit."
  fi
  echo "--- sensitive-token reminder (touched paths only: unstaged/staged/untracked) ---"
  local touched
  touched="$(
    { git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } 2>/dev/null \
      | sed '/^$/d' | sort -u
  )"
  while IFS= read -r f; do
    [[ -n "$f" && -f "$f" ]] || continue
    if command -v rg >/dev/null 2>&1; then
      rg -q -i 'credit_ledger|railway|stripe' "$f" 2>/dev/null && echo "WARN: verify sprint scope — $f matches credit_ledger|railway|stripe (informational)." || true
    elif grep -qiE 'credit_ledger|railway|stripe' "$f" 2>/dev/null; then
      echo "WARN: verify sprint scope — $f matches credit_ledger|railway|stripe (informational)."
    fi
  done < <(printf '%s\n' "$touched")
  echo "=== end guard (ok) ==="
}

api_venv_python() {
  echo "$ROOT/apps/api/.venv/bin/python"
}

do_tests() {
  echo "=== tests (api + worker) ==="
  local py
  py="$(api_venv_python)"
  if [[ ! -x "$py" ]]; then
    echo "WARN: apps/api/.venv missing — skip API/worker pytest. See apps/api/requirements.txt header for pip install."
    echo "=== end tests (skipped) ==="
    return 0
  fi
  if ! "$py" -c "import stripe" 2>/dev/null; then
    echo "WARN: stripe not importable in API venv — skip pytest. Run: (cd apps/api && .venv/bin/pip install -r requirements.txt)"
    echo "=== end tests (skipped) ==="
    return 0
  fi
  echo "--- api import smoke ---"
  (cd "$ROOT/apps/api" && "$py" -c "from app.main import app")
  echo "--- api pytest ---"
  (cd "$ROOT/apps/api" && "$py" -m pytest -q)
  echo "--- worker pytest (PYTHONPATH=api:worker) ---"
  (cd "$ROOT/apps/worker" && env PYTHONPATH="$ROOT/apps/api:$ROOT/apps/worker" "$py" -m pytest -q)
  echo "=== end tests (ok) ==="
}

do_report() {
  echo "=== report ==="
  if [[ -x "$ROOT/scripts/sprint_report.sh" ]]; then
    "$ROOT/scripts/sprint_report.sh"
  else
    echo "scripts/sprint_report.sh missing or not executable — skipping."
  fi
  echo "=== end report ==="
}

case "${1:-}" in
  checkpoint) do_checkpoint ;;
  guard) do_guard ;;
  tests) do_tests ;;
  report) do_report ;;
  all) do_checkpoint; echo ""; do_guard; echo ""; do_tests; echo ""; do_report ;;
  *)
    echo "Usage: $0 checkpoint|guard|tests|report|all" >&2
    exit 1
    ;;
esac
