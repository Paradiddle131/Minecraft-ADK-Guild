"""
Comprehensive tests for the Event Bridge system.

This test suite covers all components of the event bridge implementation
including core functionality, advanced features, and monitoring capabilities.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Import event bridge components
from src.bridge.event_bridge import (
    EventRegistry,
    ADKEventAdapter,
    PriorityEventQueue,
    EventHandlerRegistry,
    EventFilterManager,
    StateSynchronizer,
    EventCompressor,
    CircuitBreaker,
    ConnectionRecoveryManager,
    EventMetricsCollector,
    EventTracer,
    PerformanceProfiler
)
from src.bridge.event_bridge.payload_schemas import (
    BaseEventPayload,
    PayloadValidator
)
from src.bridge.event_bridge.bridge_connector import EventBridgeConnector


class TestEventRegistry:
    """Test cases for EventRegistry."""
    
    def setup_method(self):
        self.registry = EventRegistry()
    
    def test_register_event_type(self):
        """Test registering a new event type."""
        metadata = {
            'description': 'Test event',
            'priority': 100,
            'batching_enabled': True
        }
        
        self.registry.register_event_type('test:event', metadata)
        
        assert 'test:event' in self.registry.events
        assert self.registry.events['test:event']['description'] == 'Test event'
        assert self.registry.events['test:event']['priority'] == 100
    
    def test_get_event_metadata(self):
        """Test retrieving event metadata."""
        metadata = {'description': 'Test event', 'priority': 50}
        self.registry.register_event_type('test:event', metadata)
        
        retrieved = self.registry.get_event_metadata('test:event')
        assert retrieved['description'] == 'Test event'
        assert retrieved['priority'] == 50
    
    def test_get_nonexistent_event_metadata(self):
        """Test retrieving metadata for non-existent event."""
        result = self.registry.get_event_metadata('nonexistent:event')
        assert result is None
    
    def test_list_event_types(self):
        """Test listing all event types."""
        self.registry.register_event_type('test:event1', {'priority': 100})
        self.registry.register_event_type('test:event2', {'priority': 200})
        
        event_types = self.registry.list_event_types()
        assert 'test:event1' in event_types
        assert 'test:event2' in event_types
    
    def test_default_minecraft_events(self):
        """Test that default Minecraft events are registered."""
        event_types = self.registry.list_event_types()
        
        # Check for key Minecraft events
        assert 'minecraft:spawn' in event_types
        assert 'minecraft:chat' in event_types
        assert 'minecraft:position' in event_types
        assert 'minecraft:inventory' in event_types


class TestPayloadValidation:
    """Test cases for payload validation."""
    
    def setup_method(self):
        self.validator = PayloadValidator()
    
    def test_validate_base_payload(self):
        """Test validation of base event payload."""
        payload = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'eventId': 'test_123',
            'data': {'spawned': True}
        }
        
        is_valid, errors = self.validator.validate_payload(payload, BaseEventPayload)
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_invalid_payload(self):
        """Test validation of invalid payload."""
        payload = {
            'eventType': 'minecraft:spawn',
            # Missing required fields
            'data': {'spawned': True}
        }
        
        is_valid, errors = self.validator.validate_payload(payload, BaseEventPayload)
        assert not is_valid
        assert len(errors) > 0
    
    def test_validate_with_extra_fields(self):
        """Test validation with extra fields."""
        payload = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'eventId': 'test_123',
            'data': {'spawned': True},
            'extra_field': 'should_be_allowed'
        }
        
        is_valid, errors = self.validator.validate_payload(payload, BaseEventPayload)
        assert is_valid  # Extra fields should be allowed


class TestEventQueue:
    """Test cases for PriorityEventQueue."""
    
    def setup_method(self):
        self.queue = PriorityEventQueue(max_size=100)
    
    @pytest.mark.asyncio
    async def test_add_event(self):
        """Test adding an event to the queue."""
        event_data = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {'spawned': True}
        }
        
        await self.queue.add_event(event_data, priority=100)
        assert self.queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that events are processed in priority order."""
        # Add events with different priorities
        await self.queue.add_event({'eventType': 'low'}, priority=10)
        await self.queue.add_event({'eventType': 'high'}, priority=100)
        await self.queue.add_event({'eventType': 'medium'}, priority=50)
        
        # Should get high priority first
        event = await self.queue.get_next_event()
        assert event.event_data['eventType'] == 'high'
        
        # Then medium
        event = await self.queue.get_next_event()
        assert event.event_data['eventType'] == 'medium'
        
        # Then low
        event = await self.queue.get_next_event()
        assert event.event_data['eventType'] == 'low'
    
    @pytest.mark.asyncio
    async def test_queue_full_behavior(self):
        """Test behavior when queue is full."""
        small_queue = PriorityEventQueue(max_size=2)
        
        # Fill the queue
        await small_queue.add_event({'eventType': 'event1'}, priority=10)
        await small_queue.add_event({'eventType': 'event2'}, priority=20)
        
        # Should reject additional events
        with pytest.raises(Exception):  # Assuming queue raises exception when full
            await small_queue.add_event({'eventType': 'event3'}, priority=30)
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch event processing."""
        # Add multiple events
        for i in range(5):
            await self.queue.add_event({'eventType': f'event{i}'}, priority=i * 10)
        
        # Get batch of events
        batch = await self.queue.get_batch(size=3)
        assert len(batch) == 3
        
        # Should be in priority order (highest first)
        assert batch[0].event_data['eventType'] == 'event4'  # priority 40
        assert batch[1].event_data['eventType'] == 'event3'  # priority 30
        assert batch[2].event_data['eventType'] == 'event2'  # priority 20


class TestEventFiltering:
    """Test cases for event filtering."""
    
    def setup_method(self):
        self.filter_manager = EventFilterManager()
    
    def test_event_type_filter(self):
        """Test filtering by event type."""
        # Create filter for spawn events only
        spawn_filter = self.filter_manager.create_event_type_filter(['minecraft:spawn'])
        
        spawn_event = {'eventType': 'minecraft:spawn', 'data': {}}
        chat_event = {'eventType': 'minecraft:chat', 'data': {}}
        
        assert spawn_filter.should_process(spawn_event)
        assert not spawn_filter.should_process(chat_event)
    
    def test_priority_filter(self):
        """Test filtering by priority."""
        # Create filter for high priority events (>= 50)
        priority_filter = self.filter_manager.create_priority_filter(min_priority=50)
        
        high_priority_event = {'priority': 100}
        low_priority_event = {'priority': 10}
        
        assert priority_filter.should_process(high_priority_event)
        assert not priority_filter.should_process(low_priority_event)
    
    def test_frequency_filter(self):
        """Test frequency-based filtering."""
        # Create filter that allows max 2 events per second
        freq_filter = self.filter_manager.create_frequency_filter(
            max_events_per_second=2
        )
        
        event = {'eventType': 'minecraft:position', 'timestamp': time.time()}
        
        # First two should pass
        assert freq_filter.should_process(event)
        assert freq_filter.should_process(event)
        
        # Third should be filtered out
        assert not freq_filter.should_process(event)
    
    def test_filter_chain(self):
        """Test chaining multiple filters."""
        # Create a chain: spawn events only + high priority
        type_filter = self.filter_manager.create_event_type_filter(['minecraft:spawn'])
        priority_filter = self.filter_manager.create_priority_filter(min_priority=50)
        
        filter_chain = self.filter_manager.create_filter_chain([type_filter, priority_filter])
        
        # Should pass: spawn + high priority
        valid_event = {
            'eventType': 'minecraft:spawn',
            'priority': 100,
            'data': {}
        }
        assert filter_chain.should_process(valid_event)
        
        # Should fail: spawn + low priority
        invalid_event = {
            'eventType': 'minecraft:spawn',
            'priority': 10,
            'data': {}
        }
        assert not filter_chain.should_process(invalid_event)


class TestStateSynchronization:
    """Test cases for state synchronization."""
    
    def setup_method(self):
        self.state_sync = StateSynchronizer()
    
    @pytest.mark.asyncio
    async def test_update_state(self):
        """Test updating state from event."""
        event_data = {
            'eventType': 'minecraft:spawn',
            'data': {
                'spawned': True,
                'position': {'x': 10, 'y': 64, 'z': 20}
            }
        }
        
        await self.state_sync.update_state_from_event(event_data)
        
        # Check state was updated
        state = self.state_sync.get_current_state()
        assert state.get('minecraft.spawned') == True
        assert state.get('minecraft.position.x') == 10
    
    @pytest.mark.asyncio
    async def test_nested_state_updates(self):
        """Test handling of nested state updates."""
        event_data = {
            'eventType': 'minecraft:inventory',
            'data': {
                'items': [
                    {'type': 'dirt', 'count': 64},
                    {'type': 'stone', 'count': 32}
                ]
            }
        }
        
        await self.state_sync.update_state_from_event(event_data)
        
        state = self.state_sync.get_current_state()
        assert 'minecraft.inventory.items' in state
    
    def test_state_snapshot(self):
        """Test creating state snapshots."""
        # Set some state
        self.state_sync.set_state_value('minecraft.health', 20)
        self.state_sync.set_state_value('minecraft.food', 18)
        
        # Create snapshot
        snapshot = self.state_sync.create_snapshot()
        
        assert snapshot['minecraft.health'] == 20
        assert snapshot['minecraft.food'] == 18
        assert 'timestamp' in snapshot
    
    @pytest.mark.asyncio
    async def test_state_validation(self):
        """Test state validation rules."""
        # Add validation rule for health
        def validate_health(value):
            return 0 <= value <= 20
        
        self.state_sync.add_validation_rule('minecraft.health', validate_health)
        
        # Valid health value should succeed
        assert await self.state_sync.validate_state_update('minecraft.health', 15)
        
        # Invalid health value should fail
        assert not await self.state_sync.validate_state_update('minecraft.health', 25)


class TestCompression:
    """Test cases for event compression."""
    
    def setup_method(self):
        self.compressor = EventCompressor()
    
    def test_lz4_compression(self):
        """Test LZ4 compression."""
        test_data = {'eventType': 'minecraft:chat', 'message': 'Hello world!' * 100}
        
        compressed = self.compressor.compress(test_data, algorithm='lz4')
        decompressed = self.compressor.decompress(compressed, algorithm='lz4')
        
        assert decompressed == test_data
        assert len(compressed) < len(json.dumps(test_data))
    
    def test_gzip_compression(self):
        """Test GZIP compression."""
        test_data = {'eventType': 'minecraft:position', 'positions': list(range(1000))}
        
        compressed = self.compressor.compress(test_data, algorithm='gzip')
        decompressed = self.compressor.decompress(compressed, algorithm='gzip')
        
        assert decompressed == test_data
    
    def test_compression_ratio_calculation(self):
        """Test compression ratio calculation."""
        test_data = {'eventType': 'minecraft:test', 'data': 'x' * 1000}
        
        original_size = len(json.dumps(test_data))
        compressed = self.compressor.compress(test_data, algorithm='lz4')
        ratio = self.compressor.calculate_compression_ratio(original_size, len(compressed))
        
        assert 0 < ratio < 1  # Should have some compression
    
    def test_batch_compression(self):
        """Test batch compression."""
        events = [
            {'eventType': 'minecraft:chat', 'message': f'Message {i}'}
            for i in range(10)
        ]
        
        compressed = self.compressor.compress_batch(events, algorithm='gzip')
        decompressed = self.compressor.decompress_batch(compressed, algorithm='gzip')
        
        assert decompressed == events


class TestCircuitBreaker:
    """Test cases for circuit breaker."""
    
    def setup_method(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=1.0,
            expected_exception=Exception
        )
    
    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test circuit breaker with successful calls."""
        @self.circuit_breaker
        async def successful_function():
            return "success"
        
        # Multiple successful calls should work
        for _ in range(5):
            result = await successful_function()
            assert result == "success"
        
        assert self.circuit_breaker.state == "CLOSED"
    
    @pytest.mark.asyncio
    async def test_failure_threshold(self):
        """Test circuit breaker opening after failures."""
        call_count = 0
        
        @self.circuit_breaker
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Test failure")
        
        # Fail enough times to open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await failing_function()
        
        assert self.circuit_breaker.state == "OPEN"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_open_circuit_blocks_calls(self):
        """Test that open circuit blocks calls."""
        call_count = 0
        
        @self.circuit_breaker
        async def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Test failure")
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await failing_function()
        
        # Next call should be blocked without calling function
        initial_count = call_count
        with pytest.raises(Exception):
            await failing_function()
        
        assert call_count == initial_count  # Function wasn't called
    
    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        call_count = 0
        should_fail = True
        
        @self.circuit_breaker
        async def conditionally_failing_function():
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise Exception("Test failure")
            return "success"
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await conditionally_failing_function()
        
        assert self.circuit_breaker.state == "OPEN"
        
        # Wait for timeout
        await asyncio.sleep(1.1)
        
        # Fix the function
        should_fail = False
        
        # Next call should transition to HALF_OPEN then CLOSED
        result = await conditionally_failing_function()
        assert result == "success"
        assert self.circuit_breaker.state == "CLOSED"


