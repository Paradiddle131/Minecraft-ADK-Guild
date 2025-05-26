"""
Basic tests for the Event Bridge system that can run without external dependencies.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock the Google ADK import before importing our modules
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.adk'] = MagicMock()

# Now import our components
from src.bridge.event_bridge.event_registry import EventRegistry
from src.bridge.event_bridge.event_queue import PriorityEventQueue
from src.bridge.event_bridge.payload_schemas import BaseEventPayload, PayloadValidator


class TestEventRegistry:
    """Test cases for EventRegistry."""
    
    def setup_method(self):
        self.registry = EventRegistry()
    
    def test_register_event_type(self):
        """Test registering a new event type."""
        from src.bridge.event_bridge.event_registry import EventMetadata
        from src.bridge.event_bridge.payload_schemas import CommonEventPayload
        
        metadata = EventMetadata(
            description='Test event',
            payload_schema=CommonEventPayload,
            adk_state_mapping={'test.value': 'value'},
            priority=100,
            batch_enabled=True
        )
        
        self.registry.register_event('test:event', metadata)
        
        assert 'test:event' in self.registry.events
        retrieved = self.registry.get_event_metadata('test:event')
        assert retrieved.description == 'Test event'
        assert retrieved.priority == 100
    
    def test_get_nonexistent_event_metadata(self):
        """Test retrieving metadata for non-existent event."""
        result = self.registry.get_event_metadata('nonexistent:event')
        assert result is None
    
    def test_list_event_types(self):
        """Test listing all event types."""
        event_types = self.registry.list_event_types()
        
        # Check for key Minecraft events that should be registered by default
        assert 'minecraft:spawn' in event_types
        assert 'minecraft:chat' in event_types
        assert 'minecraft:position' in event_types


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
        from src.bridge.event_bridge.event_filters import EventFilterManager
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])