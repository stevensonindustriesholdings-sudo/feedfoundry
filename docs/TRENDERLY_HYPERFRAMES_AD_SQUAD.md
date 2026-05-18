# Trenderly Hyperframes POD-haul video ad squad

Status: deterministic worker scaffold, no live Hyperframes calls.

## What landed

This branch now includes a first-pass Trenderly video-ad squad under:

- `apps/worker/ai/feedfoundry_agents/hyperframes_ads/`
- `apps/worker/tests/test_trenderly_hyperframes_ads.py`

The squad plans 10-20s vertical product videos for approved or held Trenderly trends. It is intentionally offline-first and emits a structured Hyperframes request, not a live render.

## Agent team

1. `trend_brief_agent`
   - Sanitizes trend language against legal terms to avoid.
   - Creates hook/proof/buyer lines for a short ad.

2. `trend_logo_agent`
   - Creates a transparent SVG trend badge/logo.
   - Provides alpha-layer names for video GFX reuse.

3. `pod_haul_storyboard_agent`
   - Builds a 4-shot vertical ad timeline: hook, proof, product, CTA.
   - Targets Stevenson template IDs from `vendor/stevenson-contracts/product_template_ids.v1.json`:
     - `trend_alert_short_hf_v1`
     - `product_reveal_short_hf_v1`
     - `three_frame_hook_proof_product_hf_v1`

4. `gfx_layer_agent`
   - Emits inline transparent SVG layers:
     - trend logo
     - hook lower third
     - POD haul price pill
     - CTA lower third
     - diagonal alpha wipe mask

5. `hyperframes_manifest_agent`
   - Emits `stevenson.video.hyperframes.request/v1` shaped payload.
   - Adds budget metadata requiring reservation before a live provider call.
   - Keeps live Hyperframes execution disabled by default.

6. `video_safety_agent`
   - Checks blocked legal terms do not leak into creative copy.
   - Enforces the 10-20s ad lane.
   - Notes upload/operator-provided asset constraints.

## Call boundary

`apps/worker/ai/feedfoundry_agents/hyperframes_ads/client.py` defines the env-gated client boundary:

- `HYPERFRAMES_LIVE_RENDER_ENABLED=true`
- `HYPERFRAMES_API_BASE_URL`
- `HYPERFRAMES_API_KEY`

Do not call this client until credits are estimated/reserved and operator approval is recorded. FeedFoundry and Trenderly must keep AI/provider calls behind router, budget, token, retry, and provider controls.

## Example smoke

From `apps/worker`:

```bash
python -m pytest tests/test_trenderly_hyperframes_ads.py -q
```

## Next build steps

1. Add a worker job type that stores this output as a draft preview plan under the processed job folder.
2. Map `HyperframesRenderRequest` to the Stevenson `si-video-composition` package once the package is consumed directly instead of via vendored template snapshots.
3. Add a trend-logo engine pass that can export SVGs to files for FFmpeg overlay and Hyperframes upload.
4. Add a credits ledger fixture for `reserve_before_live_provider_call` around live Hyperframes submission.
5. Add a Base44/OpenAPI endpoint for previewing the draft ad plan without exposing provider secrets.
