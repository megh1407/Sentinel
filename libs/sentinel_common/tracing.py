"""
tracing.py

Thin wrapper over the OpenTelemetry SDK. `configure_tracing` is called once
per process; `start_span` auto-attaches correlation_id/causation_id as span
attributes so a trace and a log line for the same event are always
cross-referenceable. Kafka header injection/extraction lets a trace span
follow a message across the producer -> broker -> consumer boundary.
"""
from __future__ import annotations

from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .logging_context import get_causation_id, get_correlation_id

_propagator = TraceContextTextMapPropagator()
_configured_services: set[str] = set()


def configure_tracing(service_name: str, exporter=None, sample_rate: float = 1.0) -> None:
    """One-time OTel SDK bootstrap. Uses a ConsoleSpanExporter by default
    (safe for local dev / this environment, which has no live OTLP
    collector reachable) -- pass a real OTLPSpanExporter in production."""
    if service_name in _configured_services:
        return
    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter or ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured_services.add(service_name)


def get_tracer(name: str):
    return trace.get_tracer(name)


@contextmanager
def start_span(name: str, attributes: dict | None = None):
    tracer = trace.get_tracer("sentinel")
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("correlation_id", get_correlation_id() or "")
        span.set_attribute("causation_id", get_causation_id() or "")
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def inject_trace_headers(carrier: dict[str, str]) -> dict[str, str]:
    """Injects the current span's W3C traceparent into a Kafka header dict."""
    _propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: dict[str, str]):
    """Extracts a W3C traceparent from consumed Kafka headers into an OTel Context."""
    return _propagator.extract(carrier)
