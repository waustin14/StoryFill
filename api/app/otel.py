import os

from app.core.config import OTEL_SERVICE_NAME
from app.db.session import engine


def init_tracing(app) -> None:
  if os.getenv("OTEL_SDK_DISABLED", "").lower() in {"true", "1", "yes"}:
    return
  if os.getenv("OTEL_TRACES_EXPORTER", "").lower() == "none":
    return
  # Make tracing optional so local dev/tests can run without full OTEL extras installed.
  try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
  except Exception:
    return

  resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
  provider = TracerProvider(resource=resource)
  processor = BatchSpanProcessor(OTLPSpanExporter())
  provider.add_span_processor(processor)
  trace.set_tracer_provider(provider)

  FastAPIInstrumentor.instrument_app(app)
  RedisInstrumentor().instrument()
  SQLAlchemyInstrumentor().instrument(engine=engine)
