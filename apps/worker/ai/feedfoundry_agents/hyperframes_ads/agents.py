"""Deterministic worker agents for Trenderly 10-20s POD-haul video ads."""

from __future__ import annotations

from ai.feedfoundry_agents.hyperframes_ads.schemas import (
    GfxLayer,
    GfxLayerPackOutput,
    HyperframesAsset,
    HyperframesPlanOutput,
    HyperframesRenderRequest,
    PodHaulProductIn,
    PodHaulStoryboardOutput,
    ProductType,
    SafetyOutput,
    StoryboardShot,
    TrendBriefOutput,
    TrendLogoSpecOutput,
    TrenderlyHyperframesAdInput,
)
from ai.feedfoundry_agents.hyperframes_ads.svg_utils import (
    diagonal_wipe_alpha_svg,
    lower_third_svg,
    price_pill_svg,
    safe_words,
    slugify,
    trend_badge_svg,
)

TEMPLATE_THREE_FRAME = "three_frame_hook_proof_product_hf_v1"
TEMPLATE_REVEAL = "product_reveal_short_hf_v1"
TEMPLATE_ALERT = "trend_alert_short_hf_v1"


def _default_products(job: TrenderlyHyperframesAdInput) -> list[PodHaulProductIn]:
    if job.products:
        return job.products[:4]
    safe_name = safe_words(job.trend_name, job.legal_terms_to_avoid)
    return [
        PodHaulProductIn(product_type=ProductType.TSHIRT, title=f"{safe_name} tee", slogan=f"{safe_name} era"),
        PodHaulProductIn(product_type=ProductType.HOODIE, title=f"{safe_name} hoodie", slogan=f"Officially in my {safe_name} era"),
        PodHaulProductIn(product_type=ProductType.MUG, title=f"{safe_name} desk mug", slogan=f"Powered by {safe_name}"),
    ]


def run_trend_brief_agent(job: TrenderlyHyperframesAdInput) -> TrendBriefOutput:
    safe_label = safe_words(job.trend_name, job.legal_terms_to_avoid)
    evidence_count = len(job.evidence)
    proof = f"spotted across {evidence_count} operator seed{'s' if evidence_count != 1 else ''}"
    if evidence_count == 0:
        proof = "operator-seeded trend, pending live evidence refresh"
    return TrendBriefOutput(
        safe_trend_label=safe_label,
        hook_line=f"New drop for the {safe_label} crowd",
        proof_line=proof,
        buyer_line=f"Built for {safe_words(job.buyer_persona)}",
        blocked_terms=job.legal_terms_to_avoid,
    )


def run_trend_logo_agent(job: TrenderlyHyperframesAdInput, brief: TrendBriefOutput) -> TrendLogoSpecOutput:
    logo_words = brief.safe_trend_label.split()[:3]
    logo_text = " ".join(logo_words) or "Trend Drop"
    badge_text = "POD HAUL"
    palette = ["#101018", "#fff7df", "#ff3d81", "#38f5d0"]
    svg = trend_badge_svg(logo_text=logo_text, badge_text=badge_text, palette=palette)
    return TrendLogoSpecOutput(
        logo_text=logo_text,
        badge_text=badge_text,
        palette=palette,
        svg=svg,
        alpha_layers=["diagonal_wipe_alpha", "transparent_badge_svg"],
    )


def run_pod_haul_storyboard_agent(
    job: TrenderlyHyperframesAdInput,
    brief: TrendBriefOutput,
) -> PodHaulStoryboardOutput:
    products = _default_products(job)
    duration = job.duration_seconds
    hook_end = min(3.0, duration * 0.22)
    proof_end = min(duration - 5.0, hook_end + max(3.0, duration * 0.24))
    product_end = max(proof_end + 3.0, duration - 2.4)
    primary_product = products[0]
    template = TEMPLATE_THREE_FRAME if len(products) >= 2 else TEMPLATE_REVEAL
    shots = [
        StoryboardShot(
            shot_id="hook_001",
            start_seconds=0.0,
            end_seconds=round(hook_end, 2),
            purpose="hook",
            on_screen_text=brief.hook_line,
            motion_hint="logo slam-in, 8-frame hold, neon underline sweep",
        ),
        StoryboardShot(
            shot_id="proof_001",
            start_seconds=round(hook_end, 2),
            end_seconds=round(proof_end, 2),
            purpose="proof",
            on_screen_text=f"{brief.proof_line} • {brief.buyer_line}",
            motion_hint="stack trend proof cards behind product mockups",
        ),
        StoryboardShot(
            shot_id="product_001",
            start_seconds=round(proof_end, 2),
            end_seconds=round(product_end, 2),
            purpose="product",
            on_screen_text=f"Haul pick: {primary_product.slogan}",
            product_title=primary_product.title,
            motion_hint="3-product carousel, quick push-ins, soft shadows",
        ),
        StoryboardShot(
            shot_id="cta_001",
            start_seconds=round(product_end, 2),
            end_seconds=float(duration),
            purpose="cta",
            on_screen_text="Approve the trend → generate the drop",
            motion_hint="price pill bounce, logo lockup, CTA fade",
        ),
    ]
    return PodHaulStoryboardOutput(template_id=template, duration_seconds=duration, shots=shots)


