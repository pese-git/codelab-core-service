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
        # Increased timeout from default 10s to 30s for better reliability
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.otlp_exporter_url}/v1/traces",
            timeout=30,
        )

        # TracerProvider - global provider for all traces
        tracer_provider = TracerProvider(resource=resource)

        # Use BatchSpanProcessor for minimal performance impact
        # Increased schedule_delay from 5s to 10s and max_export_batch_size for batching
        # NOTE: Main tracing goes through Langfuse SDK (via decorators in code),
        # OTEL spans are secondary and exported via this processor
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                otlp_exporter,
                schedule_delay_millis=10000,  # 10 seconds
                max_export_batch_size=512,
                max_queue_size=2048,
            )
        )

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
