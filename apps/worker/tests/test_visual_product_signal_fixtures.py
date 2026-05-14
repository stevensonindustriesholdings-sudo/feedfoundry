"""Visual and product signal modules: fixtures, validation, provenance (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.mock_provider import MockAIProvider
from ai.modules.output_validator import OutputValidator, ValidationStatus
from ai.modules.product_signal import ProductSignalValidationError, run_product_signal
from ai.modules.visual_analysis import VisualAnalysisValidationError, run_visual_analysis
from ai.product_context import ProductGridContext, ProductSignalContext
from ai.provider import AIProvider
from ai.schemas.output_contracts import (
    PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
    PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
    VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
    VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
    ProductCommerceClaimStatus,
)
from ai.types import AICompletionRequest, AICompletionResponse
from ai.visual_context import KeyframeRef, OCRSnippetRef, ProductImageRef, VisualAnalysisContext

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_visual_analysis_roundtrip_provenance():
    ctx = VisualAnalysisContext(
        episode_id="ep-visual-1",
        keyframes=(KeyframeRef(frame_id="kf-1", t_ms=1200, thumbnail_ref="r2://thumb/kf-1"),),
        ocr_snippets=(OCRSnippetRef(ocr_source_id="ocr-a", t_ms=1300, text="SALE 50%"),),
        product_images=(ProductImageRef(product_image_id="pi-9", t_ms=1400, grid_cell_index=2),),
    )
    vres, raw = run_visual_analysis(ctx, job_id="job-v1")
    assert vres.status == ValidationStatus.ACCEPTED
    assert vres.model is not None
    m = vres.model
    assert any(e.frame_id == "kf-1" and e.t_ms == 1200 for e in m.visual_evidence)
    assert any(o.ocr_source_id == "ocr-a" for o in m.ocr_items)
    assert any(e.product_image_id == "pi-9" for e in m.visual_evidence)
    assert m.scenes


def test_product_signal_commerce_statuses_deferred_or_unknown():
    grid = ProductGridContext(
        listing_id="list-1",
        product_images=(
            ProductImageRef(product_image_id="img-a", t_ms=500, grid_cell_index=0),
            ProductImageRef(product_image_id="img-b", t_ms=None, grid_cell_index=1),
        ),
    )
    ctx = ProductSignalContext(job_id="job-p1", grid=grid, content_anchor_ms=10_000)
    vres, _raw = run_product_signal(ctx, job_id="job-p1")
    assert vres.status == ValidationStatus.ACCEPTED
    assert vres.model is not None
    for c in vres.model.item_candidates:
        assert c.price_status in (
            ProductCommerceClaimStatus.UNKNOWN,
            ProductCommerceClaimStatus.DEFERRED,
            ProductCommerceClaimStatus.LOW_CONFIDENCE,
        )
        assert c.external_link_status == ProductCommerceClaimStatus.DEFERRED


def test_visual_malformed_fixture_rejected():
    raw = (FIXTURES / "visual_analysis_malformed.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    v = OutputValidator().validate_payload(
        schema_name=VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
        schema_version=VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
        payload=payload,
    )
    assert v.status == ValidationStatus.REJECTED
    assert v.errors


def test_product_malformed_fixture_rejected_extra_price_field():
    raw = (FIXTURES / "product_signal_malformed.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    v = OutputValidator().validate_payload(
        schema_name=PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
        schema_version=PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
        payload=payload,
    )
    assert v.status == ValidationStatus.REJECTED
    assert v.errors


class _BadVisualProvider(AIProvider):
    name = "bad-visual"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if request.schema_name == VISUAL_ANALYSIS_REPORT_SCHEMA_NAME:
            bad = json.loads((FIXTURES / "visual_analysis_malformed.json").read_text())
            raw = json.dumps(bad)
            return AICompletionResponse(
                parsed_json=bad,
                raw_text=raw,
                input_tokens=1,
                output_tokens=4,
                cost_estimate=0.0,
                latency_ms=0,
                provider_request_id="bad-v-1",
                finish_reason="stop",
                provider_name=self.name,
            )
        return MockAIProvider().complete(request)


def test_visual_analysis_raises_on_malformed_provider():
    ctx = VisualAnalysisContext(episode_id="ep-x")
    with pytest.raises(VisualAnalysisValidationError):
        run_visual_analysis(ctx, job_id="job-bad-v", provider=_BadVisualProvider())


def test_unsupported_title_claim_status_rejected():
    payload = {
        "signals": [],
        "item_candidates": [
            {
                "candidate_id": "c1",
                "name_stub": "n",
                "title_claim_status": "in_stock_definitive",
                "price_status": "unknown",
                "availability_status": "unknown",
                "external_link_status": "deferred",
            }
        ],
        "product_visual_evidence": [],
        "associations": [],
        "grid_quality": None,
    }
    v = OutputValidator().validate_payload(
        schema_name=PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
        schema_version=PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
        payload=payload,
    )
    assert v.status == ValidationStatus.REJECTED
