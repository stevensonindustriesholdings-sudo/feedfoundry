# Captain operating contract (repo control)

This document is the operating contract for agents and humans driving bounded sprints in FeedFoundry. It complements `AGENTS.md` and engineering rules in `.cursor/rules/`.

## Sprint discipline

- **One agent = one bounded sprint.** The sprint has a named goal, a short file list, and a clear stop line.
- **One branch per sprint.** Use `chore/…`, `feat/…`, or `fix/…` prefixes; avoid mixing unrelated work on the same branch.
- **No unrelated edits.** Doc-only sprints stay doc-only; billing sprints do not touch unrelated modules.
- **Merge discipline.** Prefer small PRs; rebase or merge per team convention; do not merge work that fails agreed checks without explicit exception.

## Forbidden or restricted areas (without an explicit sprint)

- **Billing / Stripe / wallet / credit ledger / processing-minute reserve–debit policy.** No drive-by changes; only a dedicated, approved sprint may touch these.
- **Railway mutations.** No deploy hooks, variable writes, or service changes from automation unless a sprint explicitly names that scope and the allowed services (see product rules).
- **Web scraping, fake GEO, or URL ingestion (V1).** V1 jobs begin from uploaded files only; do not add URL ingestion or deceptive location signals.
- **Secrets in repo, manifests, export bundles, or client code.** Never commit keys, tokens, or `.env` with real values.

## Provider and AI policy

- **Mock provider is the default** in local development and documented policy. Real providers are **opt-in** via explicit environment flags; default configs must not perform real provider calls in tests or CI unless a sprint explicitly approves that path.
- **Customer-facing AI output** only after **validator / governor** checks pass in the product pipeline (no raw dump to end users).
- **No browser or client-side AI keys.** Keys live server-side only; the web app must not embed provider secrets.
- **OpenAI external projects:** API keys belong in the provider console and environment configuration for deployed services—**never** in git, chat logs pasted into tickets, or screenshots. Use a dedicated OpenAI project for staging when you enable real calls; rotate if exposure is suspected. This note intentionally contains **no** key material.

### Environment examples (placeholders only — never real values)

Set in your deployment or local secret store, not in the repository:

```bash
OPENAI_API_KEY=
FF_AI_PROVIDER=mock
FF_ALLOW_REAL_AI_CALLS=false
FF_OPENAI_MODEL=gpt-5-nano
FF_AI_MAX_CALLS_PER_RUN=1
FF_AI_MAX_OUTPUT_TOKENS=1000
FF_AI_MAX_ESTIMATED_COST_USD=0.25
```

- Leave `OPENAI_API_KEY` empty locally unless you intentionally enable a real-provider canary.
- Keep `FF_ALLOW_REAL_AI_CALLS=false` until a canary sprint turns it on in a controlled environment.

### First real-provider canary (later sprint, checklist)

When explicitly approved as its own sprint:

1. Use a **tiny transcript fixture** (minimal tokens).
2. **One JSON-structured call** through the AI router with full logging (provider, model, tokens, latency, success/failure, cost estimate).
3. **Validator must pass** before any output is treated as customer-visible.
4. **No customer path** in the first canary—internal or staging-only.

## Reporting

- Use `docs/REPORT_TEMPLATE.md` for sprint reports.
- Run `scripts/sprint_report.sh` before opening a PR to capture branch, commit, and diff context (see script header for options).
- Prefer **`scripts/sprint_runner.sh`** for Sprint Runner Mode: `checkpoint` → `guard` → `tests` (API + worker pytest when `apps/api/.venv` is present) → `report`, or `all` (see script header). Use it at sprint start, before commit/push, and in the final paste-back to Captain.

## Autonomy Level 1.5 (Sprint Runner Mode)

Aligns with `AGENTS.md` — summarized here for captains and agents.

- **Batch safe local commands** when Cursor allows, instead of per-command approval spam: repo-root `cd`, `git status` / `log` / `diff`, `pytest`, `npm` lint/typecheck/build where in scope, `bash -n`, scoped `mkdir`/`chmod`, and grouped **`scripts/sprint_runner.sh all`** (includes pytest when the API venv exists) after edits and again before push.
- **Prefer the runner** over one-off micro terminal steps so checkpoint, guardrails, and report context stay consistent.

### Still STOP without explicit approval

**Push/merge to `main`**, **`git rebase`**, **`git reset`**, **`git clean`**, **`rm -rf`**, **`sudo`**, **installs**, **`curl`/`wget`**, **`ssh`**, **`docker`**, **Railway mutations**, **Stripe / billing / credit_ledger / wallet / processing-minute policy edits** (unless that is the sprint’s sole scope), **live OpenAI / real provider calls**, **migrations / destructive DB**, **secrets in git or chat**, **out-of-repo writes**, **deploy**. Fast-forward **`git pull --ff-only`** on a non-main sprint branch is OK when the sprint allows network and you need to sync.

## References

- `AGENTS.md` — product and engineering non-negotiables.
- `docs/REPORT_TEMPLATE.md` — sprint report fields.
- `docs/SPRINT_BOARD.md` — near-term sequence.
