# Near-term sprint sequence

Ordered backlog for focused sprints. Reorder only with explicit product/engineering agreement.

- **Governance:** **Captain Autonomy Rules v1.5** and **Sprint Runner Mode** (`docs/CAPTAIN_RULES.md`, `bash scripts/sprint_runner.sh all`).

| # | Sprint | Notes |
|---|--------|--------|
| 1 | **Repo control pack** | Captain rules, report template, PR checklist, `sprint_report.sh`, `AGENTS.md` pointers; no billing/Railway/provider mutations. |
| 2 | **OpenAI canary guardrails** | **Done (7C-7):** `docs/phase7-openai-canary.md`, `AI_STRUCTURED_PROVIDER_MODE`, API `AICanaryGateConfig`, worker registry + adapter shell; mock default; CI/tests stay mock-only. |
| 3 | **Tiny real OpenAI canary** | Staging-only, minimal fixture, one JSON call, usage logged, validator required; no customer path. |
| 4 | **Worker orchestration integration** | Job pipeline wiring per MVP contract; respect credit controls; no policy drift in ledger. |
| 5 | **Admin / customer visibility** | Dashboards and status surfaces; still no secrets in client; align with annual access + credits language. |
| 6 | **Private beta hardening** | Reliability, observability, runbooks; scoped fixes only. |

See `docs/CAPTAIN_RULES.md` for merge discipline and forbidden areas.

- **Sprint Runner Mode:** where possible, use `bash scripts/sprint_runner.sh all` (checkpoint + guard + full API/worker pytest when `apps/api/.venv` exists + report) at sprint boundaries instead of ad-hoc shell steps; pair with `docs/REPORT_TEMPLATE.md` for the Captain paste-back.

### Phase 7 parallel worktrees (agent lanes)

Lane worktrees typically live at `~/Documents/feedfoundry-agent-{a,b,c,d,e,f}-p7`. Inspect with `git worktree list`. **Do not** `git worktree add` onto an existing directory; remove or reuse the path intentionally. When a lane is retired, prefer `git worktree remove <path>` (with a clean working tree) over deleting folders by hand, so git metadata stays consistent.
