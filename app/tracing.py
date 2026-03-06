"""OpenTelemetry tracing setup and initialization."""

from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def initialize_tracing(app: Optional[object] = None) -> None:
    """
    Initialize OpenTelemetry tracing infrastructure.

    Args:
        app: FastAPI application instance (optional, for FastAPI instrumentation)

    Gracefully degrades if Jaeger is unavailable - logs warning and continues.
    Uses OTLP exporter for better compatibility.
    """
    if not settings.enable_tracing:
        logger.info("tracing_disabled_by_config")
        return

    try:
        # Resource describes the service
        resource = Resource.create(
            {
                SERVICE_NAME: "codelab-core-service",
                "environment": settings.app_env,
                "version": settings.app_version,
            }
        )

        # OTLP exporter - uses HTTP protocol for Jaeger/other collectors
        # Falls back to no-op if collector is unavailable
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.otlp_exporter_url}/v1/traces",
        )

        # TracerProvider - global provider for all traces
        tracer_provider = TracerProvider(resource=resource)

        # Use BatchSpanProcessor for minimal performance impact
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set as global
        trace.set_tracer_provider(tracer_provider)

        # Auto-instrument FastAPI if app provided
        if app is not None:
            try:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("fastapi_instrumented")
            except Exception as e:
                logger.warning("fastapi_instrumentation_failed", error=str(e))

        logger.info(
            "opentelemetry_initialized",
            jaeger_host=settings.jaeger_host,
            jaeger_port=settings.jaeger_port,
        )

    except Exception as e:
        # Graceful degradation - log but don't crash
        logger.warning(
            "opentelemetry_initialization_failed",
            error=str(e),
            msg="Continuing without tracing",
        )


def get_tracer(module_name: str) -> trace.Tracer:
    """
    Get tracer for a specific module.

    Args:
        module_name: Module name (typically __name__)

    Returns:
        Tracer instance for the module
    """
    return trace.get_tracer(module_name)
