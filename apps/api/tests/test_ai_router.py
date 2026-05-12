from pathlib import Path

from app.services.ai_router import build_request_for_module, load_ai_routing


def test_build_request_reads_yaml():
    root = Path(__file__).resolve().parents[3]
    routing = load_ai_routing(root / "ai-routing.yaml")
    assert routing.get("modules")
    req = build_request_for_module(
        routing=routing,
        module_name="metadata",
        job_id="job_x",
        model_resolver={"OPENAI_CHEAP_TEXT_MODEL": "gpt-4o-mini"},
    )
    assert req.module_name == "metadata"
    assert req.job_id == "job_x"
    assert req.fallback_provider
