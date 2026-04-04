"""OpenTelemetry tracing bootstrap.

Initialises the OTel SDK and auto-instruments Flask.  If the OTLP
endpoint is unreachable the app continues without tracing.
"""
import logging
import os

logger = logging.getLogger(__name__)


def init_tracing(app):
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set – tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.environ.get("OTEL_SERVICE_NAME", "url-shortener")
        resource = Resource.create({"service.name": service_name})

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(app)
        logger.info("OpenTelemetry tracing initialised → %s", endpoint)
    except Exception:
        logger.warning("Failed to initialise tracing – continuing without it", exc_info=True)
