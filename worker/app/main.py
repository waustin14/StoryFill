import os

import redis
from rq import Queue, Worker

from app.logging import configure_logging
from app.otel import init_tracing

configure_logging()
init_tracing(os.getenv("OTEL_SERVICE_NAME", "storyfill-worker"))


def run_worker() -> None:
  redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
  connection = redis.Redis.from_url(redis_url)
  queue = Queue("default", connection=connection)
  worker = Worker([queue], connection=connection)
  worker.work()


if __name__ == "__main__":
  run_worker()
