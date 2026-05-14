"""Machine validation gate for structured AI outputs (no provider I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from ai.schemas.output_contracts import SCHEMA_REGISTRY

STAGE_NAME = "output_validator"


class ValidationStatus(str, Enum):
    """Governor-facing coarse status for validator decisions."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN_SCHEMA = "unknown_schema"
    VERSION_MISMATCH = "version_mismatch"


@dataclass
class ValidationResult:
    status: ValidationStatus
    errors: Tuple[str, ...]
    model: Optional[BaseModel] = None


class OutputValidator:
    """Validate parsed JSON against registered Pydantic contracts."""

    def __init__(self, registry: Optional[Dict[Tuple[str, str], Type[BaseModel]]] = None) -> None:
        self._registry = registry or SCHEMA_REGISTRY

    def validate_payload(
        self,
        *,
        schema_name: str,
        schema_version: str,
        payload: dict[str, Any],
    ) -> ValidationResult:
        key = (schema_name, schema_version)
        model = self._registry.get(key)
        if model is None:
            return ValidationResult(status=ValidationStatus.UNKNOWN_SCHEMA, errors=("unregistered schema",), model=None)
        try:
            parsed = model.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - exercised in tests
            errors = tuple(str(err) for err in exc.errors())
            return ValidationResult(status=ValidationStatus.REJECTED, errors=errors, model=None)
        return ValidationResult(status=ValidationStatus.ACCEPTED, errors=(), model=parsed)

    def validate_bundle(self, bundle: Iterable[dict[str, Any]]) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for item in bundle:
            results.append(
                self.validate_payload(
                    schema_name=str(item["schema_name"]),
                    schema_version=str(item["schema_version"]),
                    payload=dict(item["payload"]),
                )
            )
        return results


def describe() -> str:
    return "Output validator: Pydantic/JSON schema gate before customer-visible storage."
