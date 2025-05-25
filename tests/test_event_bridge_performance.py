"""
Performance tests for the Event Bridge system.

This test suite validates the performance characteristics and scalability
of the event bridge implementation under various load conditions.
"""

import pytest
import asyncio
import time
import json
import random
from unittest.mock import Mock, AsyncMock
import statistics
from pathlib import Path
import tempfile
import shutil

# Import event bridge components
from src.bridge.event_bridge import (
    EventRegistry,
    PriorityEventQueue,
    EventFilterManager,
    EventCompressor,
    EventMetricsCollector,
    EventTracer,
    PerformanceProfiler
)


class TestEventQueuePerformance:
    """Performance tests for the event queue."""
    
    def setup_method(self):
        self.queue = PriorityEventQueue(max_size=10000)
    
    @pytest.mark.asyncio
    async def test_high_volume_event_insertion(self):
        """Test inserting high volume of events."""
        num_events = 1000
        start_time = time.time()
        
        # Insert events with random priorities
        for i in range(num_events):
            event_data = {
                'eventType': f'minecraft:test{i % 10}',
                'timestamp': time.time(),
                'source': 'perf_test',
                'data': {'index': i}
            }
            priority = random.randint(1, 100)
            await self.queue.add_event(event_data, priority=priority)
        
        insertion_time = time.time() - start_time
        
        # Verify all events were added
        assert self.queue.size() == num_events
        
        # Performance assertion: should handle 1000 events in reasonable time
        events_per_second = num_events / insertion_time
        print(f"Event insertion rate: {events_per_second:.2f} events/second")
        assert events_per_second > 500  # Should handle at least 500 events/second
    
    @pytest.mark.asyncio
    async def test_priority_queue_ordering_performance(self):
        """Test priority ordering performance with large queues."""
        num_events = 5000
        
        # Add events with random priorities
        for i in range(num_events):
            priority = random.randint(1, 1000)
            event_data = {'eventType': 'test', 'priority': priority, 'index': i}
            await self.queue.add_event(event_data, priority=priority)
        
        # Measure time to extract events in priority order
        start_time = time.time()
        extracted_priorities = []
        
        while self.queue.size() > 0:
            event = await self.queue.get_next_event()
            extracted_priorities.append(event.priority)
        
        extraction_time = time.time() - start_time
        
        # Verify ordering (highest priority first)
        for i in range(1, len(extracted_priorities)):
            assert extracted_priorities[i] <= extracted_priorities[i-1]
        
        # Performance assertion
        events_per_second = num_events / extraction_time
        print(f"Event extraction rate: {events_per_second:.2f} events/second")
        assert events_per_second > 1000  # Should handle at least 1000 events/second
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self):
        """Test batch processing performance."""
        num_events = 2000
        batch_size = 100
        
        # Fill queue
        for i in range(num_events):
            event_data = {'eventType': 'batch_test', 'index': i}
            await self.queue.add_event(event_data, priority=50)
        
        # Measure batch processing performance
        start_time = time.time()
        total_processed = 0
        
        while self.queue.size() > 0:
            batch = await self.queue.get_batch(size=batch_size)
            total_processed += len(batch)
            
            # Simulate batch processing
            await asyncio.sleep(0.001)  # 1ms processing per batch
        
        processing_time = time.time() - start_time
        
        assert total_processed == num_events
        
        events_per_second = num_events / processing_time
        print(f"Batch processing rate: {events_per_second:.2f} events/second")
        assert events_per_second > 5000  # Should be very fast with batching


