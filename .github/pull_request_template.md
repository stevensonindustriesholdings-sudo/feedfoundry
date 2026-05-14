## Summary

<!-- What does this PR change and why? Link an issue or sprint doc if applicable. -->

## Checklist

- [ ] **Scope bounded** — matches a single sprint or fix; no unrelated edits bundled in.
- [ ] **No secrets** — no API keys, tokens, or real `.env` values; no pasted credentials in description or commits.
- [ ] **No billing / Railway drift** — no incidental changes to Stripe, wallet, credit ledger, processing-minute reserve/debit policy, or Railway deploy/config unless this PR is explicitly that sprint.
- [ ] **Provider policy** — mock provider remains the default in docs and local policy; real provider only behind explicit env flags; tests/CI do not call real providers unless this sprint is explicitly approved for that.
- [ ] **Tests** — added or updated tests where behavior changed; or N/A with justification.
- [ ] **Sprint report** — if this work used `docs/REPORT_TEMPLATE.md`, link or paste the filled report in the PR body.

## Reviewer notes

<!-- Optional: risk areas, follow-ups, or deployment notes (no secrets). -->
