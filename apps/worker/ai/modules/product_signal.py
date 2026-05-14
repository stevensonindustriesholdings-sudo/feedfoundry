"""Product signal extraction: product context → mock provider → ``OutputValidator``.

Guardrails
----------
**No invented prices, availability, definitive product titles, or external URLs.**
Schema uses ``ProductCommerceClaimStatus`` (``unknown`` / ``deferred`` /
``low_confidence``) instead of numeric price or URL fields. The mock provider only
emits ``DEFERRED`` or ``UNKNOWN`` for commerce-adjacent slots and never adds URL
strings or currency amounts to the JSON.
"""

from __future__ import annotations

from typing import Any

from ai.modules.output_validator import OutputValidator, ValidationResult, ValidationStatus
from ai.product_context import ProductSignalContext
from ai.provider import AIProvider
from ai.registry import get_structured_ai_provider
from ai.schemas.output_contracts import PRODUCT_SIGNAL_REPORT_SCHEMA_NAME, PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION
from ai.types import AICompletionRequest

STAGE_NAME = "product_signal"


class ProductSignalValidationError(RuntimeError):
    """Raised when mock JSON fails ``OutputValidator`` for ``ProductSignalReport``."""


def describe() -> str:
    return "Product signal: grounded visual hints with explicit deferred/unknown commerce fields."


def run_product_signal(
    ctx: ProductSignalContext,
    *,
    job_id: str,
    provider: AIProvider | None = None,
    validator: OutputValidator | None = None,
    prompt_version: str = "p7-product-signal-1",
    model: str = "mock",
) -> tuple[ValidationResult, dict[str, Any]]:
    """Build request, complete via provider, validate ``ProductSignalReport``."""
    prov = provider or get_structured_ai_provider()
    val = validator or OutputValidator()
    bundle = dict(ctx.to_input_bundle())
    req = AICompletionRequest(
        stage_name=STAGE_NAME,
        schema_name=PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
        schema_version=PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
        prompt_version=prompt_version,
        model=model,
        input_bundle=bundle,
        max_tokens=768,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id=f"{job_id}:product_signal",
    )
    parsed: dict[str, Any] = prov.complete(req).parsed_json
    vres = val.validate_payload(
        schema_name=PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
        schema_version=PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
        payload=parsed,
    )
    if vres.status != ValidationStatus.ACCEPTED:
        raise ProductSignalValidationError(f"status={vres.status} errors={vres.errors}")
    return vres, parsed
