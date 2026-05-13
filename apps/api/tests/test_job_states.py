from app.models import JobStatus


def test_terminal_states_exist():
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_happy_path_ordering():
    ordered = [
        JobStatus.UPLOADED,
        JobStatus.QUEUED,
        JobStatus.PROCESSING,
        JobStatus.COMPLETED,
    ]
    assert len(ordered) == len({s.value for s in ordered})
