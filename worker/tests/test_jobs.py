from app.jobs import noop_job


def test_noop_job_returns_payload():
  assert noop_job("ping") == "noop:ping"
