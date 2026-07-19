"""
observability/tracing.py — OpenTelemetry setup.

Configures tracing with OTLP export to Jaeger.
Auto-instruments FastAPI, httpx, and asyncpg.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("ars.observability.tracing")


def setup_tracing(service_name: str = "ars-orchestrator", app=None) -> None:
    """Initialize OpenTelemetry tracing with OTLP exporter."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            if app:
                FastAPIInstrumentor.instrument_app(app)
            else:
                FastAPIInstrumentor().instrument()
        except ImportError:
            log.info("FastAPI instrumentor not available")

        # Auto-instrument httpx
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
        except ImportError:
            log.info("httpx instrumentor not available")

        log.info("OpenTelemetry tracing initialized → %s", endpoint)

    except ImportError:
        log.warning(
            "OpenTelemetry packages not installed. Tracing disabled. "
            "Install: pip install opentelemetry-sdk opentelemetry-exporter-otlp"
        )
    except Exception as e:
        log.warning("Failed to initialize tracing: %s", e)


def get_tracer(name: str = "ars-orchestrator"):
    """Get a tracer instance (no-op if OTEL not configured)."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None
