"""Trenderly Hyperframes ad squad emits deterministic 10-20s POD haul manifests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.feedfoundry_agents.hyperframes_ads.client import HyperframesClient, HyperframesDisabledError
from ai.feedfoundry_agents.hyperframes_ads.orchestrator import run_trenderly_hyperframes_ad_squad
from ai.feedfoundry_agents.hyperframes_ads.schemas import TrenderlyHyperframesAdInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def _load_job() -> TrenderlyHyperframesAdInput:
    raw = (FIXTURE_DIR / "tiny_trenderly_hyperframes_ad.json").read_text(encoding="utf-8")
    return TrenderlyHyperframesAdInput.model_validate_json(raw)


def test_trenderly_hyperframes_ad_squad_shape_and_budget() -> None:
    output = run_trenderly_hyperframes_ad_squad(_load_job())

    assert output.run.execution_mode == "deterministic_mock"
    assert output.storyboard.duration_seconds == 15
    assert 10 <= output.hyperframes_plan.request.duration_seconds <= 20
    assert output.hyperframes_plan.request.template_id == "three_frame_hook_proof_product_hf_v1"
    assert output.hyperframes_plan.request.budget["reservation_policy"] == "reserve_before_live_provider_call"
    assert output.hyperframes_plan.live_provider_call_allowed is False
    assert output.safety.passed is True


def test_trenderly_hyperframes_ad_squad_emits_svg_and_alpha_layers() -> None:
    output = run_trenderly_hyperframes_ad_squad(_load_job())
    roles = {layer.role for layer in output.gfx_layers.layers}

    assert {"logo", "lower_third", "price_pill", "cta", "wipe"}.issubset(roles)
    assert output.trend_logo.svg.startswith("<svg")
    assert any(layer.kind == "alpha_mask" and "fill=\"white\"" in layer.svg for layer in output.gfx_layers.layers)
    assert all("TikTok" not in layer.svg for layer in output.gfx_layers.layers)


def test_hyperframes_client_is_offline_by_default() -> None:
    output = run_trenderly_hyperframes_ad_squad(_load_job())
    client = HyperframesClient()

    payload = client.build_payload(output.hyperframes_plan.request)
    assert payload["schema"] == "stevenson.video.hyperframes.request/v1"
    with pytest.raises(HyperframesDisabledError):
        client.submit_render(output.hyperframes_plan.request)
