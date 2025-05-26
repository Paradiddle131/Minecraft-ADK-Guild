"""
Event Filtering System - Advanced filtering and subscription management
"""
import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

import structlog

logger = structlog.get_logger(__name__)


class FilterType(Enum):
    """Types of event filters"""
    EVENT_TYPE = "event_type"
    PRIORITY = "priority"
    FREQUENCY = "frequency"
    CONTENT = "content"
    SOURCE = "source"
    TIME_WINDOW = "time_window"
    CUSTOM = "custom"


@dataclass
class FilterConfig:
    """Configuration for event filters"""
    enabled: bool = True
    log_filtered: bool = False
    allow_bypass: bool = False
    bypass_keywords: List[str] = None
    
    def __post_init__(self):
        if self.bypass_keywords is None:
            self.bypass_keywords = ["critical", "emergency", "spawn", "death"]


class BaseEventFilter(ABC):
    """Base class for all event filters"""
    
    def __init__(self, name: str, config: FilterConfig = None):
        self.name = name
        self.config = config or FilterConfig()
        self.stats = {
            "total_processed": 0,
            "total_passed": 0,
            "total_filtered": 0
        }
    
    @abstractmethod
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Determine if event should be processed"""
        pass
    
    def _update_stats(self, passed: bool):
        """Update filter statistics"""
        self.stats["total_processed"] += 1
        if passed:
            self.stats["total_passed"] += 1
        else:
            self.stats["total_filtered"] += 1
    
    def _check_bypass(self, event_data: Dict[str, Any]) -> bool:
        """Check if event should bypass filter"""
        if not self.config.allow_bypass:
            return False
        
        event_type = event_data.get("event", "").lower()
        for keyword in self.config.bypass_keywords:
            if keyword.lower() in event_type:
                return True
        
        return False
    
    async def filter_event(self, event_data: Dict[str, Any]) -> bool:
        """Main filter method with statistics and bypass logic"""
        if not self.config.enabled:
            self._update_stats(True)
            return True
        
        # Check bypass conditions
        if self._check_bypass(event_data):
            self._update_stats(True)
            return True
        
        # Apply actual filter logic
        should_pass = await self.should_process(event_data)
        self._update_stats(should_pass)
        
        # Log filtered events if configured
        if not should_pass and self.config.log_filtered:
            logger.debug("Event filtered",
                        filter=self.name,
                        event_type=event_data.get("event"),
                        event_id=event_data.get("eventId"))
        
        return should_pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filter statistics"""
        return {
            "name": self.name,
            "enabled": self.config.enabled,
            "stats": self.stats.copy()
        }


class EventTypeFilter(BaseEventFilter):
    """Filter events by type patterns"""
    
    def __init__(self, allowed_types: List[str] = None, blocked_types: List[str] = None, 
                 config: FilterConfig = None):
        super().__init__("event_type", config)
        self.allowed_types = set(allowed_types or [])
        self.blocked_types = set(blocked_types or [])
        self.allowed_patterns = []
        self.blocked_patterns = []
        
        # Compile regex patterns
        for pattern in allowed_types or []:
            if '*' in pattern or '?' in pattern:
                regex = pattern.replace('*', '.*').replace('?', '.')
                self.allowed_patterns.append(re.compile(regex))
        
        for pattern in blocked_types or []:
            if '*' in pattern or '?' in pattern:
                regex = pattern.replace('*', '.*').replace('?', '.')
                self.blocked_patterns.append(re.compile(regex))
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event type is allowed"""
        event_type = event_data.get("event", "")
        
        # Check blocked types first
        if event_type in self.blocked_types:
            return False
        
        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.match(event_type):
                return False
        
        # If no allowed types specified, allow all (except blocked)
        if not self.allowed_types and not self.allowed_patterns:
            return True
        
        # Check allowed types
        if event_type in self.allowed_types:
            return True
        
        # Check allowed patterns
        for pattern in self.allowed_patterns:
            if pattern.match(event_type):
                return True
        
        return False


class PriorityFilter(BaseEventFilter):
    """Filter events by priority level"""
    
    def __init__(self, min_priority: int = 0, max_priority: int = 100, 
                 config: FilterConfig = None):
        super().__init__("priority", config)
        self.min_priority = min_priority
        self.max_priority = max_priority
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event priority is within range"""
        priority = event_data.get("priority", 0)
        return self.min_priority <= priority <= self.max_priority


