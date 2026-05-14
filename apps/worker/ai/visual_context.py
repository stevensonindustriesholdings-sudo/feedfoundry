"""Typed visual-side inputs for structured visual analysis (provenance-first, no URL ingestion)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class KeyframeRef:
    """Reference to an extracted keyframe or still frame."""

    frame_id: str
    t_ms: int
    thumbnail_ref: str | None = None  # storage key / internal ref, not a public HTTP URL


@dataclass(frozen=True)
class OCRSnippetRef:
    """OCR text anchored to a timeline position."""

    ocr_source_id: str
    t_ms: int
    text: str


@dataclass(frozen=True)
class ProductImageRef:
    """Product-tile or product still extracted from grid or b-roll."""

    product_image_id: str
    t_ms: int | None = None
    grid_cell_index: int | None = None


@dataclass(frozen=True)
class ProductMetadataStub:
    """Non-authoritative hints only — never treated as definitive catalog truth."""

    sku: str | None = None
    collection_hint: str | None = None


@dataclass(frozen=True)
class VisualAnalysisContext:
    """Bundle passed into ``visual_analysis`` — all pointers are internal/upload provenance."""

    episode_id: str
    keyframes: tuple[KeyframeRef, ...] = ()
    ocr_snippets: tuple[OCRSnippetRef, ...] = ()
    product_images: tuple[ProductImageRef, ...] = ()
    product_metadata_stub: ProductMetadataStub | None = None

    def to_input_bundle(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "keyframes": [
                {"frame_id": k.frame_id, "t_ms": k.t_ms, "thumbnail_ref": k.thumbnail_ref} for k in self.keyframes
            ],
            "ocr_snippets": [
                {"ocr_source_id": o.ocr_source_id, "t_ms": o.t_ms, "text": o.text} for o in self.ocr_snippets
            ],
            "product_images": [
                {
                    "product_image_id": p.product_image_id,
                    "t_ms": p.t_ms,
                    "grid_cell_index": p.grid_cell_index,
                }
                for p in self.product_images
            ],
            "product_metadata_stub": None
            if self.product_metadata_stub is None
            else {
                "sku": self.product_metadata_stub.sku,
                "collection_hint": self.product_metadata_stub.collection_hint,
            },
        }


def provenance_slice(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Stable subset of *bundle* for trace logging (no raw media bytes)."""
    keys = ("episode_id", "keyframes", "ocr_snippets", "product_images")
    return {k: bundle.get(k) for k in keys}