class TestEventFilteringPerformance:
    """Performance tests for event filtering."""
    
    def setup_method(self):
        self.filter_manager = EventFilterManager()
    
    def test_filter_chain_performance(self):
        """Test performance of complex filter chains."""
        # Create a complex filter chain
        type_filter = self.filter_manager.create_event_type_filter([
            'minecraft:spawn', 'minecraft:chat', 'minecraft:position'
        ])
        priority_filter = self.filter_manager.create_priority_filter(min_priority=25)
        frequency_filter = self.filter_manager.create_frequency_filter(max_events_per_second=100)
        
        filter_chain = self.filter_manager.create_filter_chain([
            type_filter, priority_filter, frequency_filter
        ])
        
        # Generate test events
        num_events = 10000
        events = []
        for i in range(num_events):
            event = {
                'eventType': random.choice([
                    'minecraft:spawn', 'minecraft:chat', 'minecraft:position', 
                    'minecraft:inventory', 'minecraft:health'
                ]),
                'priority': random.randint(1, 100),
                'timestamp': time.time() + (i * 0.001),
                'data': {'index': i}
            }
            events.append(event)
        
        # Measure filtering performance
        start_time = time.time()
        filtered_events = []
        
        for event in events:
            if filter_chain.should_process(event):
                filtered_events.append(event)
        
        filtering_time = time.time() - start_time
        
        events_per_second = num_events / filtering_time
        print(f"Filter chain rate: {events_per_second:.2f} events/second")
        print(f"Filtered: {len(filtered_events)}/{num_events} events")
        
        # Should handle at least 10,000 events/second through filter chain
        assert events_per_second > 10000
    
    def test_frequency_filter_performance(self):
        """Test frequency filter performance under high load."""
        freq_filter = self.filter_manager.create_frequency_filter(
            max_events_per_second=1000
        )
        
        num_events = 5000
        current_time = time.time()
        
        # Test rapid event filtering
        start_time = time.time()
        passed_events = 0
        
        for i in range(num_events):
            event = {
                'eventType': 'minecraft:position',
                'timestamp': current_time + (i * 0.0001),  # Very high frequency
                'data': {'index': i}
            }
            
            if freq_filter.should_process(event):
                passed_events += 1
        
        filtering_time = time.time() - start_time
        
        events_per_second = num_events / filtering_time
        print(f"Frequency filter rate: {events_per_second:.2f} events/second")
        print(f"Passed: {passed_events}/{num_events} events")
        
        # Should process at very high rate
        assert events_per_second > 50000
        
        # Should properly limit based on frequency
        assert passed_events <= 1000  # Rate limit should work


class TestCompressionPerformance:
    """Performance tests for event compression."""
    
    def setup_method(self):
        self.compressor = EventCompressor()
    
    def test_compression_algorithms_performance(self):
        """Test performance of different compression algorithms."""
        # Create large test data
        large_event = {
            'eventType': 'minecraft:inventory',
            'timestamp': time.time(),
            'source': 'perf_test',
            'data': {
                'items': [
                    {
                        'type': f'item_{i}',
                        'count': random.randint(1, 64),
                        'metadata': {
                            'description': f'Item description {i}' * 10,
                            'properties': {f'prop_{j}': f'value_{j}' for j in range(20)}
                        }
                    }
                    for i in range(1000)
                ]
            }
        }
        
        algorithms = ['lz4', 'gzip', 'zlib']
        results = {}
        
        for algorithm in algorithms:
            # Test compression performance
            start_time = time.time()
            compressed = self.compressor.compress(large_event, algorithm=algorithm)
            compression_time = time.time() - start_time
            
            # Test decompression performance
            start_time = time.time()
            decompressed = self.compressor.decompress(compressed, algorithm=algorithm)
            decompression_time = time.time() - start_time
            
            # Verify correctness
            assert decompressed == large_event
            
            # Calculate metrics
            original_size = len(json.dumps(large_event))
            compressed_size = len(compressed)
            compression_ratio = self.compressor.calculate_compression_ratio(
                original_size, compressed_size
            )
            
            results[algorithm] = {
                'compression_time': compression_time,
                'decompression_time': decompression_time,
                'compression_ratio': compression_ratio,
                'compressed_size': compressed_size
            }
            
            print(f"{algorithm.upper()} Results:")
            print(f"  Compression time: {compression_time:.4f}s")
            print(f"  Decompression time: {decompression_time:.4f}s")
            print(f"  Compression ratio: {compression_ratio:.3f}")
            print(f"  Size: {original_size} -> {compressed_size} bytes")
        
        # Performance assertions
        for algorithm, result in results.items():
            # Should compress/decompress reasonably fast
            assert result['compression_time'] < 1.0
            assert result['decompression_time'] < 0.5
            assert result['compression_ratio'] < 0.8  # At least 20% compression
    
    def test_batch_compression_performance(self):
        """Test batch compression performance."""
        # Create batch of events
        num_events = 100
        events = []
        
        for i in range(num_events):
            event = {
                'eventType': 'minecraft:chat',
                'timestamp': time.time() + i,
                'source': f'player_{i % 10}',
                'data': {
                    'message': f'Message {i}: ' + ('Hello world! ' * 20),
                    'metadata': {f'key_{j}': f'value_{j}' for j in range(10)}
                }
            }
            events.append(event)
        
        # Test batch compression
        start_time = time.time()
        compressed_batch = self.compressor.compress_batch(events, algorithm='lz4')
        compression_time = time.time() - start_time
        
        # Test batch decompression
        start_time = time.time()
        decompressed_batch = self.compressor.decompress_batch(compressed_batch, algorithm='lz4')
        decompression_time = time.time() - start_time
        
        # Verify correctness
        assert decompressed_batch == events
        
        # Calculate performance
        events_per_second_compression = num_events / compression_time
        events_per_second_decompression = num_events / decompression_time
        
        print(f"Batch compression: {events_per_second_compression:.2f} events/second")
        print(f"Batch decompression: {events_per_second_decompression:.2f} events/second")
        
        # Should handle reasonable throughput
        assert events_per_second_compression > 1000
        assert events_per_second_decompression > 2000