class FrequencyFilter(BaseEventFilter):
    """Filter events by frequency/rate limiting"""
    
    def __init__(self, max_events_per_second: float = 10.0, 
                 window_size: int = 60, config: FilterConfig = None):
        super().__init__("frequency", config)
        self.max_events_per_second = max_events_per_second
        self.window_size = window_size
        self.event_times = {}  # event_type -> list of timestamps
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event frequency is within limits"""
        import time
        
        event_type = event_data.get("event", "")
        current_time = time.time()
        
        # Initialize tracking for this event type
        if event_type not in self.event_times:
            self.event_times[event_type] = []
        
        times = self.event_times[event_type]
        
        # Remove old timestamps outside window
        cutoff_time = current_time - self.window_size
        times[:] = [t for t in times if t > cutoff_time]
        
        # Check if adding this event would exceed rate limit
        if len(times) >= self.max_events_per_second * self.window_size:
            return False
        
        # Add current timestamp
        times.append(current_time)
        return True


class ContentFilter(BaseEventFilter):
    """Filter events by content patterns"""
    
    def __init__(self, required_fields: List[str] = None, 
                 field_patterns: Dict[str, str] = None,
                 config: FilterConfig = None):
        super().__init__("content", config)
        self.required_fields = required_fields or []
        self.field_patterns = {}
        
        # Compile regex patterns for field values
        for field, pattern in (field_patterns or {}).items():
            self.field_patterns[field] = re.compile(pattern)
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event content matches criteria"""
        data = event_data.get("data", {})
        
        # Check required fields
        for field in self.required_fields:
            if field not in data:
                return False
        
        # Check field patterns
        for field, pattern in self.field_patterns.items():
            value = data.get(field)
            if value is None:
                return False
            
            if not pattern.match(str(value)):
                return False
        
        return True


class SourceFilter(BaseEventFilter):
    """Filter events by source (bot ID, dimension, etc.)"""
    
    def __init__(self, allowed_bots: List[str] = None, 
                 allowed_dimensions: List[str] = None,
                 config: FilterConfig = None):
        super().__init__("source", config)
        self.allowed_bots = set(allowed_bots or [])
        self.allowed_dimensions = set(allowed_dimensions or [])
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event source is allowed"""
        # Check bot ID
        if self.allowed_bots:
            bot_id = event_data.get("botId", "")
            if bot_id not in self.allowed_bots:
                return False
        
        # Check dimension
        if self.allowed_dimensions:
            metadata = event_data.get("metadata", {})
            dimension = metadata.get("dimension", "")
            if dimension and dimension not in self.allowed_dimensions:
                return False
        
        return True


class TimeWindowFilter(BaseEventFilter):
    """Filter events by time windows"""
    
    def __init__(self, start_hour: int = 0, end_hour: int = 24,
                 allowed_days: List[int] = None, config: FilterConfig = None):
        super().__init__("time_window", config)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.allowed_days = set(allowed_days or list(range(7)))  # 0=Monday, 6=Sunday
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Check if event time is within allowed window"""
        import datetime
        
        timestamp = event_data.get("timestamp", 0)
        if timestamp <= 0:
            return True  # Allow events without valid timestamps
        
        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
        
        # Check day of week
        if dt.weekday() not in self.allowed_days:
            return False
        
        # Check hour of day
        if not (self.start_hour <= dt.hour < self.end_hour):
            return False
        
        return True


class CustomFilter(BaseEventFilter):
    """Custom filter with user-defined function"""
    
    def __init__(self, filter_func: Callable[[Dict[str, Any]], bool],
                 name: str = "custom", config: FilterConfig = None):
        super().__init__(name, config)
        self.filter_func = filter_func
    
    async def should_process(self, event_data: Dict[str, Any]) -> bool:
        """Apply custom filter function"""
        try:
            return self.filter_func(event_data)
        except Exception as e:
            logger.error("Custom filter error", 
                        filter_name=self.name, error=str(e))
            return True  # Default to allowing event on error


class EventFilterChain:
    """Chain of filters applied to events"""
    
    def __init__(self):
        self.filters: List[BaseEventFilter] = []
        self.stats = {
            "total_events": 0,
            "events_passed": 0,
            "events_filtered": 0
        }
    
    def add_filter(self, event_filter: BaseEventFilter):
        """Add filter to the chain"""
        self.filters.append(event_filter)
        logger.info("Added filter to chain", 
                   filter_name=event_filter.name,
                   total_filters=len(self.filters))
    
    def remove_filter(self, filter_name: str) -> bool:
        """Remove filter from the chain"""
        for i, f in enumerate(self.filters):
            if f.name == filter_name:
                del self.filters[i]
                logger.info("Removed filter from chain",
                           filter_name=filter_name,
                           remaining_filters=len(self.filters))
                return True
        return False
    
    async def apply_filters(self, event_data: Dict[str, Any]) -> bool:
        """Apply all filters in sequence"""
        self.stats["total_events"] += 1
        
        # Apply each filter
        for event_filter in self.filters:
            if not await event_filter.filter_event(event_data):
                self.stats["events_filtered"] += 1
                return False
        
        self.stats["events_passed"] += 1
        return True
    
    def get_chain_stats(self) -> Dict[str, Any]:
        """Get statistics for the entire filter chain"""
        return {
            "chain_stats": self.stats.copy(),
            "filter_count": len(self.filters),
            "filter_stats": [f.get_stats() for f in self.filters]
        }
    
    def clear_filters(self):
        """Remove all filters from the chain"""
        self.filters.clear()
        logger.info("Cleared all filters from chain")


