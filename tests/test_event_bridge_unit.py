"""
Unit tests for individual Event Bridge components.
"""

import pytest
import asyncio
import time
import sys
from unittest.mock import Mock, MagicMock
from pathlib import Path

# Mock external dependencies before importing
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()  
sys.modules['google.cloud.adk'] = MagicMock()

# Import after mocking
from src.bridge.event_bridge.event_registry import EventRegistry, EventMetadata
from src.bridge.event_bridge.payload_schemas import BaseEventPayload, PayloadValidator
from src.bridge.event_bridge.event_queue import PriorityEventQueue
from src.bridge.event_bridge.compression import EventCompressor
from src.bridge.event_bridge.event_filters import EventFilterManager


class TestEventRegistry:
    """Test the event registry functionality."""
    
    def test_create_registry(self):
        """Test creating an event registry."""
        registry = EventRegistry()
        assert registry is not None
        
        # Should have default events
        event_types = registry.list_event_types()
        assert len(event_types) > 0
        assert 'minecraft:spawn' in event_types
    
    def test_register_custom_event(self):
        """Test registering a custom event type."""
        registry = EventRegistry()
        
        metadata = EventMetadata(
            description='Custom test event',
            payload_schema=BaseEventPayload,
            adk_state_mapping={'custom.value': 'value'},
            priority=75
        )
        
        registry.register_event('test:custom', metadata)
        
        # Verify registration
        assert 'test:custom' in registry.list_event_types()
        retrieved = registry.get_event_metadata('test:custom')
        assert retrieved.description == 'Custom test event'
        assert retrieved.priority == 75


class TestPayloadValidation:
    """Test payload validation functionality."""
    
    def test_validator_creation(self):
        """Test creating a payload validator."""
        validator = PayloadValidator()
        assert validator is not None
    
    def test_valid_payload(self):
        """Test validation of a valid payload."""
        validator = PayloadValidator()
        
        payload = {
            'eventType': 'minecraft:spawn',
            'timestamp': time.time(),
            'source': 'test_bot',
            'eventId': 'test_123',
            'data': {'spawned': True}
        }
        
        is_valid, errors = validator.validate_payload(payload, BaseEventPayload)
        assert is_valid
        assert len(errors) == 0
    
    def test_invalid_payload(self):
        """Test validation of an invalid payload."""
        validator = PayloadValidator()
        
        # Missing required fields
        payload = {
            'eventType': 'minecraft:spawn',
            'data': {'spawned': True}
        }
        
        is_valid, errors = validator.validate_payload(payload, BaseEventPayload)
        assert not is_valid
        assert len(errors) > 0


class TestEventQueue:
    """Test the priority event queue."""
    
    @pytest.mark.asyncio
    async def test_queue_creation(self):
        """Test creating an event queue."""
        queue = PriorityEventQueue(max_size=100)
        assert queue.size() == 0
        assert queue.max_size == 100
    
    @pytest.mark.asyncio
    async def test_add_single_event(self):
        """Test adding a single event to the queue."""
        queue = PriorityEventQueue(max_size=100)
        
        event_data = {
            'eventType': 'minecraft:test',
            'timestamp': time.time(),
            'source': 'test_bot',
            'data': {'test': True}
        }
        
        await queue.add_event(event_data, priority=50)
        assert queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that events are processed in priority order."""
        queue = PriorityEventQueue(max_size=100)
        
        # Add events in mixed priority order
        await queue.add_event({'eventType': 'low', 'data': {}}, priority=10)
        await queue.add_event({'eventType': 'high', 'data': {}}, priority=100) 
        await queue.add_event({'eventType': 'medium', 'data': {}}, priority=50)
        
        # Should get high priority first
        event1 = await queue.get_next_event()
        assert event1.event_data['eventType'] == 'high'
        assert event1.priority == 100
        
        # Then medium
        event2 = await queue.get_next_event()
        assert event2.event_data['eventType'] == 'medium'
        assert event2.priority == 50
        
        # Then low
        event3 = await queue.get_next_event()
        assert event3.event_data['eventType'] == 'low'
        assert event3.priority == 10


class TestEventFiltering:
    """Test event filtering functionality."""
    
    def test_filter_manager_creation(self):
        """Test creating a filter manager."""
        filter_manager = EventFilterManager()
        assert filter_manager is not None
    
    def test_event_type_filter(self):
        """Test filtering by event type."""
        filter_manager = EventFilterManager()
        
        # Create filter for specific event types
        event_filter = filter_manager.create_event_type_filter(['minecraft:spawn', 'minecraft:chat'])
        
        # Test matching events
        spawn_event = {'eventType': 'minecraft:spawn', 'data': {}}
        chat_event = {'eventType': 'minecraft:chat', 'data': {}}
        inventory_event = {'eventType': 'minecraft:inventory', 'data': {}}
        
        assert event_filter.should_process(spawn_event)
        assert event_filter.should_process(chat_event)
        assert not event_filter.should_process(inventory_event)
    
    def test_priority_filter(self):
        """Test filtering by priority."""
        filter_manager = EventFilterManager()
        
        # Create filter for high priority events
        priority_filter = filter_manager.create_priority_filter(min_priority=50)
        
        high_event = {'priority': 100}
        medium_event = {'priority': 50}
        low_event = {'priority': 10}
        
        assert priority_filter.should_process(high_event)
        assert priority_filter.should_process(medium_event)  # Should include min_priority
        assert not priority_filter.should_process(low_event)


class TestEventCompression:
    """Test event compression functionality."""
    
    def test_compressor_creation(self):
        """Test creating an event compressor."""
        compressor = EventCompressor()
        assert compressor is not None
    
    def test_lz4_compression(self):
        """Test LZ4 compression and decompression."""
        compressor = EventCompressor()
        
        test_data = {
            'eventType': 'minecraft:test',
            'data': {'message': 'Hello world! ' * 50}  # Make it compressible
        }
        
        # Compress and decompress
        compressed = compressor.compress(test_data, algorithm='lz4')
        decompressed = compressor.decompress(compressed, algorithm='lz4')
        
        assert decompressed == test_data
        assert len(compressed) < len(str(test_data))  # Should be compressed
    
    def test_gzip_compression(self):
        """Test GZIP compression and decompression."""
        compressor = EventCompressor()
        
        test_data = {
            'eventType': 'minecraft:inventory',
            'data': {'items': [{'type': 'dirt', 'count': 64}] * 100}
        }
        
        # Compress and decompress
        compressed = compressor.compress(test_data, algorithm='gzip')
        decompressed = compressor.decompress(compressed, algorithm='gzip')
        
        assert decompressed == test_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])