class TestMetricsPerformance:
    """Performance tests for metrics collection."""
    
    def setup_method(self):
        self.metrics = EventMetricsCollector()
    
    def test_high_volume_metrics_collection(self):
        """Test metrics collection under high event volume."""
        num_events = 10000
        event_types = ['minecraft:position', 'minecraft:chat', 'minecraft:inventory']
        
        start_time = time.time()
        
        # Record metrics for high volume of events
        for i in range(num_events):
            event_type = random.choice(event_types)
            tracking_id = self.metrics.record_event_start(event_type)
            
            # Simulate processing time
            processing_time = random.uniform(0.001, 0.010)
            
            if random.random() < 0.95:  # 95% success rate
                self.metrics.record_event_success(event_type, tracking_id, processing_time)
            else:
                error = Exception("Test error")
                self.metrics.record_event_error(event_type, tracking_id, error)
        
        collection_time = time.time() - start_time
        
        # Verify metrics were collected
        system_metrics = self.metrics.get_system_metrics()
        assert system_metrics.total_events_processed == num_events
        
        # Check individual event metrics
        for event_type in event_types:
            event_metrics = self.metrics.get_event_metrics(event_type)
            assert event_metrics.total_count > 0
        
        # Performance assertion
        events_per_second = num_events / collection_time
        print(f"Metrics collection rate: {events_per_second:.2f} events/second")
        assert events_per_second > 5000  # Should handle at least 5000 events/second
    
    def test_metrics_aggregation_performance(self):
        """Test performance of metrics aggregation operations."""
        # Generate substantial metrics data
        event_types = [f'minecraft:event_{i}' for i in range(50)]
        
        for event_type in event_types:
            for _ in range(100):
                tracking_id = self.metrics.record_event_start(event_type)
                processing_time = random.uniform(0.001, 0.100)
                self.metrics.record_event_success(event_type, tracking_id, processing_time)
        
        # Test aggregation performance
        start_time = time.time()
        
        # Perform various aggregation operations
        top_by_volume = self.metrics.get_top_events_by_volume(limit=10)
        top_by_errors = self.metrics.get_top_events_by_errors(limit=10)
        slowest_events = self.metrics.get_slowest_events(limit=10)
        system_metrics = self.metrics.get_system_metrics()
        
        aggregation_time = time.time() - start_time
        
        # Verify results
        assert len(top_by_volume) == 10
        assert len(slowest_events) > 0
        assert system_metrics.total_events_processed > 0
        
        print(f"Metrics aggregation time: {aggregation_time:.4f}s")
        assert aggregation_time < 0.1  # Should aggregate quickly


class TestTracingPerformance:
    """Performance tests for event tracing."""
    
    def setup_method(self):
        self.tracer = EventTracer()
        self.tracer.sample_rate = 1.0  # Trace everything for performance testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.tracer.output_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_trace_creation_performance(self):
        """Test performance of creating and managing traces."""
        from src.bridge.event_bridge.tracing import SpanType
        
        num_traces = 1000
        start_time = time.time()
        
        traces = []
        for i in range(num_traces):
            span = self.tracer.start_trace(
                f'operation_{i}',
                SpanType.EVENT_PROCESSING,
                {'eventType': f'minecraft:event_{i}'}
            )
            
            # Add some child spans
            for j in range(3):
                child_span = self.tracer.start_child_span(
                    span, f'child_operation_{j}', SpanType.VALIDATION
                )
                # Simulate work
                time.sleep(0.0001)
                self.tracer.finish_span(child_span)
            
            self.tracer.finish_span(span)
            traces.append(span)
        
        creation_time = time.time() - start_time
        
        # Verify traces were created
        assert len(self.tracer.completed_traces) == num_traces
        
        traces_per_second = num_traces / creation_time
        print(f"Trace creation rate: {traces_per_second:.2f} traces/second")
        assert traces_per_second > 100  # Should handle at least 100 traces/second
    
    def test_trace_search_performance(self):
        """Test performance of trace search operations."""
        from src.bridge.event_bridge.tracing import SpanType
        
        # Create diverse traces for searching
        num_traces = 500
        operation_names = ['fast_op', 'slow_op', 'medium_op']
        
        for i in range(num_traces):
            operation = random.choice(operation_names)
            span = self.tracer.start_trace(operation, SpanType.EVENT_PROCESSING)
            
            # Simulate different processing times
            if operation == 'slow_op':
                time.sleep(0.002)
            elif operation == 'medium_op':
                time.sleep(0.001)
            else:
                time.sleep(0.0005)
            
            # Random errors
            error = Exception("Test error") if random.random() < 0.1 else None
            self.tracer.finish_span(span, error)
        
        # Test search performance
        start_time = time.time()
        
        # Perform various searches
        slow_traces = self.tracer.search_traces(min_duration_ms=1.5, limit=50)
        error_traces = self.tracer.search_traces(has_error=True, limit=50)
        fast_traces = self.tracer.search_traces(
            operation_name='fast_op', max_duration_ms=1.0, limit=50
        )
        
        search_time = time.time() - start_time
        
        print(f"Trace search time: {search_time:.4f}s")
        print(f"Found slow traces: {len(slow_traces)}")
        print(f"Found error traces: {len(error_traces)}")
        print(f"Found fast traces: {len(fast_traces)}")
        
        assert search_time < 0.1  # Should search quickly


