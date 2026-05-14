"""Product-side input bundle types for product signal extraction (mock-only skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.visual_context import ProductImageRef, ProductMetadataStub


@dataclass(frozen=True)
class ProductGridContext:
    """Optional product grid / imagery context — internal refs only."""

    listing_id: str
    product_images: tuple[ProductImageRef, ...] = ()
    metadata_stub: ProductMetadataStub | None = None

    def to_input_bundle(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "product_images": [
                {
                    "product_image_id": p.product_image_id,
                    "t_ms": p.t_ms,
                    "grid_cell_index": p.grid_cell_index,
                }
                for p in self.product_images
            ],
            "metadata_stub": None
            if self.metadata_stub is None
            else {
                "sku": self.metadata_stub.sku,
                "collection_hint": self.metadata_stub.collection_hint,
            },
        }


@dataclass(frozen=True)
class ProductSignalContext:
    """Full product-signal input: grid plus optional transcript anchor for associations."""

    job_id: str
    grid: ProductGridContext
    content_anchor_ms: int = 0

    def to_input_bundle(self) -> dict[str, Any]:
        base = self.grid.to_input_bundle()
        base["job_id"] = self.job_id
        base["content_anchor_ms"] = self.content_anchor_ms
        return base
