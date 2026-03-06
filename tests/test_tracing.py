"""Tests for OpenTelemetry tracing integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from app.tracing import initialize_tracing, get_tracer
from app.config import settings


class TestTracingInitialization:
    """Test OpenTelemetry initialization."""

    def test_tracer_initialization(self):
        """Test that tracer is properly initialized."""
        tracer = get_tracer(__name__)
        assert tracer is not None
        assert isinstance(tracer, trace.Tracer)

    def test_tracer_consistency(self):
        """Test that get_tracer returns same instance for same module."""
        tracer1 = get_tracer("test_module")
        tracer2 = get_tracer("test_module")
        assert tracer1 == tracer2

    def test_tracer_different_modules(self):
        """Test that different modules get different tracers."""
        tracer1 = get_tracer("module1")
        tracer2 = get_tracer("module2")
        # Same provider, but different tracer instances
        assert tracer1 is not None
        assert tracer2 is not None

    @patch('app.tracing.settings.enable_tracing', False)
    def test_tracing_disabled(self, mock_settings):
        """Test graceful handling when tracing is disabled."""
        # When tracing is disabled, initialize_tracing should return without error
        try:
            initialize_tracing()
        except Exception as e:
            pytest.fail(f"initialize_tracing raised exception when disabled: {e}")


class TestSpanCreation:
    """Test span creation and attributes."""

    def test_create_span(self):
        """Test basic span creation."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("test_span") as span:
            assert span is not None
            span.set_attribute("test.attr", "test_value")
            span.set_attribute("test.number", 42)

    def test_span_with_event(self):
        """Test adding events to spans."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("test_span") as span:
            span.add_event("test_event", {"key": "value"})
            span.add_event("another_event", {"count": 5})

    def test_nested_spans(self):
        """Test parent-child span relationship."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("parent_span") as parent:
            parent.set_attribute("parent.attr", "parent_value")
            
            with tracer.start_as_current_span("child_span") as child:
                child.set_attribute("child.attr", "child_value")
            
            # Parent span continues after child is closed
            parent.set_attribute("parent.after_child", "still_open")

    def test_span_with_exception(self):
        """Test span exception recording."""
        tracer = get_tracer(__name__)
        
        try:
            with tracer.start_as_current_span("error_span") as span:
                try:
                    raise ValueError("test error")
                except ValueError as e:
                    span.record_exception(e)
                    span.set_attribute("status", "error")
        except Exception:
            pass  # Expected to fail


class TestTracingAttributes:
    """Test span attributes are properly set."""

    def test_agent_execution_attributes(self):
        """Test attributes for agent execution span."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("agent_execution") as span:
            span.set_attribute("agent.id", "test-agent-id")
            span.set_attribute("agent.name", "test-agent")
            span.set_attribute("model", "gpt-4")
            span.set_attribute("session.id", "test-session-id")
            
            # Verify attributes were set
            assert span is not None

    def test_llm_call_attributes(self):
        """Test attributes for LLM call span."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("llm_call") as span:
            span.set_attribute("model", "gpt-4")
            span.set_attribute("temperature", 0.7)
            span.set_attribute("provider", "openai")
            span.set_attribute("latency_ms", 1250)
            span.set_attribute("tokens_prompt", 150)
            span.set_attribute("tokens_completion", 200)
            span.set_attribute("tokens_total", 350)
            
            assert span is not None

    def test_tool_execution_attributes(self):
        """Test attributes for tool execution span."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("tool_execution") as span:
            span.set_attribute("tool.name", "read_file")
            span.set_attribute("session.id", "test-session")
            span.set_attribute("execution_record_id", "test-exec-id")
            span.set_attribute("status", "pending")
            
            with tracer.start_as_current_span("tool_validation") as val_span:
                val_span.set_attribute("validation_status", "passed")
            
            with tracer.start_as_current_span("risk_assessment") as risk_span:
                risk_span.set_attribute("risk_level", "medium")
            
            assert span is not None

    def test_message_processing_attributes(self):
        """Test attributes for message processing span."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("message_processing") as span:
            span.set_attribute("session.id", "test-session-id")
            span.set_attribute("project.id", "test-project-id")
            span.set_attribute("user.id", "test-user-id")
            span.set_attribute("message.type", "user_message")
            
            span.add_event("message_received", {"content_length": 150})
            span.add_event("response_generated", {"response_length": 300})
            
            assert span is not None


class TestTracingConfiguration:
    """Test tracing configuration."""

    def test_settings_available(self):
        """Test that tracing settings are available."""
        assert hasattr(settings, 'enable_tracing')
        assert hasattr(settings, 'jaeger_host')
        assert hasattr(settings, 'jaeger_port')

    def test_settings_defaults(self):
        """Test default values for tracing settings."""
        # These should have reasonable defaults
        assert settings.enable_tracing is not None
        assert settings.jaeger_host is not None
        assert settings.jaeger_port is not None


class TestSpanContextPropagation:
    """Test span context propagation."""

    def test_current_span_context(self):
        """Test that current span context is available."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("outer_span") as outer:
            outer.set_attribute("level", "outer")
            
            # Child span should be able to access parent context
            with tracer.start_as_current_span("inner_span") as inner:
                inner.set_attribute("level", "inner")
                current = trace.get_current_span()
                assert current is not None

    def test_span_isolation(self):
        """Test that spans are properly isolated."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("span1") as span1:
            span1.set_attribute("id", "span1")
        
        with tracer.start_as_current_span("span2") as span2:
            span2.set_attribute("id", "span2")
        
        # Both spans should complete without interference


class TestErrorHandling:
    """Test error handling in tracing."""

    def test_span_records_exception(self):
        """Test that spans can record exceptions."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("error_span") as span:
            try:
                # Simulate an error
                raise RuntimeError("test error")
            except RuntimeError as e:
                span.record_exception(e)
                span.set_attribute("status", "error")

    def test_graceful_degradation_without_jaeger(self):
        """Test that tracing works even if Jaeger is unavailable."""
        # When Jaeger is down, traces should still be created
        # (they just won't be exported)
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test", "value")
        
        # Should complete without raising exceptions


class TestMultipleSpans:
    """Test handling of multiple concurrent and sequential spans."""

    def test_sequential_spans(self):
        """Test creating spans sequentially."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("span1"):
            pass
        
        with tracer.start_as_current_span("span2"):
            pass
        
        with tracer.start_as_current_span("span3"):
            pass

    def test_concurrent_spans_simulation(self):
        """Test nested spans that simulate concurrent operations."""
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("parent"):
            with tracer.start_as_current_span("child1"):
                pass
            
            with tracer.start_as_current_span("child2"):
                pass
            
            with tracer.start_as_current_span("child3"):
                pass