class TestMetricsCollection:
    """Test cases for metrics collection."""
    
    def setup_method(self):
        self.metrics = EventMetricsCollector()
    
    def test_record_event_metrics(self):
        """Test recording event metrics."""
        tracking_id = self.metrics.record_event_start('minecraft:spawn')
        
        # Simulate processing time
        time.sleep(0.1)
        
        self.metrics.record_event_success('minecraft:spawn', tracking_id, 0.1)
        
        event_metrics = self.metrics.get_event_metrics('minecraft:spawn')
        assert event_metrics.total_count == 1
        assert event_metrics.success_count == 1
        assert event_metrics.error_count == 0
        assert event_metrics.avg_processing_time > 0
    
    def test_record_event_errors(self):
        """Test recording event errors."""
        tracking_id = self.metrics.record_event_start('minecraft:chat')
        
        error = Exception("Test error")
        self.metrics.record_event_error('minecraft:chat', tracking_id, error)
        
        event_metrics = self.metrics.get_event_metrics('minecraft:chat')
        assert event_metrics.total_count == 1
        assert event_metrics.success_count == 0
        assert event_metrics.error_count == 1
    
    def test_system_metrics(self):
        """Test system metrics collection."""
        # Set up callbacks for external metrics
        self.metrics.queue_depth_callback = lambda: 5
        self.metrics.memory_callback = lambda: 128.5
        self.metrics.connection_callback = lambda: 2
        
        system_metrics = self.metrics.get_system_metrics()
        
        assert system_metrics.current_queue_depth == 5
        assert system_metrics.memory_usage_mb == 128.5
        assert system_metrics.active_connections == 2
    
    def test_top_events_by_volume(self):
        """Test getting top events by volume."""
        # Record different event volumes
        for _ in range(10):
            tracking_id = self.metrics.record_event_start('minecraft:position')
            self.metrics.record_event_success('minecraft:position', tracking_id, 0.01)
        
        for _ in range(5):
            tracking_id = self.metrics.record_event_start('minecraft:chat')
            self.metrics.record_event_success('minecraft:chat', tracking_id, 0.02)
        
        top_events = self.metrics.get_top_events_by_volume(limit=2)
        
        assert len(top_events) == 2
        assert top_events[0].event_type == 'minecraft:position'  # Highest volume
        assert top_events[0].total_count == 10
        assert top_events[1].event_type == 'minecraft:chat'
        assert top_events[1].total_count == 5


