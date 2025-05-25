# Event Bridge API Reference

## Overview

This document provides comprehensive API reference for the Event Bridge system components, including classes, methods, configuration options, and usage examples.

## Core Components

### EventRegistry

Central registry for managing event types and their metadata.

#### Class: `EventRegistry`

```python
class EventRegistry:
    def __init__(self)
```

**Methods:**

##### `register_event_type(event_type: str, metadata: Dict[str, Any]) -> None`
Register a new event type with metadata.

**Parameters:**
- `event_type` (str): Event type identifier (e.g., "minecraft:spawn")
- `metadata` (dict): Event metadata configuration

**Example:**
```python
registry = EventRegistry()
registry.register_event_type("minecraft:custom", {
    "description": "Custom event",
    "priority": 75,
    "batching_enabled": True,
    "adk_state_mapping": {
        "minecraft.custom.value": "value"
    }
})
```

##### `get_event_metadata(event_type: str) -> Optional[Dict[str, Any]]`
Retrieve metadata for an event type.

**Parameters:**
- `event_type` (str): Event type identifier

**Returns:**
- `dict` or `None`: Event metadata or None if not found

##### `list_event_types() -> List[str]`
Get list of all registered event types.

**Returns:**
- `List[str]`: List of event type identifiers

---

### PriorityEventQueue

Priority-based event processing queue with batching support.

#### Class: `PriorityEventQueue`

```python
class PriorityEventQueue:
    def __init__(self, max_size: int = 10000, workers: int = 3)
```

**Parameters:**
- `max_size` (int): Maximum queue size (default: 10000)
- `workers` (int): Number of worker coroutines (default: 3)

**Methods:**

##### `async add_event(event_data: Dict[str, Any], priority: int = 50) -> None`
Add an event to the queue.

**Parameters:**
- `event_data` (dict): Event payload
- `priority` (int): Event priority (higher = processed first)

**Example:**
```python
queue = PriorityEventQueue()
await queue.add_event({
    "eventType": "minecraft:spawn",
    "timestamp": time.time(),
    "source": "bot_1",
    "data": {"spawned": True}
}, priority=100)
```

##### `async get_next_event() -> QueuedEvent`
Get the next highest priority event.

**Returns:**
- `QueuedEvent`: Next event to process

##### `async get_batch(size: int = 50) -> List[QueuedEvent]`
Get a batch of events for bulk processing.

**Parameters:**
- `size` (int): Maximum batch size

**Returns:**
- `List[QueuedEvent]`: Batch of events

##### `size() -> int`
Get current queue size.

**Returns:**
- `int`: Number of events in queue

---

### EventFilterManager

Comprehensive event filtering and subscription system.

#### Class: `EventFilterManager`

```python
class EventFilterManager:
    def __init__(self)
```

**Methods:**

##### `create_event_type_filter(event_types: List[str]) -> EventFilter`
Create filter for specific event types.

**Parameters:**
- `event_types` (List[str]): Allowed event types

**Example:**
```python
filter_manager = EventFilterManager()
type_filter = filter_manager.create_event_type_filter([
    "minecraft:spawn", "minecraft:chat"
])
```

##### `create_priority_filter(min_priority: int = 0, max_priority: int = 100) -> EventFilter`
Create priority-based filter.

**Parameters:**
- `min_priority` (int): Minimum priority threshold
- `max_priority` (int): Maximum priority threshold

##### `create_frequency_filter(max_events_per_second: float) -> EventFilter`
Create frequency-limiting filter.

**Parameters:**
- `max_events_per_second` (float): Maximum event rate

##### `create_filter_chain(filters: List[EventFilter]) -> EventFilter`
Chain multiple filters together.

**Parameters:**
- `filters` (List[EventFilter]): Filters to chain

**Returns:**
- `EventFilter`: Combined filter

---

### StateSynchronizer

Bidirectional state synchronization with ADK sessions.

#### Class: `StateSynchronizer`

```python
class StateSynchronizer:
    def __init__(self, persistence_enabled: bool = True)
```

**Parameters:**
- `persistence_enabled` (bool): Enable state persistence

**Methods:**

##### `async update_state_from_event(event_data: Dict[str, Any]) -> None`
Update state from an event.

**Parameters:**
- `event_data` (dict): Event payload

**Example:**
```python
state_sync = StateSynchronizer()
await state_sync.update_state_from_event({
    "eventType": "minecraft:spawn",
    "data": {
        "spawned": True,
        "position": {"x": 100, "y": 64, "z": 200}
    }
})
```

##### `get_current_state() -> Dict[str, Any]`
Get current state snapshot.

**Returns:**
- `dict`: Current state

