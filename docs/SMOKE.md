# FeedFoundry — copy-paste smoke

Run from repo root unless noted.

```bash
cd apps/web && npm run typecheck
```

```bash
cd apps/api && python3 -m pytest tests/test_ai_router.py -q
```

**Note:** `test_ai_router.py` must be run with `apps/api` as the current working directory so package imports resolve.

Stripe/Railway/billing are out of scope for this smoke block; OpenRouter remains **off by default** (`FF_AI_OPENROUTER_ENABLED` unset or `0` in `.env.example`).
