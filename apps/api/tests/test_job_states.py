from app.models import JobStatus


def test_terminal_states_exist():
    assert JobStatus.COMPLETE.value == "complete"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_happy_path_ordering():
    ordered = [
        JobStatus.CREATED,
        JobStatus.ESTIMATING,
        JobStatus.AWAITING_CREDIT_RESERVATION,
        JobStatus.QUEUED,
        JobStatus.PROBING,
        JobStatus.EXTRACTING_AUDIO,
        JobStatus.CHUNKING,
        JobStatus.TRANSCRIBING,
        JobStatus.GENERATING_OUTPUTS,
        JobStatus.QA_VALIDATING,
        JobStatus.EXPORTING,
        JobStatus.COMPLETE,
    ]
    assert len(ordered) == len({s.value for s in ordered})
