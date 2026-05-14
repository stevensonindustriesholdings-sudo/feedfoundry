"""OpenAI canary guardrails: mock default, fail-closed canary, no live HTTP in tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from ai.canary_error_codes import CanaryFailClosedCode, CanaryRuntimeCode
from ai.canary_runner import (
    cli_main,
    manual_run_openai_canary_preflight,
    maybe_run_openai_canary_job_runner,
    openai_canary_runner_enabled,
)
from ai.provider_mode import ProviderDisabledError, StructuredProviderMode, resolve_structured_provider_mode
from ai.registry import get_structured_ai_provider
from ai.types import AICompletionRequest, AICompletionResponse
from app import models  # noqa: F401
from app.models import (
    AIRun,
    AIStageLog,
    Job,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _minimal_request() -> AICompletionRequest:
    return AICompletionRequest(
        stage_name="transcript_intelligence",
        schema_name="ai.stub.v1",
        schema_version="0.1.0",
        prompt_version="p1",
        model="gpt-4.1-mini",
        input_bundle={"hello": "world"},
        max_tokens=32,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.01,
        trace_id="job:canary:test",
    )


def _mock_client_cm(inner: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None
    return cm


def _canary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")


def test_mock_mode_even_if_canary_flags_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-be-used")
    prov = get_structured_ai_provider()
    assert prov.name == "mock"


def test_canary_without_openai_key_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.OPENAI_API_KEY_MISSING.value):
        get_structured_ai_provider()


def test_canary_canary_master_off_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "false")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.1")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.KILL_SWITCH_OFF.value):
        get_structured_ai_provider()


def test_canary_numeric_defaults_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.delenv("AI_CANARY_MAX_CALLS", raising=False)
    monkeypatch.delenv("AI_CANARY_MAX_COST", raising=False)
    monkeypatch.delenv("AI_CANARY_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.NUMERIC_CAPS_INVALID.value):
        get_structured_ai_provider()


def test_canary_ai_provider_not_openai_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.AI_PROVIDER_NOT_OPENAI.value):
        get_structured_ai_provider()


def test_canary_all_gates_complete_fail_closed_without_runner(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)
    monkeypatch.delenv("FF_OPENAI_CANARY_RUNNER_ENABLED", raising=False)
    monkeypatch.delenv("FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE", raising=False)
    prov = get_structured_ai_provider()
    assert prov.name == "openai"
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.CANARY_RUNNER_FLAG_OFF.value):
        prov.complete(_minimal_request())


def test_resolve_mode_invalid_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "production")
    with pytest.raises(ProviderDisabledError, match="Invalid AI_STRUCTURED_PROVIDER_MODE"):
        resolve_structured_provider_mode()


def test_resolve_legacy_canary_alias(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    assert resolve_structured_provider_mode() == StructuredProviderMode.CANARY_OPENAI


def test_resolve_canary_openai_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    assert resolve_structured_provider_mode() == StructuredProviderMode.CANARY_OPENAI


def test_openai_adapter_module_has_no_openai_sdk_imports():
    root = Path(__file__).resolve().parents[1] / "ai" / "openai_adapter.py"
    text = root.read_text(encoding="utf-8")
    assert "import httpx" in text
    assert "import openai" not in text
    assert "from openai" not in text


def test_get_structured_does_not_invoke_httpx(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    with patch("httpx.Client") as client_ctor:
        prov = get_structured_ai_provider()
        assert prov.name == "mock"
        client_ctor.assert_not_called()


def test_enum_values_documented():
    assert StructuredProviderMode.MOCK.value == "mock"
    assert StructuredProviderMode.CANARY_OPENAI.value == "canary_openai"
    assert StructuredProviderMode.DISABLED.value == "disabled"


def test_openai_shell_constructor_fail_closed_without_gates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    monkeypatch.setenv("AI_CANARY_ENABLED", "false")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "false")
    from ai.openai_adapter import OpenAIStructuredProviderShell

    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.KILL_SWITCH_OFF.value):
        OpenAIStructuredProviderShell()


def test_openai_shell_constructor_requires_canary_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    from ai.openai_adapter import OpenAIStructuredProviderShell

    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.STRUCTURED_MODE_NOT_CANARY.value):
        OpenAIStructuredProviderShell()


@pytest.fixture
def sqlite_engine():
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["FF_INTERNAL_API_KEY"] = "test-openai-canary"
    os.environ["AI_ROUTING_CONFIG_PATH"] = str(REPO_ROOT / "ai-routing.yaml")
    from app.settings import get_settings

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    get_settings.cache_clear()


def _seed_job(session: Session, *, org_id: str, job_id: str, ma_id: str) -> Job:
    session.add(Organisation(id=org_id, name="Canary Org", slug=f"slug-{org_id}"))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"u@{org_id}.test"))
    session.add(
        MediaAsset(
            id=ma_id,
            organisation_id=org_id,
            original_filename="f.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key=f"orgs/{org_id}/assets/{ma_id}/source/f.mp4",
            status=MediaAssetStatus.UPLOADED,
        )
    )
    job = Job(
        id=job_id,
        organisation_id=org_id,
        media_asset_id=ma_id,
        status=JobStatus.PROCESSING,
        reserved_processing_minutes=10,
        estimated_processing_minutes=10,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_runner_flag_off_no_airun(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.delenv("FF_OPENAI_CANARY_RUNNER_ENABLED", raising=False)
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)

    org_id, job_id, ma_id = "org_cr_off", "job_cr_off", "ma_cr_off"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        maybe_run_openai_canary_job_runner(session, job)
        assert session.exec(select(AIRun).where(AIRun.job_id == job_id)).all() == []


def test_runner_skipped_when_mode_mock(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    org_id, job_id, ma_id = "org_cr_mock", "job_cr_mock", "ma_cr_mock"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        maybe_run_openai_canary_job_runner(session, job)
        assert session.exec(select(AIRun).where(AIRun.job_id == job_id)).all() == []


def test_runner_persists_failed_stage_on_http_auth(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)
    org_id, job_id, ma_id = "org_cr_shell", "job_cr_shell", "ma_cr_shell"
    inner = MagicMock()
    inner.post.return_value = httpx.Response(401, json={"error": {"message": "bad"}})
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
            maybe_run_openai_canary_job_runner(session, job)
        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert runs[0].error_code == CanaryRuntimeCode.HTTP_AUTH.value
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        assert len(stages) == 1
        assert stages[0].stage_name == "openai_canary_synthetic"
        assert stages[0].error_code == CanaryRuntimeCode.HTTP_AUTH.value
        extra = stages[0].extra_json or {}
        assert "sk-" not in str(extra)
        assert "OPENAI" not in str(extra)
        inner.post.assert_called_once()


def test_runner_success_path_patched_complete(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)

    def fake_complete(_self: object, _req: AICompletionRequest) -> AICompletionResponse:
        return AICompletionResponse(
            parsed_json={
                "title": "Canary",
                "summary": "Synthetic fixture summary.",
                "key_facts": ["a", "b"],
            },
            raw_text=None,
            input_tokens=12,
            output_tokens=34,
            cost_estimate=0.001,
            latency_ms=1,
            provider_request_id="test-req",
            finish_reason="stop",
            provider_name="openai",
        )

    org_id, job_id, ma_id = "org_cr_ok", "job_cr_ok", "ma_cr_ok"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        from ai.openai_adapter import OpenAIStructuredProviderShell

        with patch.object(OpenAIStructuredProviderShell, "complete", fake_complete):
            maybe_run_openai_canary_job_runner(session, job)
        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        st = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).one()
        assert st.validation_status == "accepted"
        assert st.provider_name == "openai"


def test_runner_no_ledger_side_effects(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)
    org_id, job_id, ma_id = "org_cr_led", "job_cr_led", "ma_cr_led"
    inner = MagicMock()
    inner.post.return_value = httpx.Response(401, json={})
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
            with patch("app.services.credit_ledger.debit_reserved_processing_minutes") as m_debit, patch(
                "app.services.credit_ledger.reserve_processing_minutes"
            ) as m_res, patch(
                "app.services.credit_ledger.release_reserved_processing_minutes"
            ) as m_rel:
                maybe_run_openai_canary_job_runner(session, job)
                m_debit.assert_not_called()
                m_res.assert_not_called()
                m_rel.assert_not_called()


def test_openai_canary_runner_enabled_helper(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FF_OPENAI_CANARY_RUNNER_ENABLED", raising=False)
    assert not openai_canary_runner_enabled()
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "1")
    assert openai_canary_runner_enabled()


def test_runner_calls_bounded_http_once_with_mocked_transport(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)
    org_id, job_id, ma_id = "org_cr_http", "job_cr_http", "ma_cr_http"
    inner = MagicMock()
    inner.post.return_value = httpx.Response(401, json={})
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
            maybe_run_openai_canary_job_runner(session, job)
        inner.post.assert_called_once()


def test_cli_dry_run_fail_closed_without_gates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AI_STRUCTURED_PROVIDER_MODE", raising=False)
    monkeypatch.setenv("AI_ENABLE_MOCK_PROVIDER", "true")
    rc = cli_main(["--dry-run", "--fixture", "tiny_transcript"])
    assert rc == 1


def test_cli_dry_run_ok_prints_redacted_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    _canary_env(monkeypatch)
    rc = cli_main(["--preflight", "--fixture", "tiny_transcript"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tiny_transcript" in out
    assert "present" in out
    assert "sk-" not in out


def test_cli_preflight_alias_matches_dry_run(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    _canary_env(monkeypatch)
    assert cli_main(["--dry-run", "--fixture", "tiny_transcript"]) == 0
    assert cli_main(["--preflight", "--fixture", "tiny_transcript"]) == 0


def test_manual_preflight_dry_run_returns_summary_dict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    _canary_env(monkeypatch)
    d = manual_run_openai_canary_preflight(dry_run=True, fixture_id="tiny_transcript", session=None, job=None)
    assert d is not None
    assert d.get("dry_run") is True
    assert d.get("fixture_id") == "tiny_transcript"


def test_manual_preflight_non_dry_patched_complete(monkeypatch: pytest.MonkeyPatch, sqlite_engine):
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    _canary_env(monkeypatch)

    def fake_complete(_self: object, _req: AICompletionRequest) -> AICompletionResponse:
        return AICompletionResponse(
            parsed_json={
                "title": "Canary",
                "summary": "Synthetic fixture summary.",
                "key_facts": ["a", "b"],
            },
            raw_text=None,
            input_tokens=12,
            output_tokens=34,
            cost_estimate=0.001,
            latency_ms=1,
            provider_request_id="test-req",
            finish_reason="stop",
            provider_name="openai",
        )

    org_id, job_id, ma_id = "org_cli_ok", "job_cli_ok", "ma_cli_ok"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        from ai.openai_adapter import OpenAIStructuredProviderShell

        with patch.object(OpenAIStructuredProviderShell, "complete", fake_complete):
            manual_run_openai_canary_preflight(
                dry_run=False,
                fixture_id="tiny_transcript",
                session=session,
                job=job,
            )
        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"


def test_cli_non_dry_requires_job_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    _canary_env(monkeypatch)
    assert cli_main([]) == 2


def test_cli_unknown_fixture_argv_errors():
    with pytest.raises(SystemExit):
        cli_main(["--fixture", "nope", "--dry-run"])
