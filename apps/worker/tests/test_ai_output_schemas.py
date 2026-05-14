from __future__ import annotations

import pytest

from ai.modules.output_validator import OutputValidator, ValidationStatus
from ai.schemas.output_contracts import (
    CHAPTERS_SCHEMA_NAME,
    CHAPTERS_SCHEMA_VERSION,
    CTA_SCHEMA_NAME,
    CTA_SCHEMA_VERSION,
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    FAQ_SCHEMA_NAME,
    FAQ_SCHEMA_VERSION,
    HOSTED_MANIFEST_ENRICHMENT_SCHEMA_NAME,
    HOSTED_MANIFEST_ENRICHMENT_SCHEMA_VERSION,
    METADATA_SCHEMA_NAME,
    METADATA_SCHEMA_VERSION,
    OUTPUT_QUALITY_REPORT_SCHEMA_NAME,
    OUTPUT_QUALITY_REPORT_SCHEMA_VERSION,
    PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
    PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
    VERIFICATION_REPORT_SCHEMA_NAME,
    VERIFICATION_REPORT_SCHEMA_VERSION,
    VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
    VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
    VerificationOverallStatus,
)


def test_schema_registry_covers_all_named_contracts():
    keys = set(SCHEMA_REGISTRY.keys())
    assert (FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION) in keys
    assert (METADATA_SCHEMA_NAME, METADATA_SCHEMA_VERSION) in keys
    assert (CHAPTERS_SCHEMA_NAME, CHAPTERS_SCHEMA_VERSION) in keys
    assert (VERIFICATION_REPORT_SCHEMA_NAME, VERIFICATION_REPORT_SCHEMA_VERSION) in keys
    assert (VISUAL_ANALYSIS_REPORT_SCHEMA_NAME, VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION) in keys
    assert (PRODUCT_SIGNAL_REPORT_SCHEMA_NAME, PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION) in keys
    assert (OUTPUT_QUALITY_REPORT_SCHEMA_NAME, OUTPUT_QUALITY_REPORT_SCHEMA_VERSION) in keys


def test_output_validator_accepts_factsheet():
    validator = OutputValidator()
    payload = {"title": "T", "summary": "S", "key_facts": ["a"]}
    res = validator.validate_payload(
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        payload=payload,
    )
    assert res.status == ValidationStatus.ACCEPTED
    assert res.model is not None
    assert res.model.title == "T"


def test_output_validator_rejects_unknown_schema():
    validator = OutputValidator()
    res = validator.validate_payload(schema_name="unknown", schema_version="0.0.0", payload={})
    assert res.status == ValidationStatus.UNKNOWN_SCHEMA


def test_output_validator_rejects_invalid_payload():
    validator = OutputValidator()
    res = validator.validate_payload(
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        payload={"title": "only-title"},
    )
    assert res.status == ValidationStatus.REJECTED
    assert res.errors


def test_output_validator_rejects_extra_fields():
    validator = OutputValidator()
    res = validator.validate_payload(
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        payload={"title": "T", "summary": "S", "unexpected": 1},
    )
    assert res.status == ValidationStatus.REJECTED


@pytest.mark.parametrize(
    "schema_name,schema_version,payload",
    [
        (
            CHAPTERS_SCHEMA_NAME,
            CHAPTERS_SCHEMA_VERSION,
            {"chapters": [{"title": "Intro", "start_ms": 0}]},
        ),
        (
            METADATA_SCHEMA_NAME,
            METADATA_SCHEMA_VERSION,
            {"episode_title": "Ep1"},
        ),
        (
            VERIFICATION_REPORT_SCHEMA_NAME,
            VERIFICATION_REPORT_SCHEMA_VERSION,
            {
                "claims": [{"text": "x", "supported": True}],
                "overall_status": VerificationOverallStatus.PASS.value,
            },
        ),
        (
            VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
            VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
            {"scenes": [{"label": "A", "start_ms": 0, "end_ms": 100}]},
        ),
        (
            PRODUCT_SIGNAL_REPORT_SCHEMA_NAME,
            PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION,
            {"signals": [{"label": "deal", "confidence": 0.4}]},
        ),
        (
            OUTPUT_QUALITY_REPORT_SCHEMA_NAME,
            OUTPUT_QUALITY_REPORT_SCHEMA_VERSION,
            {"score": 0.8, "issues": []},
        ),
        (
            FAQ_SCHEMA_NAME,
            FAQ_SCHEMA_VERSION,
            {"items": [{"question": "Q?", "answer": "A."}]},
        ),
        (
            CTA_SCHEMA_NAME,
            CTA_SCHEMA_VERSION,
            {"ctas": [{"text": "Subscribe", "placement": "outro"}]},
        ),
        (
            HOSTED_MANIFEST_ENRICHMENT_SCHEMA_NAME,
            HOSTED_MANIFEST_ENRICHMENT_SCHEMA_VERSION,
            {"manifest_version": "1", "supplements": {"notes": "x"}},
        ),
    ],
)
def test_output_validator_accepts_core_contracts(schema_name: str, schema_version: str, payload: dict):
    validator = OutputValidator()
    res = validator.validate_payload(schema_name=schema_name, schema_version=schema_version, payload=payload)
    assert res.status == ValidationStatus.ACCEPTED


def test_validate_bundle_roundtrip():
    validator = OutputValidator()
    bundle = [
        {
            "schema_name": FACTSHEET_SCHEMA_NAME,
            "schema_version": FACTSHEET_SCHEMA_VERSION,
            "payload": {"title": "T", "summary": "S"},
        },
        {
            "schema_name": METADATA_SCHEMA_NAME,
            "schema_version": METADATA_SCHEMA_VERSION,
            "payload": {"episode_title": "E"},
        },
    ]
    results = validator.validate_bundle(bundle)
    assert [r.status for r in results] == [ValidationStatus.ACCEPTED, ValidationStatus.ACCEPTED]
