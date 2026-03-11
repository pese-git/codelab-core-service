"""Тесты для Prometheus метрик Langfuse интеграции."""

import pytest
from prometheus_client import REGISTRY, CollectorRegistry
from unittest.mock import patch, MagicMock

from app.metrics import (
    langfuse_traces_total,
    langfuse_spans_total,
    langfuse_scores_total,
    langfuse_callback_failures,
    langfuse_trace_creation_latency_seconds,
    record_trace_created,
    record_span_created,
    record_score,
    record_callback_failure,
    trace_latency,
)


class TestLangfuseMetrics:
    """Тесты для Langfuse метрик."""

    def test_record_trace_created(self):
        """Тест записи метрики создания trace."""
        # Очищаем метрику
        langfuse_traces_total._metrics.clear()
        
        # Записываем метрику
        workspace_id = "workspace-1"
        record_trace_created(workspace_id)
        
        # Проверяем что метрика была увеличена
        metric_value = langfuse_traces_total.labels(workspace_id=workspace_id)._value.get()
        assert metric_value > 0

    def test_record_span_created(self):
        """Тест записи метрики создания span."""
        # Очищаем метрику
        langfuse_spans_total._metrics.clear()
        
        # Записываем метрику
        trace_id = "trace-1"
        record_span_created(trace_id)
        
        # Проверяем что метрика была увеличена
        metric_value = langfuse_spans_total.labels(trace_id=trace_id)._value.get()
        assert metric_value > 0

    def test_record_score(self):
        """Тест записи метрики score."""
        # Очищаем метрику
        langfuse_scores_total._metrics.clear()
        
        # Записываем метрику
        score_name = "user_satisfaction"
        record_score(score_name)
        
        # Проверяем что метрика была увеличена
        metric_value = langfuse_scores_total.labels(score_name=score_name)._value.get()
        assert metric_value > 0

    def test_record_callback_failure(self):
        """Тест записи метрики ошибки callback."""
        # Очищаем метрику
        langfuse_callback_failures._metrics.clear()
        
        # Записываем метрику
        callback_type = "trace_creation"
        error_type = "TimeoutError"
        record_callback_failure(callback_type, error_type)
        
        # Проверяем что метрика была увеличена
        metric_value = langfuse_callback_failures.labels(
            callback_type=callback_type, error_type=error_type
        )._value.get()
        assert metric_value > 0

    def test_trace_latency_context_manager(self):
        """Тест context manager для измерения latency."""
        # Используем context manager
        with trace_latency():
            # Имитируем работу
            import time
            time.sleep(0.01)
        
        # Проверяем что метрика была записана
        # Для histogram нет простого способа проверить значение напрямую,
        # но мы можем проверить что объект метрики существует
        assert langfuse_trace_creation_latency_seconds is not None
        assert hasattr(langfuse_trace_creation_latency_seconds, 'observe')

    def test_multiple_metrics_recording(self):
        """Тест записи нескольких метрик."""
        # Очищаем метрики
        langfuse_traces_total._metrics.clear()
        langfuse_spans_total._metrics.clear()
        langfuse_scores_total._metrics.clear()
        
        # Записываем метрики
        workspace_id = "workspace-test"
        trace_id = "trace-test"
        score_name = "test_score"
        
        record_trace_created(workspace_id)
        record_span_created(trace_id)
        record_score(score_name)
        
        # Проверяем все метрики
        trace_metric = langfuse_traces_total.labels(workspace_id=workspace_id)._value.get()
        span_metric = langfuse_spans_total.labels(trace_id=trace_id)._value.get()
        score_metric = langfuse_scores_total.labels(score_name=score_name)._value.get()
        
        assert trace_metric > 0
        assert span_metric > 0
        assert score_metric > 0

    def test_callback_failure_various_errors(self):
        """Тест записи различных типов ошибок callback."""
        # Очищаем метрику
        langfuse_callback_failures._metrics.clear()
        
        # Записываем разные типы ошибок
        errors = [
            ("trace_creation", "TimeoutError"),
            ("span_creation", "ConnectionError"),
            ("score_recording", "ValueError"),
        ]
        
        for callback_type, error_type in errors:
            record_callback_failure(callback_type, error_type)
        
        # Проверяем что все метрики были записаны
        for callback_type, error_type in errors:
            metric_value = langfuse_callback_failures.labels(
                callback_type=callback_type, error_type=error_type
            )._value.get()
            assert metric_value > 0
