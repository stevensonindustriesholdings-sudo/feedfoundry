# Stevenson shared platform bridge (FeedFoundry)

This branch carries **documentation only** for how FeedFoundry aligns with Stevenson Skunk Works CEO shared packages (`@stevenson/*`). No runtime wiring is introduced here to avoid destabilizing the product spine.

## Principles

- **Uploads-only V1:** FeedFoundry does not ingest arbitrary creator URLs; Stevenson bridge docs must not imply URL ingestion shortcuts.
- **Credits + annual access language** stays canonical; do not introduce monthly SaaS framing in bridge materials.
- **AI calls** remain behind the FeedFoundry AI router with mocks/default-off live providers per existing control packs.

## CEO package map (contract layer)

| Package | FeedFoundry touchpoint (future) |
|---------|---------------------------------|
| `@stevenson/si-ai-routing` | Mock-first routing parity with internal AI router contracts. |
| `@stevenson/si-browser-ops` | Evidence/capture policy for marketing surfaces—not used for core archive ingestion. |
| `@stevenson/si-video-composition` | Hyperframes-first manifests for worker FFmpeg stages. |
| `@stevenson/si-commerce-print` | Out-of-scope for core archive engine; optional downstream export experiments. |
| `@stevenson/si-safety-editorial` | Editorial gates for published artifacts; complements job state machines. |

## Operational note

Integrations should consume CEO packages via pinned git URLs or tarball vendoring **outside** this document’s scope. This file is a **bridge index** only.