##### `set_state_value(key: str, value: Any) -> None`
Set a specific state value.

**Parameters:**
- `key` (str): State key (supports dot notation)
- `value` (Any): State value

##### `create_snapshot() -> Dict[str, Any]`
Create timestamped state snapshot.

**Returns:**
- `dict`: State snapshot with timestamp

##### `add_validation_rule(key: str, validator: Callable[[Any], bool]) -> None`
Add validation rule for state updates.

**Parameters:**
- `key` (str): State key
- `validator` (Callable): Validation function

---

### EventCompressor

Event compression for network efficiency.

#### Class: `EventCompressor`

```python
class EventCompressor:
    def __init__(self, default_algorithm: str = "lz4")
```

**Parameters:**
- `default_algorithm` (str): Default compression algorithm

**Methods:**

##### `compress(data: Dict[str, Any], algorithm: str = None) -> bytes`
Compress event data.

**Parameters:**
- `data` (dict): Event data to compress
- `algorithm` (str): Compression algorithm ("lz4", "gzip", "zlib")

**Returns:**
- `bytes`: Compressed data

**Example:**
```python
compressor = EventCompressor()
compressed = compressor.compress({
    "eventType": "minecraft:inventory",
    "data": {"items": [...]}  # Large inventory data
}, algorithm="gzip")
```

##### `decompress(compressed_data: bytes, algorithm: str) -> Dict[str, Any]`
Decompress event data.

**Parameters:**
- `compressed_data` (bytes): Compressed data
- `algorithm` (str): Compression algorithm used

**Returns:**
- `dict`: Decompressed event data

##### `compress_batch(events: List[Dict[str, Any]], algorithm: str = None) -> bytes`
Compress batch of events.

**Parameters:**
- `events` (List[dict]): Events to compress
- `algorithm` (str): Compression algorithm

**Returns:**
- `bytes`: Compressed batch

---

### CircuitBreaker

Fault tolerance and system protection.

#### Class: `CircuitBreaker`

```python
class CircuitBreaker:
    def __init__(self, 
                 failure_threshold: int = 5,
                 timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception)
```

**Parameters:**
- `failure_threshold` (int): Failures before opening circuit
- `timeout` (float): Timeout before attempting recovery
- `expected_exception` (Type[Exception]): Exception type to catch

**Usage as Decorator:**
```python
circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)

@circuit_breaker
async def fragile_operation():
    # Operation that might fail
    pass
```

**Properties:**
- `state` (str): Current state ("CLOSED", "OPEN", "HALF_OPEN")
- `failure_count` (int): Current failure count
- `last_failure_time` (float): Timestamp of last failure

---

## Monitoring Components

### EventMetricsCollector

Comprehensive performance and health monitoring.

#### Class: `EventMetricsCollector`

```python
class EventMetricsCollector:
    def __init__(self, window_size: int = 300)
```

**Parameters:**
- `window_size` (int): Time window for rate calculations (seconds)

**Methods:**

##### `record_event_start(event_type: str) -> str`
Record start of event processing.

**Parameters:**
- `event_type` (str): Event type being processed

**Returns:**
- `str`: Tracking ID for this event

##### `record_event_success(event_type: str, tracking_id: str, processing_time: float) -> None`
Record successful event processing.

**Parameters:**
- `event_type` (str): Event type
- `tracking_id` (str): Tracking ID from event start
- `processing_time` (float): Processing time in seconds

##### `record_event_error(event_type: str, tracking_id: str, error: Exception) -> None`
Record event processing error.

**Parameters:**
- `event_type` (str): Event type
- `tracking_id` (str): Tracking ID from event start
- `error` (Exception): Error that occurred

##### `get_system_metrics() -> SystemMetrics`
Get current system metrics.

**Returns:**
- `SystemMetrics`: System performance data

**Example:**
```python
metrics = EventMetricsCollector()

# Record event processing
tracking_id = metrics.record_event_start("minecraft:spawn")
try:
    # Process event
    processing_time = 0.05
    metrics.record_event_success("minecraft:spawn", tracking_id, processing_time)
except Exception as e:
    metrics.record_event_error("minecraft:spawn", tracking_id, e)

# Get metrics
system_stats = metrics.get_system_metrics()
print(f"Events/sec: {system_stats.events_per_second}")
```

---

### EventTracer

Distributed tracing for debugging and monitoring.

#### Class: `EventTracer`

```python
class EventTracer:
    def __init__(self, max_traces: int = 10000, trace_retention_hours: int = 24)
```

**Parameters:**
- `max_traces` (int): Maximum traces to retain
- `trace_retention_hours` (int): Hours to retain trace files

**Methods:**

