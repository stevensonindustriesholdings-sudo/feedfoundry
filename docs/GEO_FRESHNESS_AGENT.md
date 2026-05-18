# GEO / Freshness Agent — gated behaviour

## Purpose

Support **Generative Engine Optimization (GEO)** style freshness signals (titles, entities, “last reviewed” style metadata) **without** inventing live web facts or silently calling crawlers on the customer path.

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED` | `false` | When **not** truthy, all freshness fields come from **static seeds / fixtures** bundled with the worker tests. |

Truthy values: `1`, `true`, `yes` (case-insensitive).

## v0.1 behaviour (hard)

- **No HTTP / browser research** in worker code paths, including when the flag is true. A true value only records `live_research_requested: true` on the payload; **live fetch is explicitly unimplemented** and must be added behind a separate internal approval gate in a future version.
- **Customer path:** only static/cached outputs are returned.
- **Evidence:** fixture-based `citations` are **mock-labelled** (`source: "fixture_seed"`).

## Output sketch

```json
{
  "schema_version": "0.1",
  "mode": "static_fixture",
  "reviewed_at": "2026-05-18",
  "freshness_notes": ["Deterministic seed — not live web research."],
  "citations": [{"label": "fixture", "source": "fixture_seed"}]
}
```

## Related

- Full team roster: `docs/FEEDFOUNDRY_AGENT_STACK.md`
- Implementation: `ai/feedfoundry_agents/agents/geo_freshness.py`