class TestProfilingPerformance:
    """Performance tests for the profiling system itself."""
    
    def setup_method(self):
        self.profiler = PerformanceProfiler()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.profiler.output_dir = self.temp_dir
        self.profiler.profile_threshold_ms = 0  # Profile everything for testing
    
    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_profiling_overhead(self):
        """Test overhead of profiling on normal operations."""
        def test_operation():
            # Simple operation to measure
            total = 0
            for i in range(1000):
                total += i * i
            return total
        
        # Measure without profiling
        start_time = time.time()
        for _ in range(100):
            result = test_operation()
        baseline_time = time.time() - start_time
        
        # Measure with profiling
        start_time = time.time()
        for i in range(100):
            with self.profiler.profile_cpu(f'test_operation_{i}'):
                result = test_operation()
        profiled_time = time.time() - start_time
        
        overhead_ratio = (profiled_time - baseline_time) / baseline_time
        
        print(f"Baseline time: {baseline_time:.4f}s")
        print(f"Profiled time: {profiled_time:.4f}s")
        print(f"Overhead ratio: {overhead_ratio:.2%}")
        
        # Profiling overhead should be reasonable (< 50%)
        assert overhead_ratio < 0.5
    
    def test_memory_snapshot_performance(self):
        """Test performance of memory snapshots."""
        self.profiler.enable_memory_tracking()
        
        num_snapshots = 100
        start_time = time.time()
        
        snapshots = []
        for i in range(num_snapshots):
            # Create some objects between snapshots
            data = [list(range(100)) for _ in range(10)]
            
            snapshot = self.profiler.take_memory_snapshot()
            snapshots.append(snapshot)
        
        snapshot_time = time.time() - start_time
        
        snapshots_per_second = num_snapshots / snapshot_time
        print(f"Memory snapshot rate: {snapshots_per_second:.2f} snapshots/second")
        
        # Should be able to take snapshots quickly
        assert snapshots_per_second > 50
        assert len(snapshots) == num_snapshots
        
        self.profiler.disable_memory_tracking()


