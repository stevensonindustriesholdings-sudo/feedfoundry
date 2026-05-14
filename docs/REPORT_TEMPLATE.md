# Sprint report template

**Paste this block back to Captain** (PR body, sprint doc, or agent final message). Trim unused lines; keep forbidden-area and check lines honest.

---

## Optional quick checklist (delete after tick)

- [ ] Sprint branch (not `main` / `master`)
- [ ] `bash scripts/sprint_runner.sh all` → exit 0
- [ ] No secrets / no forbidden-area drift (see sections below)

---

## Sprint report

**Branch name:**  
**Commit hash:**  

**Files changed:**  
- (paths or “see `git diff --stat` / runner checkpoint output”)

**Purpose:**  
(1–3 sentences.)

**Tests run:**  
(e.g. `pytest …`, `npm run lint`, `bash scripts/sprint_runner.sh all`, or **skipped — doc-only** with reason.)

**Results:**  
(pass / fail / skip; CI link if any.)

**Forbidden areas checked:**  
- [ ] No billing / Stripe / wallet / credit_ledger / processing-minute policy edits (unless this sprint’s sole scope)  
- [ ] No Railway deploy or env mutations (unless explicitly in scope)  
- [ ] No secrets; no client-side provider keys  
- [ ] Provider: mock default; real calls only if sprint-approved and env-gated  

**Secret / key-pattern check:**  
(tool: e.g. `scripts/sprint_runner.sh guard` or `rg` on changed paths; outcome: **clean** / **N/A** — do not paste matches.)

**Provider-call check:**  
(Tests/CI did not hit real providers unless this sprint explicitly approved that.)

**Known risks:**  

**Next recommended sprint:**  
(see `docs/SPRINT_BOARD.md`.)

**Commands run (redact secrets):**  
```
(paste only; use runner where possible)
```

---
