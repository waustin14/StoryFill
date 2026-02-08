from app.main import run_worker


def test_run_worker_wires_queue(monkeypatch):
  calls = {}

  class DummyQueue:
    def __init__(self, name, connection):
      calls["queue_name"] = name
      calls["queue_connection"] = connection

  class DummyWorker:
    def __init__(self, queues, connection):
      calls["worker_queues"] = queues
      calls["worker_connection"] = connection

    def work(self):
      calls["work_called"] = True

  monkeypatch.setattr("app.main.redis.Redis.from_url", lambda url: "redis-conn")
  monkeypatch.setattr("app.main.Queue", DummyQueue)
  monkeypatch.setattr("app.main.Worker", DummyWorker)

  run_worker()

  assert calls["queue_name"] == "default"
  assert calls["queue_connection"] == "redis-conn"
  assert calls["work_called"] is True
