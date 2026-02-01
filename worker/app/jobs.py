import time

from opentelemetry import trace

_TRACER = trace.get_tracer(__name__)

def noop_job(payload: str) -> str:
  with _TRACER.start_as_current_span("worker.job.noop") as span:
    span.set_attribute("job.payload_length", len(payload))
    time.sleep(0.1)
    return f"noop:{payload}"
