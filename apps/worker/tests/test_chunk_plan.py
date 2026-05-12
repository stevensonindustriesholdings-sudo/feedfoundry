from pipeline.chunk_plan import plan_chunks


def test_plan_chunks_splits():
    chunks = plan_chunks(1250.0, chunk_seconds=600.0)
    assert len(chunks) == 3
    assert chunks[0].start_sec == 0.0
    assert chunks[-1].end_sec == 1250.0