##### `start_trace(operation_name: str, span_type: SpanType, event_data: Optional[Dict] = None) -> Optional[TraceSpan]`
Start a new trace.

**Parameters:**
- `operation_name` (str): Name of operation being traced
- `span_type` (SpanType): Type of span
- `event_data` (dict, optional): Event data to include

**Returns:**
- `TraceSpan` or `None`: Trace span if sampling allows

##### `start_child_span(parent_span: TraceSpan, operation_name: str, span_type: SpanType) -> TraceSpan`
Start a child span.

**Parameters:**
- `parent_span` (TraceSpan): Parent span
- `operation_name` (str): Child operation name
- `span_type` (SpanType): Span type

**Returns:**
- `TraceSpan`: Child span

##### `finish_span(span: TraceSpan, error: Optional[Exception] = None) -> None`
Finish a span.

**Parameters:**
- `span` (TraceSpan): Span to finish
- `error` (Exception, optional): Error if span failed

**Example:**
```python
from src.bridge.event_bridge.tracing import SpanType

tracer = EventTracer()

# Start trace
span = tracer.start_trace("process_event", SpanType.EVENT_PROCESSING)
if span:
    try:
        # Add child span for validation
        validation_span = tracer.start_child_span(
            span, "validate_payload", SpanType.VALIDATION
        )
        # Validation logic
        tracer.finish_span(validation_span)
        
        # Processing logic
        tracer.finish_span(span)
    except Exception as e:
        tracer.finish_span(span, e)
```

---

### PerformanceProfiler

Detailed performance analysis and optimization.

#### Class: `PerformanceProfiler`

```python
class PerformanceProfiler:
    def __init__(self, output_dir: Optional[Path] = None)
```

**Parameters:**
- `output_dir` (Path, optional): Directory for profile outputs

**Methods:**

##### `profile_cpu(operation_name: str, profile_id: Optional[str] = None)`
Context manager for CPU profiling.

**Parameters:**
- `operation_name` (str): Name of operation
- `profile_id` (str, optional): Custom profile ID

**Usage:**
```python
profiler = PerformanceProfiler()

with profiler.profile_cpu("expensive_operation") as profile_id:
    # CPU-intensive code
    result = compute_heavy_task()
```

##### `profile_memory(operation_name: str, profile_id: Optional[str] = None)`
Context manager for memory profiling.

**Parameters:**
- `operation_name` (str): Name of operation
- `profile_id` (str, optional): Custom profile ID

##### `profile_function(operation_name: Optional[str] = None)`
Decorator for automatic function profiling.

**Parameters:**
- `operation_name` (str, optional): Custom operation name

**Usage:**
```python
@profiler.profile_function("my_function")
def my_expensive_function():
    # Function code
    pass
```

##### `take_memory_snapshot() -> MemorySnapshot`
Take memory usage snapshot.

**Returns:**
- `MemorySnapshot`: Current memory usage data

##### `get_profile_summary(hours: int = 1) -> Dict[str, Any]`
Get profiling summary.

**Parameters:**
- `hours` (int): Hours of data to include

**Returns:**
- `dict`: Profile summary statistics

---

## Event Schemas

### Base Event Schema

All events must conform to the base schema:

```python
class BaseEventPayload(BaseModel):
    eventType: str
    timestamp: float
    source: str
    eventId: str
    data: Dict[str, Any]
```

### Common Data Models

#### PositionModel
```python
class PositionModel(BaseModel):
    x: float
    y: float
    z: float
    yaw: Optional[float] = None
    pitch: Optional[float] = None
```

#### ItemModel
```python
class ItemModel(BaseModel):
    type: str
    count: int
    metadata: Optional[Dict[str, Any]] = None
    slot: Optional[int] = None
```

#### PlayerModel
```python
class PlayerModel(BaseModel):
    username: str
    uuid: str
    position: Optional[PositionModel] = None
    health: Optional[float] = None
```

### Event-Specific Schemas

#### MinecraftSpawnPayload
```python
class MinecraftSpawnPayload(BaseEventPayload):
    data: Dict[str, Any] = Field(..., description="Spawn event data")
    
    # Expected data fields:
    # - spawned: bool
    # - position: PositionModel
    # - time: float
```

#### MinecraftChatPayload
```python
class MinecraftChatPayload(BaseEventPayload):
    data: Dict[str, Any] = Field(..., description="Chat event data")
    
    # Expected data fields:
    # - message: str
    # - player: PlayerModel
    # - channel: str
```

## Configuration

### Environment Variables

