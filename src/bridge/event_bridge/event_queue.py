"""
Priority Event Queue - Asynchronous event processing with priority and batching
"""
import asyncio
import heapq
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import structlog

from .event_registry import event_registry
from .event_logger import event_logger
from .event_filters import filter_manager, EventFilterManager

logger = structlog.get_logger(__name__)


@dataclass
class QueuedEvent:
    """Event in the priority queue"""
    priority: int
    timestamp: float
    event_data: Dict[str, Any]
    event_id: str
    event_type: str
    batch_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """Support for heapq - higher priority first, then FIFO"""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.timestamp < other.timestamp  # Earlier timestamp first


@dataclass
class BatchConfig:
    """Configuration for event batching"""
    enabled: bool = False
    max_size: int = 100
    window_ms: int = 100
    max_wait_ms: int = 1000


@dataclass
class QueueStats:
    """Queue performance statistics"""
    total_enqueued: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_dropped: int = 0
    batch_count: int = 0
    retry_count: int = 0
    queue_size_peak: int = 0
    processing_time_total: float = 0
    start_time: float = field(default_factory=time.time)
    
    def success_rate(self) -> float:
        total = self.total_processed + self.total_failed
        return (self.total_processed / total * 100) if total > 0 else 0
    
    def average_processing_time(self) -> float:
        return (self.processing_time_total / self.total_processed) if self.total_processed > 0 else 0
    
    def events_per_second(self) -> float:
        elapsed = time.time() - self.start_time
        return self.total_processed / elapsed if elapsed > 0 else 0


