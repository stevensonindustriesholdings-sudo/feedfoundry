"""Worker stub output order matches hosted object keys (transcript-derived slice)."""

from __future__ import annotations

import worker as worker_mod


def test_stub_output_write_order_covers_core_manifest_artefacts():
    """Transcript + derived JSON filenames align with API/README object layout."""
    order = worker_mod.OUTPUT_WRITE_ORDER
    filenames = [fn for fn, _ot in order]
    assert filenames[0] == "transcript.json"
    assert "chapters.json" in filenames
    assert "factsheet.json" in filenames
    assert "faq.json" in filenames
    assert "metadata.json" in filenames
    assert "hosted_manifest.json" in filenames
    types = [ot for _fn, ot in order]
    from app.models import JobOutputType

    assert types[0] == JobOutputType.RAW_TRANSCRIPT
    assert JobOutputType.HOSTED_MANIFEST in types