class TestEventTracing:
    """Test cases for event tracing."""
    
    def setup_method(self):
        self.tracer = EventTracer()
        self.tracer.sample_rate = 1.0  # Trace everything for tests
    
    def test_start_trace(self):
        """Test starting a new trace."""
        from src.bridge.event_bridge.tracing import SpanType
        
        span = self.tracer.start_trace(
            'test_operation',
            SpanType.EVENT_PROCESSING,
            {'eventType': 'minecraft:spawn'}
        )
        
        assert span is not None
        assert span.operation_name == 'test_operation'
        assert span.span_type == SpanType.EVENT_PROCESSING
        assert span.trace_id in self.tracer.active_traces
    
    def test_child_spans(self):
        """Test creating child spans."""
        from src.bridge.event_bridge.tracing import SpanType
        
        root_span = self.tracer.start_trace('root_operation', SpanType.EVENT_PROCESSING)
        child_span = self.tracer.start_child_span(
            root_span, 'child_operation', SpanType.VALIDATION
        )
        
        assert child_span.parent_span_id == root_span.span_id
        assert child_span.trace_id == root_span.trace_id
    
    def test_finish_span(self):
        """Test finishing spans."""
        from src.bridge.event_bridge.tracing import SpanType
        
        span = self.tracer.start_trace('test_operation', SpanType.EVENT_PROCESSING)
        
        # Simulate some work
        time.sleep(0.1)
        
        self.tracer.finish_span(span)
        
        assert span.status == "success"
        assert span.duration_ms > 0
        assert span.end_time is not None
    
    def test_trace_with_error(self):
        """Test tracing with errors."""
        from src.bridge.event_bridge.tracing import SpanType
        
        span = self.tracer.start_trace('failing_operation', SpanType.EVENT_PROCESSING)
        
        error = Exception("Test error")
        self.tracer.finish_span(span, error)
        
        assert span.status == "error"
        assert span.error == "Test error"
        assert span.tags.get("error") == True
    
    def test_trace_search(self):
        """Test searching traces."""
        from src.bridge.event_bridge.tracing import SpanType
        
        # Create traces with different characteristics
        span1 = self.tracer.start_trace('fast_operation', SpanType.EVENT_PROCESSING)
        time.sleep(0.05)
        self.tracer.finish_span(span1)
        
        span2 = self.tracer.start_trace('slow_operation', SpanType.EVENT_PROCESSING)
        time.sleep(0.15)
        self.tracer.finish_span(span2)
        
        # Search for slow operations (> 100ms)
        slow_traces = self.tracer.search_traces(
            min_duration_ms=100,
            limit=10
        )
        
        assert len(slow_traces) == 1
        assert slow_traces[0].spans[span2.span_id].operation_name == 'slow_operation'


