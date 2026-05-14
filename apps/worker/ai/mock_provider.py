"""Deterministic mock provider for CI and local development (no network)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Mapping

from ai.provider import AIProvider
from ai.schemas.output_contracts import (
    CHAPTERS_SCHEMA_NAME,
    CHAPTERS_SCHEMA_VERSION,
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    P7_CANARY_LIVE_SCHEMA_NAME,
    P7_CANARY_LIVE_SCHEMA_VERSION,
    FAQ_SCHEMA_NAME,
    FAQ_SCHEMA_VERSION,
    METADATA_SCHEMA_NAME,
    METADATA_SCHEMA_VERSION,
    PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
    PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
    VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
    VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
)
from ai.types import AICompletionRequest, AICompletionResponse


def _bundle_slice(input_bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in input_bundle.items()}


def _deterministic_registry_payload(request: AICompletionRequest) -> dict[str, Any] | None:
    """If *request* targets a registered output contract, return a valid payload dict."""
    key = (request.schema_name, request.schema_version)
    if key not in SCHEMA_REGISTRY:
        return None

    ib = _bundle_slice(request.input_bundle)
    chunk_index = int(ib.get("chunk_index", 0))
    text = str(ib.get("transcript_text", ""))
    summary = text[:500] if text else "No transcript text for this chunk."
    segment_id = ib.get("segment_id")
    start_ms_raw = ib.get("start_ms")
    start_ms = int(start_ms_raw) if start_ms_raw is not None else chunk_index * 60_000

    if key in (
        (FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION),
        (P7_CANARY_LIVE_SCHEMA_NAME, P7_CANARY_LIVE_SCHEMA_VERSION),
    ):
        title = f"Transcript intelligence facts (chunk {chunk_index})"
        if segment_id is not None:
            title = f"{title} seg={segment_id}"
        key_facts: list[str] = []
        if text.strip():
            toks = text.split()[:5]
            if toks:
                key_facts.append(" ".join(toks) + " …")
        return {"title": title, "summary": summary, "key_facts": key_facts}

    if key == (FAQ_SCHEMA_NAME, FAQ_SCHEMA_VERSION):
        return {
            "items": [
                {
                    "question": f"What is discussed in transcript chunk {chunk_index}?",
                    "answer": summary,
                }
            ]
        }

    if key == (CHAPTERS_SCHEMA_NAME, CHAPTERS_SCHEMA_VERSION):
        return {"chapters": [{"title": f"Chunk {chunk_index}", "start_ms": max(0, start_ms)}]}

    if key == (METADATA_SCHEMA_NAME, METADATA_SCHEMA_VERSION):
        ep = str(ib.get("episode_title") or f"Episode (chunk {chunk_index})")
        tags = [f"chunk:{chunk_index}"]
        if segment_id is not None:
            tags.append(f"segment:{segment_id}")
        return {"episode_title": ep, "speakers": [], "tags": tags}

    if key == (VISUAL_ANALYSIS_REPORT_SCHEMA_NAME, VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION):
        sc = ib.get("scene_fallback")
        if not isinstance(sc, dict) or not {"label", "start_ms", "end_ms"}.issubset(sc.keys()):
            sc = {"label": "Synthetic scene (mock)", "start_ms": 0, "end_ms": 1}
        scenes = [
            {
                "label": str(sc["label"]),
                "start_ms": int(sc["start_ms"]),
                "end_ms": int(sc["end_ms"]),
            }
        ]
        episode = str(ib.get("episode_id") or "episode")
        dominant_colors = ["#222222", "#444444"] if len(episode) % 2 == 0 else ["#333333", "#555555"]
        keyframe_summaries: list[dict[str, Any]] = []
        kfs = ib.get("keyframes")
        if isinstance(kfs, list):
            for row in kfs:
                if not isinstance(row, dict):
                    continue
                fid = str(row.get("frame_id", "frame-unknown"))
                t_ms = int(row.get("t_ms", 0))
                keyframe_summaries.append(
                    {
                        "frame_id": fid,
                        "t_ms": t_ms,
                        "summary": f"Keyframe {fid} at {t_ms}ms (mock)",
                        "confidence": 0.35,
                    }
                )
        ocr_items: list[dict[str, Any]] = []
        ocr_snips = ib.get("ocr_snippets")
        if isinstance(ocr_snips, list):
            for row in ocr_snips:
                if not isinstance(row, dict):
                    continue
                oid = str(row.get("ocr_source_id", "ocr-unknown"))
                t_ms = int(row.get("t_ms", 0))
                text = str(row.get("text", ""))[:200]
                ocr_items.append(
                    {
                        "ocr_source_id": oid,
                        "t_ms": t_ms,
                        "text_snippet": text,
                        "confidence": 0.4,
                    }
                )
        visual_evidence: list[dict[str, Any]] = []
        for ks in keyframe_summaries:
            visual_evidence.append(
                {
                    "frame_id": ks["frame_id"],
                    "t_ms": ks["t_ms"],
                    "description": ks["summary"],
                    "ocr_source_id": None,
                    "product_image_id": None,
                }
            )
        pimgs = ib.get("product_images")
        if isinstance(pimgs, list):
            for row in pimgs:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("product_image_id", "prodimg-unknown"))
                t_raw = row.get("t_ms")
                t_ms = int(t_raw) if t_raw is not None else 0
                visual_evidence.append(
                    {
                        "frame_id": f"frame-for-{pid}",
                        "t_ms": t_ms,
                        "description": f"Product still {pid} (mock)",
                        "ocr_source_id": None,
                        "product_image_id": pid,
                    }
                )
        mismatch_flags: list[dict[str, Any]] = []
        if not keyframe_summaries:
            mismatch_flags.append(
                {
                    "code": "no_keyframes",
                    "detail": "No keyframe refs supplied to mock visual analysis.",
                    "severity": "low",
                }
            )
        return {
            "scenes": scenes,
            "dominant_colors": dominant_colors,
            "keyframe_summaries": keyframe_summaries,
            "ocr_items": ocr_items,
            "visual_evidence": visual_evidence,
            "mismatch_flags": mismatch_flags,
        }

    if key == (PRODUCT_SIGNAL_REPORT_SCHEMA_NAME, PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION):
        imgs = ib.get("product_images")
        item_candidates: list[dict[str, Any]] = []
        product_visual_evidence: list[dict[str, Any]] = []
        if isinstance(imgs, list):
            for idx, row in enumerate(imgs):
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("product_image_id", f"product-{idx}"))
                t_raw = row.get("t_ms")
                t_ms = int(t_raw) if t_raw is not None else None
                cid = f"cand-{pid}"
                item_candidates.append(
                    {
                        "candidate_id": cid,
                        "name_stub": f"stub-{pid}",
                        "title_claim_status": "unknown",
                        "price_status": "unknown",
                        "availability_status": "unknown",
                        "external_link_status": "deferred",
                    }
                )
                product_visual_evidence.append(
                    {
                        "product_image_id": pid,
                        "frame_id": None,
                        "t_ms": t_ms,
                        "notes": "mock visual grounding only",
                    }
                )
        anchor = int(ib.get("content_anchor_ms", 0))
        associations: list[dict[str, Any]] = []
        if item_candidates:
            associations.append(
                {
                    "association_id": "assoc-0",
                    "candidate_id": item_candidates[0]["candidate_id"],
                    "content_anchor_ms": max(0, anchor),
                    "confidence": 0.25,
                }
            )
        return {
            "signals": [{"label": "product_grid_presence", "confidence": 0.2}],
            "item_candidates": item_candidates,
            "product_visual_evidence": product_visual_evidence,
            "associations": associations,
            "grid_quality": {"score": 0.55, "issues": []},
        }

    # Other registered schemas are not emitted by this mock slice; fall back to echo stub.
    return None


class MockAIProvider(AIProvider):
    """Returns stable JSON payloads derived from ``stage_name`` / ``schema_name`` only."""

    name = "mock"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        t0 = time.perf_counter()
        contract = _deterministic_registry_payload(request)
        if contract is not None:
            payload: dict[str, Any] = contract
        else:
            payload = {
                "schema_version": request.schema_version,
                "stage": request.stage_name,
                "schema": request.schema_name,
                "echo_keys": sorted(str(k) for k in request.input_bundle.keys()),
                "provider": self.name,
                "trace_id": request.trace_id,
            }
        raw = json.dumps(payload, sort_keys=True)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return AICompletionResponse(
            parsed_json=payload,
            raw_text=raw,
            input_tokens=1,
            output_tokens=len(raw) // 4,
            cost_estimate=0.0,
            latency_ms=max(latency_ms, 0),
            provider_request_id=f"mock-{uuid.uuid4()}",
            finish_reason="stop",
            provider_name=self.name,
            retry_count=0,
            raw_response_meta={"mock": True},
        )


def deterministic_stub_bundle(stage: str) -> Mapping[str, Any]:
    """Tiny fixture bundle for tests (no secrets, no PII)."""
    return {"stage": stage, "note": "stub"}