class PriorityEventQueue:
    """Asynchronous priority queue for Minecraft events with batching support"""
    
    def __init__(self, 
                 max_size: int = 10000,
                 worker_count: int = 3,
                 batch_configs: Dict[str, BatchConfig] = None):
        self.max_size = max_size
        self.worker_count = worker_count
        self.batch_configs = batch_configs or {}
        
        # Queue and processing
        self._queue: List[QueuedEvent] = []
        self._queue_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._workers: List[asyncio.Task] = []
        self._batch_tasks: Dict[str, asyncio.Task] = {}
        
        # Batching
        self._pending_batches: Dict[str, List[QueuedEvent]] = defaultdict(list)
        self._batch_timers: Dict[str, asyncio.Handle] = {}
        
        # Sampling and filtering
        self._sampling_counters: Dict[str, int] = defaultdict(int)
        self._rate_limiters: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Statistics
        self.stats = QueueStats()
        
        # Event handlers
        self.event_handlers: Dict[str, List] = defaultdict(list)
        
        logger.info("PriorityEventQueue initialized",
                   max_size=max_size,
                   worker_count=worker_count,
                   batch_configs=len(self.batch_configs))
    
    async def start(self):
        """Start the queue processing workers"""
        logger.info("Starting event queue workers", worker_count=self.worker_count)
        
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        
        # Start batch processor
        batch_processor = asyncio.create_task(self._batch_processor())
        self._workers.append(batch_processor)
        
        logger.info("Event queue started")
    
    async def stop(self):
        """Stop the queue and all workers"""
        logger.info("Stopping event queue")
        
        self._shutdown_event.set()
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Cancel batch tasks
        for task in self._batch_tasks.values():
            task.cancel()
        
        # Cancel batch timers
        for timer in self._batch_timers.values():
            timer.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        logger.info("Event queue stopped")
    
    async def enqueue(self, event_data: Dict[str, Any]) -> bool:
        """
        Add an event to the queue
        
        Args:
            event_data: Event data from JavaScript bridge
            
        Returns:
            True if event was queued, False if dropped
        """
        event_type = event_data.get('event')
        event_id = event_data.get('eventId')
        
        if not event_type or not event_id:
            logger.error("Invalid event data for queue", event_data=event_data)
            return False
        
        # Apply global event filters first
        if not await filter_manager.global_filters.apply_filters(event_data):
            logger.debug("Event dropped by global filters",
                        event_type=event_type, event_id=event_id)
            self.stats.total_dropped += 1
            return False
        
        # Apply sampling if configured
        if not self._should_sample_event(event_type):
            logger.debug("Event dropped due to sampling", 
                        event_type=event_type, event_id=event_id)
            self.stats.total_dropped += 1
            return False
        
        # Apply rate limiting
        if not self._check_rate_limit(event_type):
            logger.debug("Event dropped due to rate limiting",
                        event_type=event_type, event_id=event_id)
            self.stats.total_dropped += 1
            return False
        
        # Get priority from registry
        priority = event_registry.get_event_priority(event_type)
        
        # Create queued event
        queued_event = QueuedEvent(
            priority=priority,
            timestamp=time.time(),
            event_data=event_data,
            event_id=event_id,
            event_type=event_type
        )
        
        # Check if batching is enabled for this event type
        batch_config = self._get_batch_config(event_type)
        if batch_config and batch_config.enabled:
            await self._enqueue_for_batch(queued_event, batch_config)
        else:
            await self._enqueue_single(queued_event)
        
        return True
    
    async def _enqueue_single(self, queued_event: QueuedEvent):
        """Enqueue a single event"""
        async with self._queue_lock:
            # Check queue size limit
            if len(self._queue) >= self.max_size:
                # Drop lowest priority event
                if self._queue and self._queue[-1].priority < queued_event.priority:
                    dropped = heapq.heappop(self._queue)
                    logger.warning("Queue full, dropped low priority event",
                                 dropped_event_type=dropped.event_type,
                                 dropped_event_id=dropped.event_id)
                    self.stats.total_dropped += 1
                else:
                    logger.warning("Queue full, dropping new event",
                                 event_type=queued_event.event_type,
                                 event_id=queued_event.event_id)
                    self.stats.total_dropped += 1
                    return
            
            heapq.heappush(self._queue, queued_event)
            self.stats.total_enqueued += 1
            self.stats.queue_size_peak = max(self.stats.queue_size_peak, len(self._queue))
            
            logger.debug("Event enqueued",
                        event_type=queued_event.event_type,
                        event_id=queued_event.event_id,
                        priority=queued_event.priority,
                        queue_size=len(self._queue))
    
    async def _enqueue_for_batch(self, queued_event: QueuedEvent, batch_config: BatchConfig):
        """Enqueue an event for batching"""
        event_type = queued_event.event_type
        batch_key = self._get_batch_key(event_type)
        
        self._pending_batches[batch_key].append(queued_event)
        
        # Generate batch ID if not set
        if not queued_event.batch_id:
            queued_event.batch_id = f"batch_{batch_key}_{time.time()}_{len(self._pending_batches[batch_key])}"
        
        logger.debug("Event added to batch",
                    event_type=event_type,
                    event_id=queued_event.event_id,
                    batch_key=batch_key,
                    batch_size=len(self._pending_batches[batch_key]))
        
        # Check if batch is ready to process
        if len(self._pending_batches[batch_key]) >= batch_config.max_size:
            await self._flush_batch(batch_key, "size_limit")
        elif batch_key not in self._batch_timers:
            # Start timer for this batch
            self._start_batch_timer(batch_key, batch_config.window_ms)
    
    def _start_batch_timer(self, batch_key: str, delay_ms: int):
        """Start a timer to flush a batch"""
        def timer_callback():
            asyncio.create_task(self._flush_batch(batch_key, "timer"))
        
        timer = asyncio.get_event_loop().call_later(
            delay_ms / 1000, timer_callback
        )
        self._batch_timers[batch_key] = timer
    
    async def _flush_batch(self, batch_key: str, reason: str):
        """Flush a batch to the main queue"""
        if batch_key not in self._pending_batches:
            return
        
        batch_events = self._pending_batches.pop(batch_key, [])
        if not batch_events:
            return
        
        # Cancel timer if exists
        if batch_key in self._batch_timers:
            self._batch_timers[batch_key].cancel()
            del self._batch_timers[batch_key]
        
        # Create a single high-priority batch event
        batch_event = QueuedEvent(
            priority=max(event.priority for event in batch_events) + 10,  # Slightly higher
            timestamp=min(event.timestamp for event in batch_events),
            event_data={
                'event': 'minecraft:batch',
                'eventId': f"batch_{batch_key}_{time.time()}",
                'data': {
                    'batch_type': batch_key,
                    'events': [event.event_data for event in batch_events],
                    'event_count': len(batch_events),
                    'flush_reason': reason
                }
            },
            event_id=f"batch_{batch_key}_{time.time()}",
            event_type='minecraft:batch',
            batch_id=batch_key
        )
        
        await self._enqueue_single(batch_event)
        self.stats.batch_count += 1
        
        logger.info("Batch flushed to queue",
                   batch_key=batch_key,
                   batch_size=len(batch_events),
                   flush_reason=reason)
    
    async def _worker(self, worker_name: str):
        """Queue processing worker"""
        logger.info("Queue worker started", worker=worker_name)
        
        while not self._shutdown_event.is_set():
            try:
                # Get next event
                queued_event = await self._dequeue()
                if not queued_event:
                    await asyncio.sleep(0.01)  # Brief sleep if queue empty
                    continue
                
                # Process the event
                await self._process_event(queued_event, worker_name)
                
            except Exception as e:
                logger.error("Worker error", worker=worker_name, error=str(e))
                await asyncio.sleep(0.1)  # Brief pause on error
        
        logger.info("Queue worker stopped", worker=worker_name)
    
    async def _dequeue(self) -> Optional[QueuedEvent]:
        """Dequeue the highest priority event"""
        async with self._queue_lock:
            if self._queue:
                return heapq.heappop(self._queue)
            return None
    
    async def _process_event(self, queued_event: QueuedEvent, worker_name: str):
        """Process a single event"""
        start_time = time.time()
        
        try:
            # Log event received
            event_logger.log_event_received(
                queued_event.event_id,
                start_time - queued_event.timestamp
            )
            
            # Call registered handlers
            await self._call_event_handlers(queued_event)
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats.total_processed += 1
            self.stats.processing_time_total += processing_time
            
            logger.debug("Event processed successfully",
                        event_type=queued_event.event_type,
                        event_id=queued_event.event_id,
                        worker=worker_name,
                        processing_time_ms=round(processing_time * 1000, 2))
            
        except Exception as e:
            self.stats.total_failed += 1
            
            # Retry logic
            if queued_event.retry_count < queued_event.max_retries:
                queued_event.retry_count += 1
                queued_event.timestamp = time.time()  # Reset timestamp for retry
                
                await self._enqueue_single(queued_event)
                self.stats.retry_count += 1
                
                logger.warning("Event processing failed, retrying",
                             event_type=queued_event.event_type,
                             event_id=queued_event.event_id,
                             retry_count=queued_event.retry_count,
                             error=str(e))
            else:
                logger.error("Event processing failed after max retries",
                           event_type=queued_event.event_type,
                           event_id=queued_event.event_id,
                           error=str(e))
                
                event_logger.log_event_failed(
                    queued_event.event_id,
                    f"Processing failed after {queued_event.max_retries} retries: {e}"
                )
    
    async def _call_event_handlers(self, queued_event: QueuedEvent):
        """Call all registered handlers for an event"""
        event_type = queued_event.event_type
        handlers = self.event_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(queued_event.event_data)
                else:
                    handler(queued_event.event_data)
            except Exception as e:
                logger.error("Event handler failed",
                           event_type=event_type,
                           handler=getattr(handler, '__name__', str(handler)),
                           error=str(e))
    
    async def _batch_processor(self):
        """Background task to handle batch timeouts"""
        logger.info("Batch processor started")
        
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(0.1)  # Check every 100ms
                
                # Check for expired batches
                current_time = time.time()
                expired_batches = []
                
                for batch_key, events in self._pending_batches.items():
                    if events:
                        oldest_event_time = min(event.timestamp for event in events)
                        batch_config = self._get_batch_config(events[0].event_type)
                        
                        if batch_config and current_time - oldest_event_time > batch_config.max_wait_ms / 1000:
                            expired_batches.append(batch_key)
                
                # Flush expired batches
                for batch_key in expired_batches:
                    await self._flush_batch(batch_key, "timeout")
                    
            except Exception as e:
                logger.error("Batch processor error", error=str(e))
        
        logger.info("Batch processor stopped")
    
    def _should_sample_event(self, event_type: str) -> bool:
        """Check if event should be sampled based on sampling rate"""
        sampling_rate = event_registry.get_sampling_rate(event_type)
        
        if sampling_rate >= 1.0:
            return True
        
        self._sampling_counters[event_type] += 1
        
        # Use deterministic sampling based on counter
        return (self._sampling_counters[event_type] % int(1 / sampling_rate)) == 0
    
    def _check_rate_limit(self, event_type: str) -> bool:
        """Check rate limiting for event type"""
        current_time = time.time()
        rate_limiter = self._rate_limiters[event_type]
        
        # Add current timestamp
        rate_limiter.append(current_time)
        
        # Check rate (events per second)
        if len(rate_limiter) >= rate_limiter.maxlen:
            time_span = rate_limiter[-1] - rate_limiter[0]
            rate = len(rate_limiter) / time_span if time_span > 0 else float('inf')
            
            # Apply different limits based on event type
            if event_type.endswith(':position'):
                return rate < 10  # Max 10 position updates per second
            elif event_type.endswith(':block_update'):
                return rate < 50  # Max 50 block updates per second
            else:
                return rate < 100  # Default limit
        
        return True
    
    def _get_batch_config(self, event_type: str) -> Optional[BatchConfig]:
        """Get batch configuration for event type"""
        if event_registry.is_batch_enabled(event_type):
            return self.batch_configs.get(event_type, BatchConfig(enabled=True))
        return None
    
    def _get_batch_key(self, event_type: str) -> str:
        """Get batch key for event type"""
        return event_type.replace('minecraft:', '')
    
    def register_handler(self, event_type: str, handler):
        """Register an event handler"""
        self.event_handlers[event_type].append(handler)
        logger.info("Handler registered with queue",
                   event_type=event_type,
                   handler=getattr(handler, '__name__', str(handler)))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queue_size": len(self._queue),
            "pending_batches": {
                batch_key: len(events) 
                for batch_key, events in self._pending_batches.items()
            },
            "worker_count": len(self._workers),
            "is_running": not self._shutdown_event.is_set(),
            "stats": {
                "total_enqueued": self.stats.total_enqueued,
                "total_processed": self.stats.total_processed,
                "total_failed": self.stats.total_failed,
                "total_dropped": self.stats.total_dropped,
                "batch_count": self.stats.batch_count,
                "retry_count": self.stats.retry_count,
                "queue_size_peak": self.stats.queue_size_peak,
                "success_rate_percent": round(self.stats.success_rate(), 2),
                "average_processing_time_ms": round(self.stats.average_processing_time() * 1000, 2),
                "events_per_second": round(self.stats.events_per_second(), 2)
            }
        }


# Global queue instance
priority_queue = PriorityEventQueue()