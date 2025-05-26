"""
Event tracing and distributed tracing system.

This module provides comprehensive event tracing capabilities for debugging
and monitoring event flow through the bridge system.
"""

import time
import uuid
import asyncio
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from collections import defaultdict, deque

from .payload_schemas import BaseEventPayload


class TraceLevel(Enum):
    """Trace level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SpanType(Enum):
    """Span type enumeration."""
    EVENT_EMISSION = "event_emission"
    EVENT_PROCESSING = "event_processing"
    EVENT_FILTERING = "event_filtering"
    EVENT_COMPRESSION = "event_compression"
    STATE_UPDATE = "state_update"
    ADK_PROCESSING = "adk_processing"
    QUEUE_PROCESSING = "queue_processing"
    VALIDATION = "validation"


@dataclass
class TraceSpan:
    """Represents a single span in a distributed trace."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    span_type: SpanType
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "active"  # active, success, error
    error: Optional[str] = None
    
    def finish(self, error: Optional[Exception] = None):
        """Finish the span and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if error:
            self.status = "error"
            self.error = str(error)
            self.tags["error"] = True
            self.tags["error.type"] = type(error).__name__
        else:
            self.status = "success"
    
    def add_tag(self, key: str, value: Any):
        """Add a tag to the span."""
        self.tags[key] = value
    
    def add_log(self, level: TraceLevel, message: str, **kwargs):
        """Add a log entry to the span."""
        log_entry = {
            "timestamp": time.time(),
            "level": level.value,
            "message": message,
            **kwargs
        }
        self.logs.append(log_entry)


@dataclass
class Trace:
    """Represents a complete distributed trace."""
    trace_id: str
    root_span_id: str
    spans: Dict[str, TraceSpan] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def add_span(self, span: TraceSpan):
        """Add a span to the trace."""
        self.spans[span.span_id] = span
    
    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get a span by ID."""
        return self.spans.get(span_id)
    
    def finish(self):
        """Finish the trace."""
        self.end_time = time.time()
    
    def get_duration_ms(self) -> float:
        """Get total trace duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000
    
    def get_span_tree(self) -> Dict[str, List[str]]:
        """Get the parent-child relationships of spans."""
        tree = defaultdict(list)
        for span in self.spans.values():
            parent = span.parent_span_id or "root"
            tree[parent].append(span.span_id)
        return dict(tree)


class EventTracer:
    """Main event tracing system."""
    
    def __init__(self, max_traces: int = 10000, trace_retention_hours: int = 24):
        self.max_traces = max_traces
        self.trace_retention_hours = trace_retention_hours
        
        self.active_traces: Dict[str, Trace] = {}
        self.completed_traces: deque = deque(maxlen=max_traces)
        self.active_spans: Dict[str, TraceSpan] = {}
        
        # Configuration
        self.enabled = True
        self.sample_rate = 1.0  # Sample 100% of traces by default
        self.min_duration_ms = 0  # Trace all events by default
        
        # Output configuration
        self.output_dir = Path("monitoring/traces")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def start_tracer(self):
        """Start the tracer and cleanup task."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    def stop_tracer(self):
        """Stop the tracer and cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    def should_trace(self) -> bool:
        """Determine if a new trace should be created based on sampling."""
        import random
        return self.enabled and random.random() < self.sample_rate
    
    def start_trace(self, operation_name: str, span_type: SpanType, 
                   event_data: Optional[Dict[str, Any]] = None) -> Optional[TraceSpan]:
        """Start a new trace with a root span."""
        if not self.should_trace():
            return None
        
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        # Create root span
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=None,
            operation_name=operation_name,
            span_type=span_type,
            start_time=time.time()
        )
        
        # Add event data as tags
        if event_data:
            span.add_tag("event.type", event_data.get("eventType"))
            span.add_tag("event.id", event_data.get("eventId"))
            span.add_tag("event.source", event_data.get("source"))
            span.add_tag("event.timestamp", event_data.get("timestamp"))
        
        # Create trace
        trace = Trace(trace_id=trace_id, root_span_id=span_id)
        trace.add_span(span)
        
        # Store active trace and span
        self.active_traces[trace_id] = trace
        self.active_spans[span_id] = span
        
        return span
    
    def start_child_span(self, parent_span: TraceSpan, operation_name: str, 
                        span_type: SpanType) -> TraceSpan:
        """Start a child span."""
        span_id = str(uuid.uuid4())
        
        child_span = TraceSpan(
            span_id=span_id,
            trace_id=parent_span.trace_id,
            parent_span_id=parent_span.span_id,
            operation_name=operation_name,
            span_type=span_type,
            start_time=time.time()
        )
        
        # Add to trace and active spans
        if parent_span.trace_id in self.active_traces:
            self.active_traces[parent_span.trace_id].add_span(child_span)
        
        self.active_spans[span_id] = child_span
        
        return child_span
    
    def finish_span(self, span: TraceSpan, error: Optional[Exception] = None):
        """Finish a span and potentially the entire trace."""
        span.finish(error)
        
        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
        
        # Check if this was the root span
        if span.trace_id in self.active_traces:
            trace = self.active_traces[span.trace_id]
            if span.span_id == trace.root_span_id:
                # Root span finished, complete the trace
                trace.finish()
                
                # Only keep trace if it meets minimum duration
                if trace.get_duration_ms() >= self.min_duration_ms:
                    self.completed_traces.append(trace)
                    self._export_trace(trace)
                
                # Remove from active traces
                del self.active_traces[span.trace_id]
    
    def get_active_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get an active span by ID."""
        return self.active_spans.get(span_id)
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID (active or completed)."""
        # Check active traces first
        if trace_id in self.active_traces:
            return self.active_traces[trace_id]
        
        # Check completed traces
        for trace in self.completed_traces:
            if trace.trace_id == trace_id:
                return trace
        
        return None
    
    def search_traces(self, operation_name: Optional[str] = None,
                     span_type: Optional[SpanType] = None,
                     min_duration_ms: Optional[float] = None,
                     max_duration_ms: Optional[float] = None,
                     has_error: Optional[bool] = None,
                     limit: int = 100) -> List[Trace]:
        """Search traces based on criteria."""
        results = []
        
        for trace in list(self.completed_traces):
            if len(results) >= limit:
                break
            
            # Check duration filters
            if min_duration_ms and trace.get_duration_ms() < min_duration_ms:
                continue
            if max_duration_ms and trace.get_duration_ms() > max_duration_ms:
                continue
            
            # Check if trace has spans matching criteria
            matching_spans = []
            for span in trace.spans.values():
                if operation_name and operation_name not in span.operation_name:
                    continue
                if span_type and span.span_type != span_type:
                    continue
                if has_error is not None and bool(span.error) != has_error:
                    continue
                matching_spans.append(span)
            
            if matching_spans:
                results.append(trace)
        
        return results
    
    def get_trace_statistics(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        total_traces = len(self.completed_traces) + len(self.active_traces)
        error_traces = len([t for t in self.completed_traces 
                           if any(s.status == "error" for s in t.spans.values())])
        
        durations = [t.get_duration_ms() for t in self.completed_traces]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        span_types = defaultdict(int)
        for trace in self.completed_traces:
            for span in trace.spans.values():
                span_types[span.span_type.value] += 1
        
        return {
            "total_traces": total_traces,
            "active_traces": len(self.active_traces),
            "completed_traces": len(self.completed_traces),
            "error_traces": error_traces,
            "error_rate": error_traces / len(self.completed_traces) if self.completed_traces else 0,
            "avg_duration_ms": avg_duration,
            "span_types": dict(span_types),
            "sample_rate": self.sample_rate,
            "enabled": self.enabled
        }
    
    def _export_trace(self, trace: Trace):
        """Export a completed trace to storage."""
        trace_data = {
            "traceId": trace.trace_id,
            "rootSpanId": trace.root_span_id,
            "startTime": trace.start_time,
            "endTime": trace.end_time,
            "durationMs": trace.get_duration_ms(),
            "spans": []
        }
        
        for span in trace.spans.values():
            span_data = {
                "spanId": span.span_id,
                "parentSpanId": span.parent_span_id,
                "operationName": span.operation_name,
                "spanType": span.span_type.value,
                "startTime": span.start_time,
                "endTime": span.end_time,
                "durationMs": span.duration_ms,
                "status": span.status,
                "error": span.error,
                "tags": span.tags,
                "logs": span.logs
            }
            trace_data["spans"].append(span_data)
        
        # Export to JSON file
        timestamp = datetime.fromtimestamp(trace.start_time)
        filename = f"trace_{trace.trace_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        output_file = self.output_dir / filename
        
        with open(output_file, 'w') as f:
            json.dump(trace_data, f, indent=2)
    
    async def _cleanup_loop(self):
        """Cleanup old traces periodically."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_traces()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Trace cleanup error: {e}")
    
    async def _cleanup_old_traces(self):
        """Remove old trace files."""
        cutoff_time = time.time() - (self.trace_retention_hours * 3600)
        
        for trace_file in self.output_dir.glob("trace_*.json"):
            if trace_file.stat().st_mtime < cutoff_time:
                trace_file.unlink()