class TestIntegratedPerformance:
    """Integrated performance tests simulating real-world scenarios."""
    
    def setup_method(self):
        """Set up complete event bridge system."""
        self.queue = PriorityEventQueue(max_size=10000)
        self.filter_manager = EventFilterManager()
        self.compressor = EventCompressor()
        self.metrics = EventMetricsCollector()
        
        # Set up realistic filters
        self.event_filter = self.filter_manager.create_event_type_filter([
            'minecraft:spawn', 'minecraft:chat', 'minecraft:position', 
            'minecraft:inventory', 'minecraft:health'
        ])
        self.frequency_filter = self.filter_manager.create_frequency_filter(
            max_events_per_second=500
        )
        self.filter_chain = self.filter_manager.create_filter_chain([
            self.event_filter, self.frequency_filter
        ])
    
    @pytest.mark.asyncio
    async def test_realistic_minecraft_event_load(self):
        """Test performance under realistic Minecraft event load."""
        # Simulate realistic event distribution
        event_patterns = {
            'minecraft:position': {'frequency': 0.4, 'priority': 10},
            'minecraft:chat': {'frequency': 0.2, 'priority': 80},
            'minecraft:inventory': {'frequency': 0.15, 'priority': 50},
            'minecraft:health': {'frequency': 0.1, 'priority': 90},
            'minecraft:spawn': {'frequency': 0.05, 'priority': 100},
            'minecraft:death': {'frequency': 0.02, 'priority': 100},
            'minecraft:block_break': {'frequency': 0.08, 'priority': 30}
        }
        
        num_events = 5000
        events_processed = 0
        events_filtered = 0
        compression_time = 0
        
        start_time = time.time()
        
        for i in range(num_events):
            # Generate realistic event
            event_type = random.choices(
                list(event_patterns.keys()),
                weights=[p['frequency'] for p in event_patterns.values()]
            )[0]
            
            event_data = {
                'eventType': event_type,
                'timestamp': time.time() + (i * 0.001),
                'source': f'bot_{random.randint(1, 5)}',
                'eventId': f'event_{i}',
                'data': self._generate_realistic_event_data(event_type)
            }
            
            priority = event_patterns[event_type]['priority']
            
            # Apply filters
            if self.filter_chain.should_process(event_data):
                # Record metrics
                tracking_id = self.metrics.record_event_start(event_type)
                
                # Add to queue
                await self.queue.add_event(event_data, priority=priority)
                
                # Simulate compression for large events
                if len(json.dumps(event_data)) > 500:
                    compress_start = time.time()
                    compressed = self.compressor.compress(event_data, algorithm='lz4')
                    compression_time += time.time() - compress_start
                
                # Record success
                processing_time = random.uniform(0.001, 0.010)
                self.metrics.record_event_success(event_type, tracking_id, processing_time)
                
                events_processed += 1
            else:
                events_filtered += 1
        
        total_time = time.time() - start_time
        
        # Process remaining events in queue
        queue_process_start = time.time()
        processed_from_queue = 0
        
        while self.queue.size() > 0:
            batch = await self.queue.get_batch(size=50)
            processed_from_queue += len(batch)
            await asyncio.sleep(0.001)  # Simulate processing
        
        queue_process_time = time.time() - queue_process_start
        
        # Calculate performance metrics
        total_events_per_second = num_events / total_time
        processed_events_per_second = events_processed / total_time
        queue_throughput = processed_from_queue / queue_process_time if queue_process_time > 0 else 0
        
        print(f"\nRealistic Load Test Results:")
        print(f"Total events: {num_events}")
        print(f"Events processed: {events_processed}")
        print(f"Events filtered: {events_filtered}")
        print(f"Total processing rate: {total_events_per_second:.2f} events/second")
        print(f"Processed events rate: {processed_events_per_second:.2f} events/second")
        print(f"Queue throughput: {queue_throughput:.2f} events/second")
        print(f"Compression time: {compression_time:.4f}s")
        
        # Get metrics summary
        system_metrics = self.metrics.get_system_metrics()
        print(f"Total events processed by metrics: {system_metrics.total_events_processed}")
        
        # Performance assertions for realistic Minecraft server load
        assert total_events_per_second > 1000  # Should handle 1000+ events/second
        assert processed_events_per_second > 500  # Should process 500+ valid events/second
        assert queue_throughput > 1000  # Queue should drain quickly
        assert compression_time < 1.0  # Compression shouldn't be bottleneck
    
    def _generate_realistic_event_data(self, event_type: str) -> dict:
        """Generate realistic event data for different event types."""
        if event_type == 'minecraft:position':
            return {
                'position': {
                    'x': random.uniform(-1000, 1000),
                    'y': random.uniform(0, 256),
                    'z': random.uniform(-1000, 1000)
                },
                'velocity': {
                    'x': random.uniform(-5, 5),
                    'y': random.uniform(-5, 5),
                    'z': random.uniform(-5, 5)
                }
            }
        elif event_type == 'minecraft:chat':
            return {
                'message': f'Chat message {random.randint(1, 1000)}',
                'player': f'Player_{random.randint(1, 20)}',
                'channel': random.choice(['global', 'local', 'team'])
            }
        elif event_type == 'minecraft:inventory':
            return {
                'items': [
                    {
                        'type': f'minecraft:{random.choice(["dirt", "stone", "wood", "iron", "diamond"])}',
                        'count': random.randint(1, 64),
                        'slot': i
                    }
                    for i in range(random.randint(5, 20))
                ]
            }
        elif event_type == 'minecraft:health':
            return {
                'health': random.randint(1, 20),
                'food': random.randint(0, 20),
                'saturation': random.uniform(0, 20)
            }
        else:
            return {'value': random.randint(1, 100)}


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])