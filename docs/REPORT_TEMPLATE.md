# Sprint report template

Copy the block below into the PR description, a sprint doc, or the agent’s final message. Remove unused rows; keep **forbidden areas** and **checks** explicit.

---

## Sprint report

**Branch name:**  
**Commit hash:**  

**Files changed:**  
- (list paths or `see git diff --stat`)

**Purpose:**  
(1–3 sentences: what this sprint was meant to accomplish.)

**Tests run:**  
(e.g. `npm run lint`, `pytest apps/api/tests/test_foo.py`, `bash -n scripts/…`, or **not run / optional** with reason.)

**Results:**  
(pass/fail/skip; link CI if applicable.)

**Forbidden areas checked:**  
- [ ] No billing / Stripe / wallet / credit_ledger / processing-minute policy edits (unless this sprint’s sole scope)  
- [ ] No Railway deploy or env mutations (unless explicitly in scope)  
- [ ] No secrets committed; no client-side provider keys  
- [ ] Provider: mock default; real calls only if sprint-approved and gated by env  

**Secret scan / key-pattern check:**  
(Command used, e.g. `rg` on changed paths for `sk-` patterns; outcome: **clean** / **N/A** / note without pasting matches.)

**Provider-call check:**  
(Confirm tests/CI did not invoke real providers unless explicitly approved for this sprint.)

**Known risks:**  

**Next recommended sprint:**  
(Reference `docs/SPRINT_BOARD.md` row if applicable.)

**Exact commands run:**  
```
(paste commands only; redact env values)
```

---
