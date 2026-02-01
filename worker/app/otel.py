from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(service_name: str) -> None:
  resource = Resource.create({"service.name": service_name})
  provider = TracerProvider(resource=resource)
  processor = BatchSpanProcessor(OTLPSpanExporter())
  provider.add_span_processor(processor)
  trace.set_tracer_provider(provider)
  RedisInstrumentor().instrument()