class TestPerformanceProfiling:
    """Test cases for performance profiling."""
    
    def setup_method(self):
        self.profiler = PerformanceProfiler()
        # Use temp directory for test outputs
        self.temp_dir = Path(tempfile.mkdtemp())
        self.profiler.output_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cpu_profiling(self):
        """Test CPU profiling context manager."""
        def cpu_intensive_work():
            # Simulate CPU work
            total = 0
            for i in range(10000):
                total += i * i
            return total
        
        with self.profiler.profile_cpu('test_cpu_work') as profile_id:
            result = cpu_intensive_work()
        
        assert result > 0
        assert profile_id is not None
        
        # Check that profile was recorded if above threshold
        profiles = [p for p in self.profiler.profile_results if p.profile_id == profile_id]
        # May or may not be recorded depending on execution time vs threshold
    
    def test_memory_profiling(self):
        """Test memory profiling context manager."""
        self.profiler.enable_memory_tracking()
        
        def memory_intensive_work():
            # Create some objects
            data = []
            for i in range(1000):
                data.append({'item': i, 'data': list(range(100))})
            return data
        
        with self.profiler.profile_memory('test_memory_work') as profile_id:
            result = memory_intensive_work()
        
        assert len(result) == 1000
        assert profile_id is not None
        
        self.profiler.disable_memory_tracking()
    
    def test_function_profiling_decorator(self):
        """Test function profiling decorator."""
        @self.profiler.profile_function('decorated_function')
        def test_function(x, y):
            time.sleep(0.01)  # Small delay
            return x + y
        
        result = test_function(5, 3)
        assert result == 8
    
    def test_memory_snapshots(self):
        """Test memory snapshot functionality."""
        snapshot1 = self.profiler.take_memory_snapshot()
        
        # Create some objects
        large_data = [list(range(1000)) for _ in range(100)]
        
        snapshot2 = self.profiler.take_memory_snapshot()
        
        assert snapshot2.timestamp > snapshot1.timestamp
        # Memory usage should have increased
        assert len(self.profiler.memory_snapshots) >= 2
    
    def test_profiling_summary(self):
        """Test getting profiling summary."""
        # Generate some profile data
        tracking_id = self.profiler.get_profiler().metrics.record_event_start('test_event')
        self.profiler.get_profiler().metrics.record_event_success('test_event', tracking_id, 0.1)
        
        summary = self.profiler.get_profile_summary(hours=1)
        
        assert 'profiling' in summary
        assert 'memory' in summary
        assert 'cpu' in summary
        assert 'system' in summary