def run_gfx_layer_agent(
    job: TrenderlyHyperframesAdInput,
    brief: TrendBriefOutput,
    logo: TrendLogoSpecOutput,
    storyboard: PodHaulStoryboardOutput,
) -> GfxLayerPackOutput:
    products = _default_products(job)
    product_label = products[0].title if products else brief.safe_trend_label
    layers = [
        GfxLayer(
            layer_id="trend_logo_svg",
            kind="svg",
            role="logo",
            start_seconds=0.0,
            end_seconds=float(storyboard.duration_seconds),
            svg=logo.svg,
            alpha=0.96,
        ),
        GfxLayer(
            layer_id="hook_lower_third_svg",
            kind="svg",
            role="lower_third",
            start_seconds=0.25,
            end_seconds=storyboard.shots[1].end_seconds,
            svg=lower_third_svg(brief.hook_line, brief.buyer_line),
        ),
        GfxLayer(
            layer_id="pod_haul_price_pill_svg",
            kind="svg",
            role="price_pill",
            start_seconds=storyboard.shots[2].start_seconds,
            end_seconds=storyboard.shots[3].end_seconds,
            svg=price_pill_svg("POD HAUL"),
        ),
        GfxLayer(
            layer_id="cta_lower_third_svg",
            kind="svg",
            role="cta",
            start_seconds=storyboard.shots[3].start_seconds,
            end_seconds=storyboard.shots[3].end_seconds,
            svg=lower_third_svg("Ready for operator review", product_label),
        ),
        GfxLayer(
            layer_id="diagonal_wipe_alpha",
            kind="alpha_mask",
            role="wipe",
            start_seconds=storyboard.shots[1].start_seconds,
            end_seconds=storyboard.shots[2].start_seconds,
            svg=diagonal_wipe_alpha_svg(),
            alpha=0.72,
        ),
    ]
    return GfxLayerPackOutput(layers=layers)


def run_hyperframes_manifest_agent(
    job: TrenderlyHyperframesAdInput,
    storyboard: PodHaulStoryboardOutput,
    logo: TrendLogoSpecOutput,
    gfx_layers: GfxLayerPackOutput,
) -> HyperframesPlanOutput:
    assets = [
        HyperframesAsset(asset_id="trend_logo_svg", kind="svg", role="trend_logo", inline_svg=logo.svg),
        *[
            HyperframesAsset(
                asset_id=layer.layer_id,
                kind="svg" if layer.kind == "svg" else "json",
                role=layer.role,
                inline_svg=layer.svg,
            )
            for layer in gfx_layers.layers
        ],
    ]
    for index, product in enumerate(_default_products(job), start=1):
        if product.mockup_uri:
            assets.append(
                HyperframesAsset(
                    asset_id=f"product_mockup_{index}",
                    kind="image",
                    role=product.product_type.value,
                    uri=product.mockup_uri,
                )
            )

    request = HyperframesRenderRequest(
        template_id=storyboard.template_id,
        job_id=f"trenderly-{slugify(job.trend_id)}-hf-ad-v1",
        duration_seconds=storyboard.duration_seconds,
        timeline=storyboard.shots,
        assets=assets,
        budget={
            "estimated_render_credits": max(1, round(storyboard.duration_seconds / 5)),
            "estimated_ai_credits": 0,
            "reservation_policy": "reserve_before_live_provider_call",
        },
        provider_routing={
            "video_provider": "hyperframes_env_gated",
            "ai_provider": "feedfoundry_ai_router_only",
        },
    )
    return HyperframesPlanOutput(
        request=request,
        deterministic_export_slot=f"media/processed/{slugify(job.trend_id)}/hyperframes/",
    )


def run_video_safety_agent(
    job: TrenderlyHyperframesAdInput,
    brief: TrendBriefOutput,
    plan: HyperframesPlanOutput,
) -> SafetyOutput:
    issues: list[str] = []
    combined_text = " ".join(
        [brief.safe_trend_label, brief.hook_line, *[shot.on_screen_text for shot in plan.request.timeline]]
    ).lower()
    for term in job.legal_terms_to_avoid:
        if term and term.lower() in combined_text:
            issues.append(f"blocked term leaked into creative text: {term}")
    if plan.live_provider_call_allowed is not False:
        issues.append("live Hyperframes provider calls must remain explicit/operator-gated")
    if not (10 <= plan.request.duration_seconds <= 20):
        issues.append("Trenderly video ads must stay in the 10-20s lane")
    notes = [
        "No URL ingestion: all product/mockup assets must be uploaded or operator-provided.",
        "Budget block requires reservation before live provider call.",
        "Transparent SVG/alpha layers are inline for review; renderer may externalize them later.",
    ]
    return SafetyOutput(passed=not issues, issues=issues, notes=notes)