```bash
# Core Settings
EVENT_BRIDGE_ENABLED=true
EVENT_BRIDGE_MAX_QUEUE_SIZE=10000
EVENT_BRIDGE_WORKER_COUNT=3
EVENT_BRIDGE_BATCH_SIZE=50

# Filtering
EVENT_BRIDGE_DEFAULT_PRIORITY=50
EVENT_BRIDGE_FREQUENCY_LIMIT=1000

# Monitoring
EVENT_BRIDGE_METRICS_ENABLED=true
EVENT_BRIDGE_TRACING_ENABLED=true
EVENT_BRIDGE_TRACING_SAMPLE_RATE=0.1
EVENT_BRIDGE_PROFILING_ENABLED=false

# Compression
EVENT_BRIDGE_COMPRESSION_ENABLED=true
EVENT_BRIDGE_COMPRESSION_ALGORITHM=lz4
EVENT_BRIDGE_COMPRESSION_THRESHOLD=1024

# Circuit Breaker
EVENT_BRIDGE_FAILURE_THRESHOLD=5
EVENT_BRIDGE_TIMEOUT_SECONDS=30
```

### Configuration Class

```python
from dataclasses import dataclass

@dataclass
class EventBridgeConfig:
    enabled: bool = True
    max_queue_size: int = 10000
    worker_count: int = 3
    batch_size: int = 50
    
    # Filtering
    default_priority: int = 50
    frequency_limit: float = 1000.0
    
    # Monitoring
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    tracing_sample_rate: float = 0.1
    profiling_enabled: bool = False
    
    # Compression
    compression_enabled: bool = True
    compression_algorithm: str = "lz4"
    compression_threshold: int = 1024
    
    # Circuit Breaker
    failure_threshold: int = 5
    timeout_seconds: float = 30.0
```

## Global Functions

### Initialization

```python
from src.bridge.event_bridge import initialize_event_bridge, shutdown_event_bridge

# Initialize the event bridge system
await initialize_event_bridge(
    agent=my_adk_agent,
    config=EventBridgeConfig(),
    enable_monitoring=True
)

# Shutdown gracefully
await shutdown_event_bridge()
```

### Monitoring Globals

```python
from src.bridge.event_bridge import (
    get_metrics_collector,
    get_tracer, 
    get_profiler,
    start_monitoring,
    stop_monitoring
)

# Get global instances
metrics = get_metrics_collector()
tracer = get_tracer()
profiler = get_profiler()

# Start/stop monitoring
await start_monitoring()
await stop_monitoring()
```

### Event Decorators

```python
from src.bridge.event_bridge import minecraft_event, priority_event_handler

@minecraft_event("minecraft:custom", priority=80)
async def handle_custom_event(event_data):
    """Handle custom event with priority 80."""
    return {"processed": True}

@priority_event_handler(priority=90)
async def high_priority_handler(event_data):
    """High priority event handler."""
    return {"urgent": True}
```

## Error Handling

### Exception Types

```python
class EventBridgeError(Exception):
    """Base exception for event bridge errors."""
    pass

class ValidationError(EventBridgeError):
    """Event validation failed."""
    pass

class QueueFullError(EventBridgeError):
    """Event queue is full."""
    pass

class CircuitBreakerOpenError(EventBridgeError):
    """Circuit breaker is open."""
    pass

class CompressionError(EventBridgeError):
    """Compression/decompression failed."""
    pass
```

### Error Handling Example

```python
try:
    await queue.add_event(event_data, priority=100)
except QueueFullError:
    # Handle queue full condition
    logger.warning("Event queue is full, dropping event")
except ValidationError as e:
    # Handle validation error
    logger.error(f"Event validation failed: {e}")
except Exception as e:
    # Handle unexpected errors
    logger.error(f"Unexpected error: {e}")
```

## Best Practices

### Performance Optimization

1. **Use Batching**: Process events in batches for better throughput
2. **Configure Filters**: Use event filters to reduce processing load
3. **Enable Compression**: Use compression for large payloads
4. **Monitor Metrics**: Track performance metrics and adjust configuration

### Error Handling

1. **Use Circuit Breakers**: Protect against cascade failures
2. **Implement Retry Logic**: Use exponential backoff for transient failures
3. **Monitor Error Rates**: Track and alert on error patterns
4. **Graceful Degradation**: Provide fallback mechanisms

### Monitoring

1. **Enable Tracing**: Use distributed tracing for debugging
2. **Profile Performance**: Use profiling to identify bottlenecks
3. **Set Up Dashboards**: Monitor system health with real-time dashboards
4. **Configure Alerts**: Set up alerts for critical metrics

### Configuration

1. **Environment-Based Config**: Use environment variables for deployment-specific settings
2. **Validate Configuration**: Validate configuration at startup
3. **Document Defaults**: Clearly document default values and their implications
4. **Version Configuration**: Track configuration changes with version control