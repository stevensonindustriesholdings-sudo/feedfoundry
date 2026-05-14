# Near-term sprint sequence

Ordered backlog for focused sprints. Reorder only with explicit product/engineering agreement.

| # | Sprint | Notes |
|---|--------|--------|
| 1 | **Repo control pack** | Captain rules, report template, PR checklist, `sprint_report.sh`, `AGENTS.md` pointers; no billing/Railway/provider mutations. |
| 2 | **OpenAI canary guardrails** | Env flags, caps, router logging assertions; mock remains default; document CI/test policy (no real calls unless explicitly approved). |
| 3 | **Tiny real OpenAI canary** | Staging-only, minimal fixture, one JSON call, usage logged, validator required; no customer path. |
| 4 | **Worker orchestration integration** | Job pipeline wiring per MVP contract; respect credit controls; no policy drift in ledger. |
| 5 | **Admin / customer visibility** | Dashboards and status surfaces; still no secrets in client; align with annual access + credits language. |
| 6 | **Private beta hardening** | Reliability, observability, runbooks; scoped fixes only. |

See `docs/CAPTAIN_RULES.md` for merge discipline and forbidden areas.
