"""Strict schemas for Trenderly Hyperframes 10-20s POD haul ad planning."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)


class VideoAspect(str, Enum):
    VERTICAL_9_16 = "9:16"


class ProductType(str, Enum):
    TSHIRT = "tshirt"
    HOODIE = "hoodie"
    MUG = "mug"
    CUP = "cup"
    STICKER = "sticker"
    TOTE = "tote"


class TrendEvidenceIn(StrictModel):
    source_id: str = "operator_seed"
    url: str | None = None
    observed_at: str | None = None
    confidence_0_1: float = Field(default=0.5, ge=0.0, le=1.0)


class PodHaulProductIn(StrictModel):
    product_type: ProductType
    title: str
    slogan: str
    colorway: str = "black/cream"
    mockup_uri: str | None = None


class TrenderlyHyperframesAdInput(StrictModel):
    trend_id: str
    trend_name: str
    buyer_persona: str
    trend_mechanic: str = "identity phrase"
    primary_platform: str = "cross_platform"
    evidence: list[TrendEvidenceIn] = Field(default_factory=list)
    products: list[PodHaulProductIn] = Field(default_factory=list)
    legal_terms_to_avoid: list[str] = Field(default_factory=list)
    duration_seconds: int = Field(default=15, ge=10, le=20)
    aspect_ratio: VideoAspect = VideoAspect.VERTICAL_9_16
    brand_lane: Literal["trenderly_pod_haul"] = "trenderly_pod_haul"


class AgentRunMeta(StrictModel):
    schema_version: str = "0.1"
    execution_mode: Literal["deterministic_mock"] = "deterministic_mock"
    agents_scheduled: list[str] = Field(default_factory=list)


class TrendBriefOutput(StrictModel):
    agent_id: Literal["trend_brief_agent"] = "trend_brief_agent"
    schema_version: str = "0.1"
    safe_trend_label: str
    hook_line: str
    proof_line: str
    buyer_line: str
    blocked_terms: list[str] = Field(default_factory=list)


class TrendLogoSpecOutput(StrictModel):
    agent_id: Literal["trend_logo_agent"] = "trend_logo_agent"
    schema_version: str = "0.1"
    logo_text: str
    badge_text: str
    palette: list[str]
    svg: str
    alpha_layers: list[str] = Field(default_factory=list)


class StoryboardShot(StrictModel):
    shot_id: str
    start_seconds: float
    end_seconds: float
    purpose: Literal["hook", "proof", "product", "cta"]
    on_screen_text: str
    product_title: str | None = None
    motion_hint: str


class PodHaulStoryboardOutput(StrictModel):
    agent_id: Literal["pod_haul_storyboard_agent"] = "pod_haul_storyboard_agent"
    schema_version: str = "0.1"
    template_id: Literal[
        "trend_alert_short_hf_v1",
        "product_reveal_short_hf_v1",
        "three_frame_hook_proof_product_hf_v1",
    ]
    duration_seconds: int
    shots: list[StoryboardShot]


class GfxLayer(StrictModel):
    layer_id: str
    kind: Literal["svg", "alpha_mask"]
    role: Literal["logo", "lower_third", "price_pill", "cta", "wipe", "background"]
    start_seconds: float
    end_seconds: float
    svg: str
    alpha: float = Field(default=1.0, ge=0.0, le=1.0)


class GfxLayerPackOutput(StrictModel):
    agent_id: Literal["gfx_layer_agent"] = "gfx_layer_agent"
    schema_version: str = "0.1"
    canvas_width: int = 1080
    canvas_height: int = 1920
    layers: list[GfxLayer]


class SafetyOutput(StrictModel):
    agent_id: Literal["video_safety_agent"] = "video_safety_agent"
    schema_version: str = "0.1"
    passed: bool
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HyperframesAsset(StrictModel):
    asset_id: str
    kind: Literal["svg", "image", "video", "json"]
    role: str
    inline_svg: str | None = None
    uri: str | None = None


class HyperframesRenderRequest(StrictModel):
    schema_uri: Literal["stevenson.video.hyperframes.request/v1"] = Field(
        default="stevenson.video.hyperframes.request/v1",
        alias="schema",
    )
    template_id: str
    job_id: str
    render_mode: Literal["draft_preview", "operator_approved"] = "draft_preview"
    duration_seconds: int
    fps: int = 30
    width: int = 1080
    height: int = 1920
    timeline: list[StoryboardShot]
    assets: list[HyperframesAsset]
    budget: dict[str, int | str]
    provider_routing: dict[str, str]


class HyperframesPlanOutput(StrictModel):
    agent_id: Literal["hyperframes_manifest_agent"] = "hyperframes_manifest_agent"
    schema_version: str = "0.1"
    request: HyperframesRenderRequest
    deterministic_export_slot: str
    live_provider_call_allowed: Literal[False] = False


class TrenderlyHyperframesAdOutput(StrictModel):
    run: AgentRunMeta
    trend_brief: TrendBriefOutput
    trend_logo: TrendLogoSpecOutput
    storyboard: PodHaulStoryboardOutput
    gfx_layers: GfxLayerPackOutput
    hyperframes_plan: HyperframesPlanOutput
    safety: SafetyOutput
