"""Prometheus метрики для Langfuse интеграции."""

import time
from collections.abc import Generator
from contextlib import contextmanager

from prometheus_client import REGISTRY, Counter, Histogram

# Создаём метрики для Langfuse
langfuse_traces_total = Counter(
    "langfuse_traces_total",
    "Общее количество traces созданных в Langfuse",
    ["workspace_id"],
    registry=REGISTRY,
)

langfuse_spans_total = Counter(
    "langfuse_spans_total",
    "Общее количество spans созданных в Langfuse traces",
    ["trace_id"],
    registry=REGISTRY,
)

langfuse_scores_total = Counter(
    "langfuse_scores_total",
    "Общее количество scores (оценок) записанных в Langfuse",
    ["score_name"],
    registry=REGISTRY,
)

langfuse_callback_failures = Counter(
    "langfuse_callback_failures",
    "Количество ошибок при выполнении Langfuse callbacks",
    ["callback_type", "error_type"],
    registry=REGISTRY,
)

langfuse_trace_creation_latency_seconds = Histogram(
    "langfuse_trace_creation_latency_seconds",
    "Latency создания trace в Langfuse (секунды)",
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)


@contextmanager
def trace_latency() -> Generator[None, None, None]:
    """
    Context manager для измерения latency создания trace.

    Usage:
        with trace_latency():
            # trace creation code
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        langfuse_trace_creation_latency_seconds.observe(elapsed)


def record_trace_created(workspace_id: str) -> None:
    """Записать что trace был создан."""
    langfuse_traces_total.labels(workspace_id=workspace_id).inc()


def record_span_created(trace_id: str) -> None:
    """Записать что span был создан."""
    langfuse_spans_total.labels(trace_id=trace_id).inc()


def record_score(score_name: str) -> None:
    """Записать что score был записан."""
    langfuse_scores_total.labels(score_name=score_name).inc()


def record_callback_failure(callback_type: str, error_type: str) -> None:
    """Записать ошибку в callback."""
    langfuse_callback_failures.labels(
        callback_type=callback_type, error_type=error_type
    ).inc()