class TracingMiddleware:
    """Middleware to automatically trace event processing."""
    
    def __init__(self, tracer: EventTracer):
        self.tracer = tracer
    
    async def trace_event_processing(self, event_type: str, event_data: Dict[str, Any],
                                   handler: callable) -> Any:
        """Trace event processing through a handler."""
        # Start root span for event processing
        root_span = self.tracer.start_trace(
            operation_name=f"process_{event_type}",
            span_type=SpanType.EVENT_PROCESSING,
            event_data=event_data
        )
        
        if not root_span:
            # Tracing disabled or not sampled
            return await handler(event_data)
        
        try:
            # Add event-specific tags
            root_span.add_tag("event.size_bytes", len(str(event_data)))
            root_span.add_log(TraceLevel.INFO, f"Starting processing of {event_type}")
            
            # Process the event
            result = await handler(event_data)
            
            root_span.add_log(TraceLevel.INFO, f"Successfully processed {event_type}")
            return result
            
        except Exception as e:
            root_span.add_log(TraceLevel.ERROR, f"Error processing {event_type}: {e}")
            raise
        finally:
            self.tracer.finish_span(root_span)
    
    def trace_operation(self, parent_span: TraceSpan, operation_name: str, 
                       span_type: SpanType):
        """Context manager for tracing an operation."""
        return TracingContext(self.tracer, parent_span, operation_name, span_type)


class TracingContext:
    """Context manager for tracing operations."""
    
    def __init__(self, tracer: EventTracer, parent_span: TraceSpan, 
                 operation_name: str, span_type: SpanType):
        self.tracer = tracer
        self.parent_span = parent_span
        self.operation_name = operation_name
        self.span_type = span_type
        self.span: Optional[TraceSpan] = None
    
    def __enter__(self) -> TraceSpan:
        self.span = self.tracer.start_child_span(
            self.parent_span, self.operation_name, self.span_type
        )
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            error = exc_val if exc_type else None
            self.tracer.finish_span(self.span, error)


# Global tracer instance
_global_tracer: Optional[EventTracer] = None


def get_tracer() -> EventTracer:
    """Get the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = EventTracer()
    return _global_tracer


def start_tracing():
    """Start the global tracing system."""
    tracer = get_tracer()
    tracer.start_tracer()


def stop_tracing():
    """Stop the global tracing system."""
    tracer = get_tracer()
    tracer.stop_tracer()