class EventSubscription:
    """Event subscription with filtering"""
    
    def __init__(self, subscription_id: str, handler: Callable):
        self.subscription_id = subscription_id
        self.handler = handler
        self.filter_chain = EventFilterChain()
        self.active = True
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "handler_errors": 0
        }
    
    async def process_event(self, event_data: Dict[str, Any]):
        """Process event through filters and handler"""
        if not self.active:
            return
        
        self.stats["events_received"] += 1
        
        # Apply filters
        if not await self.filter_chain.apply_filters(event_data):
            return  # Event filtered out
        
        self.stats["events_processed"] += 1
        
        # Call handler
        try:
            if asyncio.iscoroutinefunction(self.handler):
                await self.handler(event_data)
            else:
                self.handler(event_data)
        except Exception as e:
            self.stats["handler_errors"] += 1
            logger.error("Subscription handler error",
                        subscription_id=self.subscription_id,
                        error=str(e))
    
    def add_filter(self, event_filter: BaseEventFilter):
        """Add filter to subscription"""
        self.filter_chain.add_filter(event_filter)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get subscription statistics"""
        return {
            "subscription_id": self.subscription_id,
            "active": self.active,
            "stats": self.stats.copy(),
            "filter_chain": self.filter_chain.get_chain_stats()
        }


class EventFilterManager:
    """Manages event filtering and subscriptions"""
    
    def __init__(self):
        self.global_filters = EventFilterChain()
        self.subscriptions: Dict[str, EventSubscription] = {}
        self.stats = {
            "total_subscriptions": 0,
            "active_subscriptions": 0
        }
    
    def add_global_filter(self, event_filter: BaseEventFilter):
        """Add filter that applies to all events"""
        self.global_filters.add_filter(event_filter)
    
    def create_subscription(self, subscription_id: str, handler: Callable) -> EventSubscription:
        """Create new event subscription"""
        if subscription_id in self.subscriptions:
            raise ValueError(f"Subscription {subscription_id} already exists")
        
        subscription = EventSubscription(subscription_id, handler)
        self.subscriptions[subscription_id] = subscription
        self.stats["total_subscriptions"] += 1
        self.stats["active_subscriptions"] += 1
        
        logger.info("Created event subscription",
                   subscription_id=subscription_id,
                   total_subscriptions=len(self.subscriptions))
        
        return subscription
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove event subscription"""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            self.stats["active_subscriptions"] -= 1
            logger.info("Removed event subscription",
                       subscription_id=subscription_id)
            return True
        return False
    
    async def distribute_event(self, event_data: Dict[str, Any]):
        """Distribute event to all subscriptions after global filtering"""
        # Apply global filters first
        if not await self.global_filters.apply_filters(event_data):
            return  # Event filtered out globally
        
        # Distribute to all active subscriptions
        tasks = []
        for subscription in self.subscriptions.values():
            if subscription.active:
                tasks.append(subscription.process_event(event_data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "manager_stats": self.stats.copy(),
            "global_filters": self.global_filters.get_chain_stats(),
            "subscriptions": {
                sub_id: sub.get_stats() 
                for sub_id, sub in self.subscriptions.items()
            }
        }


# Global filter manager instance
filter_manager = EventFilterManager()


# Convenience functions for common filter configurations
def create_debug_filters() -> List[BaseEventFilter]:
    """Create filters for debug/development environment"""
    return [
        EventTypeFilter(blocked_types=["minecraft:position", "minecraft:time_change"]),
        FrequencyFilter(max_events_per_second=5.0),
        PriorityFilter(min_priority=10)
    ]


def create_production_filters() -> List[BaseEventFilter]:
    """Create filters for production environment"""
    return [
        EventTypeFilter(blocked_types=["minecraft:position", "minecraft:entity_move"]),
        FrequencyFilter(max_events_per_second=20.0),
        PriorityFilter(min_priority=0),
        SourceFilter()  # No restrictions, but enables source tracking
    ]


def create_minimal_filters() -> List[BaseEventFilter]:
    """Create minimal filters for high-performance scenarios"""
    return [
        EventTypeFilter(
            allowed_types=["minecraft:spawn", "minecraft:chat", "minecraft:health", "minecraft:bot_death"]
        ),
        PriorityFilter(min_priority=30)
    ]