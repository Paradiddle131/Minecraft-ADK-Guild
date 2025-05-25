"""
Event Lifecycle Logger - Comprehensive logging for event bridge operations
"""
import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EventLogEntry:
    """Single event log entry"""
    event_id: str
    event_type: str
    timestamp: float
    stage: str  # emitted, received, processed, completed, failed
    payload_size: int
    processing_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventStats:
    """Event statistics for monitoring"""
    total_events: int = 0
    events_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    events_by_stage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    processing_times: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    error_count: int = 0
    errors_by_type: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    start_time: float = field(default_factory=time.time)
    
    def events_per_second(self) -> float:
        """Calculate events per second"""
        elapsed = time.time() - self.start_time
        return self.total_events / elapsed if elapsed > 0 else 0
    
    def average_processing_time(self, event_type: str = None) -> float:
        """Get average processing time for event type or overall"""
        if event_type:
            times = self.processing_times.get(event_type, [])
        else:
            times = []
            for type_times in self.processing_times.values():
                times.extend(type_times)
        
        return sum(times) / len(times) if times else 0
    
    def error_rate(self) -> float:
        """Calculate error rate as percentage"""
        return (self.error_count / self.total_events * 100) if self.total_events > 0 else 0


class EventLifecycleLogger:
    """Tracks and logs the complete lifecycle of events through the bridge"""
    
    def __init__(self, max_history: int = 10000, debug_mode: bool = False):
        self.max_history = max_history
        self.debug_mode = debug_mode
        
        # Event tracking
        self.active_events: Dict[str, EventLogEntry] = {}
        self.event_history: deque = deque(maxlen=max_history)
        self.stats = EventStats()
        
        # Performance monitoring
        self.performance_window = timedelta(minutes=5)
        self.recent_events: deque = deque()
        
        # Async tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        
        logger.info("EventLifecycleLogger initialized", 
                   max_history=max_history, debug_mode=debug_mode)
    
    async def start(self):
        """Start background tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_events())
        self._metrics_task = asyncio.create_task(self._periodic_metrics())
        logger.info("EventLifecycleLogger started")
    
    async def stop(self):
        """Stop background tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
        logger.info("EventLifecycleLogger stopped")
    
    def log_event_emitted(self, event_id: str, event_type: str, payload: Dict[str, Any]):
        """Log when an event is emitted from JavaScript"""
        payload_size = len(json.dumps(payload)) if payload else 0
        
        entry = EventLogEntry(
            event_id=event_id,
            event_type=event_type,
            timestamp=time.time(),
            stage="emitted",
            payload_size=payload_size,
            metadata={
                "source": "javascript",
                "payload_keys": list(payload.keys()) if payload else []
            }
        )
        
        self.active_events[event_id] = entry
        self._update_stats("emitted", event_type)
        
        if self.debug_mode:
            logger.debug("Event emitted", 
                        event_id=event_id, 
                        event_type=event_type,
                        payload_size=payload_size)
    
    def log_event_received(self, event_id: str, processing_time: float = None):
        """Log when an event is received by Python"""
        if event_id not in self.active_events:
            logger.warning("Received unknown event", event_id=event_id)
            return
        
        entry = self.active_events[event_id]
        entry.stage = "received"
        entry.processing_time = processing_time
        
        self._update_stats("received", entry.event_type)
        
        if self.debug_mode:
            logger.debug("Event received",
                        event_id=event_id,
                        event_type=entry.event_type,
                        processing_time=processing_time)
    
    def log_event_processed(self, event_id: str, adk_state_changes: Dict[str, Any] = None):
        """Log when an event has been processed"""
        if event_id not in self.active_events:
            logger.warning("Processed unknown event", event_id=event_id)
            return
        
        entry = self.active_events[event_id]
        entry.stage = "processed"
        
        if adk_state_changes:
            entry.metadata["adk_state_changes"] = list(adk_state_changes.keys())
        
        self._update_stats("processed", entry.event_type)
        
        if self.debug_mode:
            logger.debug("Event processed",
                        event_id=event_id,
                        event_type=entry.event_type,
                        state_changes=len(adk_state_changes or {}))
    
    def log_event_completed(self, event_id: str):
        """Log when an event has completed successfully"""
        if event_id not in self.active_events:
            logger.warning("Completed unknown event", event_id=event_id)
            return
        
        entry = self.active_events[event_id]
        entry.stage = "completed"
        
        # Calculate total processing time
        total_time = time.time() - entry.timestamp
        entry.processing_time = total_time
        
        # Move to history
        self.event_history.append(entry)
        del self.active_events[event_id]
        
        # Update stats
        self._update_stats("completed", entry.event_type)
        self.stats.processing_times[entry.event_type].append(total_time)
        
        # Keep recent events for performance monitoring
        self.recent_events.append((time.time(), entry))
        
        if self.debug_mode:
            logger.debug("Event completed",
                        event_id=event_id,
                        event_type=entry.event_type,
                        total_time=total_time)
    
    def log_event_failed(self, event_id: str, error: str):
        """Log when an event processing fails"""
        if event_id not in self.active_events:
            logger.warning("Failed unknown event", event_id=event_id)
            return
        
        entry = self.active_events[event_id]
        entry.stage = "failed"
        entry.error = error
        
        # Move to history
        self.event_history.append(entry)
        del self.active_events[event_id]
        
        # Update stats
        self._update_stats("failed", entry.event_type)
        self.stats.error_count += 1
        self.stats.errors_by_type[entry.event_type].append(error)
        
        logger.warning("Event failed",
                      event_id=event_id,
                      event_type=entry.event_type,
                      error=error)
    
    def _update_stats(self, stage: str, event_type: str):
        """Update internal statistics"""
        self.stats.total_events += 1
        self.stats.events_by_type[event_type] += 1
        self.stats.events_by_stage[stage] += 1
    
    async def _cleanup_expired_events(self):
        """Clean up events that have been active too long"""
        while True:
            try:
                current_time = time.time()
                expired_threshold = current_time - 300  # 5 minutes
                
                expired_events = [
                    event_id for event_id, entry in self.active_events.items()
                    if entry.timestamp < expired_threshold
                ]
                
                for event_id in expired_events:
                    self.log_event_failed(event_id, "Event expired - processing timeout")
                
                if expired_events:
                    logger.warning("Cleaned up expired events", count=len(expired_events))
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error in cleanup task", error=str(e))
                await asyncio.sleep(60)
    
    async def _periodic_metrics(self):
        """Log periodic metrics"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Clean recent events older than performance window
                cutoff_time = time.time() - self.performance_window.total_seconds()
                while self.recent_events and self.recent_events[0][0] < cutoff_time:
                    self.recent_events.popleft()
                
                # Log metrics
                recent_count = len(self.recent_events)
                active_count = len(self.active_events)
                
                logger.info("Event bridge metrics",
                           total_events=self.stats.total_events,
                           events_per_second=round(self.stats.events_per_second(), 2),
                           active_events=active_count,
                           recent_events=recent_count,
                           error_rate=round(self.stats.error_rate(), 2),
                           avg_processing_time=round(self.stats.average_processing_time(), 3))
                
            except Exception as e:
                logger.error("Error in metrics task", error=str(e))
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        # Recent events in performance window
        cutoff_time = time.time() - self.performance_window.total_seconds()
        recent_events = [
            entry for timestamp, entry in self.recent_events 
            if timestamp >= cutoff_time
        ]
        
        # Group by event type
        recent_by_type = defaultdict(int)
        for _, entry in recent_events:
            recent_by_type[entry.event_type] += 1
        
        return {
            "total_events": self.stats.total_events,
            "events_per_second": round(self.stats.events_per_second(), 2),
            "active_events": len(self.active_events),
            "recent_events": len(recent_events),
            "error_rate_percent": round(self.stats.error_rate(), 2),
            "average_processing_time_ms": round(self.stats.average_processing_time() * 1000, 2),
            "events_by_type": dict(self.stats.events_by_type),
            "recent_events_by_type": dict(recent_by_type),
            "processing_times_by_type": {
                event_type: {
                    "avg_ms": round(sum(times) / len(times) * 1000, 2),
                    "count": len(times)
                }
                for event_type, times in self.stats.processing_times.items()
                if times
            }
        }
    
    def get_event_timeline(self, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get event timeline for debugging"""
        events = list(self.event_history)
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        events = events[-limit:]  # Get most recent
        
        return [
            {
                "event_id": entry.event_id,
                "event_type": entry.event_type,
                "timestamp": datetime.fromtimestamp(entry.timestamp).isoformat(),
                "stage": entry.stage,
                "payload_size_bytes": entry.payload_size,
                "processing_time_ms": round(entry.processing_time * 1000, 2) if entry.processing_time else None,
                "error": entry.error,
                "metadata": entry.metadata
            }
            for entry in events
        ]


# Global logger instance
event_logger = EventLifecycleLogger()