class TestIntegrationEventBridge:
    """Integration tests for the complete event bridge system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Initialize components
        self.registry = EventRegistry()
        self.queue = PriorityEventQueue(max_size=1000)
        self.filter_manager = EventFilterManager()
        self.state_sync = StateSynchronizer()
        self.metrics = EventMetricsCollector()
        
        # Mock ADK agent
        self.mock_agent = Mock()
        self.mock_agent.run = AsyncMock(return_value=Mock(output_keys={'result': 'success'}))
        
        self.adapter = ADKEventAdapter(agent=self.mock_agent)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_end_to_end_event_processing(self):
        """Test complete event processing pipeline."""
        # Create a test event
        event_data = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'eventId': 'test_spawn_123',
            'data': {
                'spawned': True,
                'position': {'x': 100, 'y': 64, 'z': 200},
                'health': 20
            }
        }
        
        # Add to queue
        await self.queue.add_event(event_data, priority=100)
        
        # Process through adapter
        adk_action = await self.adapter.process_minecraft_event(event_data)
        
        # Verify ADK action was created
        assert adk_action is not None
        assert hasattr(adk_action, 'state_delta')
        
        # Verify state updates
        await self.state_sync.update_state_from_event(event_data)
        state = self.state_sync.get_current_state()
        
        assert state.get('minecraft.spawned') == True
        assert state.get('minecraft.position.x') == 100
        assert state.get('minecraft.health') == 20
    
    @pytest.mark.asyncio
    async def test_event_filtering_integration(self):
        """Test event filtering in the pipeline."""
        # Create filter for high-priority spawn events only
        type_filter = self.filter_manager.create_event_type_filter(['minecraft:spawn'])
        priority_filter = self.filter_manager.create_priority_filter(min_priority=50)
        filter_chain = self.filter_manager.create_filter_chain([type_filter, priority_filter])
        
        # Test events
        valid_event = {
            'eventType': 'minecraft:spawn',
            'priority': 100,
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {'spawned': True}
        }
        
        invalid_event = {
            'eventType': 'minecraft:chat',  # Wrong type
            'priority': 100,
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {'message': 'Hello'}
        }
        
        # Apply filters
        assert filter_chain.should_process(valid_event)
        assert not filter_chain.should_process(invalid_event)
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Create failing adapter
        failing_adapter = ADKEventAdapter(agent=None)  # Will cause errors
        
        # Use circuit breaker
        circuit_breaker = CircuitBreaker(failure_threshold=2, timeout=0.5)
        
        @circuit_breaker
        async def process_with_circuit_breaker(event_data):
            return await failing_adapter.process_minecraft_event(event_data)
        
        event_data = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {'spawned': True}
        }
        
        # Should fail and eventually open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await process_with_circuit_breaker(event_data)
        
        assert circuit_breaker.state == "OPEN"
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self):
        """Test performance monitoring during event processing."""
        # Enable all monitoring
        self.metrics.queue_depth_callback = lambda: self.queue.size()
        
        # Process multiple events and monitor performance
        events = [
            {
                'eventType': f'minecraft:test{i}',
                'timestamp': time.time(),
                'source': 'test_bot',
                'data': {'value': i}
            }
            for i in range(10)
        ]
        
        # Process events and collect metrics
        for event in events:
            tracking_id = self.metrics.record_event_start(event['eventType'])
            
            start_time = time.time()
            await self.queue.add_event(event, priority=50)
            processing_time = time.time() - start_time
            
            self.metrics.record_event_success(event['eventType'], tracking_id, processing_time)
        
        # Verify metrics were collected
        system_metrics = self.metrics.get_system_metrics()
        assert system_metrics.total_events_processed >= 10
        
        top_events = self.metrics.get_top_events_by_volume(limit=5)
        assert len(top_events) > 0
    
    @pytest.mark.asyncio
    async def test_compression_integration(self):
        """Test event compression in the pipeline."""
        compressor = EventCompressor()
        
        # Create large event data
        large_event = {
            'eventType': 'minecraft:inventory',
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {
                'items': [
                    {'type': f'item_{i}', 'count': i, 'metadata': f'data_{i}' * 50}
                    for i in range(100)
                ]
            }
        }
        
        # Test compression
        original_size = len(json.dumps(large_event))
        compressed = compressor.compress(large_event, algorithm='lz4')
        decompressed = compressor.decompress(compressed, algorithm='lz4')
        
        assert decompressed == large_event
        assert len(compressed) < original_size
        
        ratio = compressor.calculate_compression_ratio(original_size, len(compressed))
        assert 0 < ratio < 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])