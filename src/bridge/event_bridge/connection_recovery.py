"""
Connection Recovery System - Handles connection failures and recovery
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ConnectionState(Enum):
    """Connection states"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class RecoveryConfig:
    """Configuration for connection recovery"""
    max_retries: int = 10
    initial_delay: float = 1.0
    max_delay: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    
    # Health check settings
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0
    
    # Event queue settings during disconnection
    max_queued_events: int = 10000
    queue_overflow_strategy: str = "drop_oldest"  # drop_oldest, drop_newest, reject
    
    # Recovery strategies
    enable_event_catch_up: bool = True
    catch_up_window: float = 300.0  # 5 minutes
    enable_state_resync: bool = True


@dataclass
class ConnectionMetrics:
    """Connection health metrics"""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    disconnections: int = 0
    
    # Timing metrics
    connection_attempts: int = 0
    last_connection_time: Optional[float] = None
    last_disconnection_time: Optional[float] = None
    total_downtime: float = 0.0
    
    # Current state
    current_retry_count: int = 0
    consecutive_failures: int = 0
    uptime_start: Optional[float] = None
    
    def uptime(self) -> float:
        """Calculate current uptime"""
        if self.uptime_start is None:
            return 0.0
        return time.time() - self.uptime_start
    
    def success_rate(self) -> float:
        """Calculate connection success rate"""
        if self.total_connections == 0:
            return 0.0
        return self.successful_connections / self.total_connections


class EventQueue:
    """Queue for events during disconnection"""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
        self.events: List[Dict[str, Any]] = []
        self.overflow_count = 0
    
    def enqueue(self, event: Dict[str, Any]) -> bool:
        """Add event to queue"""
        if len(self.events) >= self.config.max_queued_events:
            self.overflow_count += 1
            
            if self.config.queue_overflow_strategy == "drop_oldest":
                self.events.pop(0)
            elif self.config.queue_overflow_strategy == "drop_newest":
                return False
            elif self.config.queue_overflow_strategy == "reject":
                return False
        
        self.events.append(event)
        return True
    
    def dequeue_all(self) -> List[Dict[str, Any]]:
        """Get all queued events and clear queue"""
        events = self.events.copy()
        self.events.clear()
        return events
    
    def size(self) -> int:
        """Get queue size"""
        return len(self.events)
    
    def clear(self):
        """Clear all queued events"""
        self.events.clear()


class ConnectionRecoveryManager:
    """Manages connection recovery and health monitoring"""
    
    def __init__(self, config: RecoveryConfig = None):
        self.config = config or RecoveryConfig()
        self.state = ConnectionState.DISCONNECTED
        self.metrics = ConnectionMetrics()
        
        # Event management
        self.event_queue = EventQueue(self.config)
        self.event_handlers: List[Callable] = []
        
        # Recovery management
        self.recovery_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.connection_callback: Optional[Callable] = None
        self.disconnection_callback: Optional[Callable] = None
        
        # State tracking
        self.last_successful_operation = time.time()
        self.recovery_start_time: Optional[float] = None
        
        logger.info("ConnectionRecoveryManager initialized", config=self.config)
    
    async def start_monitoring(self):
        """Start connection monitoring"""
        if self.health_check_task is None:
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Connection monitoring started")
    
    async def stop_monitoring(self):
        """Stop connection monitoring"""
        if self.health_check_task:
            self.health_check_task.cancel()
            self.health_check_task = None
        
        if self.recovery_task:
            self.recovery_task.cancel()
            self.recovery_task = None
        
        logger.info("Connection monitoring stopped")
    
    def set_connection_callback(self, callback: Callable):
        """Set callback for establishing connections"""
        self.connection_callback = callback
    
    def set_disconnection_callback(self, callback: Callable):
        """Set callback for handling disconnections"""
        self.disconnection_callback = callback
    
    def add_event_handler(self, handler: Callable):
        """Add handler for recovered events"""
        self.event_handlers.append(handler)
    
    async def handle_connection_established(self):
        """Handle successful connection"""
        old_state = self.state
        self.state = ConnectionState.CONNECTED
        self.metrics.successful_connections += 1
        self.metrics.last_connection_time = time.time()
        self.metrics.uptime_start = time.time()
        self.metrics.current_retry_count = 0
        self.metrics.consecutive_failures = 0
        
        # Calculate downtime if we were recovering
        if self.recovery_start_time:
            downtime = time.time() - self.recovery_start_time
            self.metrics.total_downtime += downtime
            self.recovery_start_time = None
        
        logger.info("Connection established",
                   previous_state=old_state.value,
                   uptime_start=self.metrics.uptime_start)
        
        # Process queued events if enabled
        if self.config.enable_event_catch_up:
            await self._process_queued_events()
        
        # Trigger state resync if enabled
        if self.config.enable_state_resync:
            await self._trigger_state_resync()
    
    async def handle_connection_lost(self, error: Optional[str] = None):
        """Handle connection loss"""
        old_state = self.state
        self.state = ConnectionState.DISCONNECTED
        self.metrics.disconnections += 1
        self.metrics.last_disconnection_time = time.time()
        
        if self.disconnection_callback:
            try:
                await self.disconnection_callback(error)
            except Exception as e:
                logger.error("Disconnection callback failed", error=str(e))
        
        logger.warning("Connection lost",
                      previous_state=old_state.value,
                      error=error,
                      uptime=self.metrics.uptime())
        
        # Start recovery if not already running
        if self.recovery_task is None:
            self.recovery_task = asyncio.create_task(self._recovery_loop())
    
    async def queue_event(self, event: Dict[str, Any]) -> bool:
        """Queue event during disconnection"""
        if self.state == ConnectionState.CONNECTED:
            # Process immediately if connected
            await self._process_single_event(event)
            return True
        else:
            # Queue for later processing
            return self.event_queue.enqueue(event)
    
    async def _recovery_loop(self):
        """Main recovery loop with exponential backoff"""
        self.state = ConnectionState.RECONNECTING
        self.recovery_start_time = time.time()
        retry_delay = self.config.initial_delay
        
        logger.info("Starting connection recovery",
                   max_retries=self.config.max_retries)
        
        while self.metrics.current_retry_count < self.config.max_retries:
            try:
                self.metrics.current_retry_count += 1
                self.metrics.connection_attempts += 1
                
                logger.info("Attempting to reconnect",
                           attempt=self.metrics.current_retry_count,
                           max_retries=self.config.max_retries)
                
                # Attempt reconnection
                if self.connection_callback:
                    await self.connection_callback()
                    
                    # If we get here, connection was successful
                    await self.handle_connection_established()
                    self.recovery_task = None
                    return
                else:
                    logger.error("No connection callback configured")
                    break
                    
            except Exception as e:
                self.metrics.failed_connections += 1
                self.metrics.consecutive_failures += 1
                
                logger.warning("Reconnection attempt failed",
                             attempt=self.metrics.current_retry_count,
                             error=str(e))
                
                # Calculate next retry delay with exponential backoff
                if self.config.jitter:
                    import random
                    jitter_factor = 0.1 * random.random()  # Up to 10% jitter
                    actual_delay = retry_delay * (1 + jitter_factor)
                else:
                    actual_delay = retry_delay
                
                logger.info("Waiting before next retry",
                           delay=round(actual_delay, 2))
                
                await asyncio.sleep(actual_delay)
                
                # Increase delay for next attempt
                retry_delay = min(
                    retry_delay * self.config.backoff_multiplier,
                    self.config.max_delay
                )
        
        # All retries exhausted
        self.state = ConnectionState.FAILED
        self.recovery_task = None
        
        logger.error("Connection recovery failed after all retries",
                    attempts=self.metrics.current_retry_count,
                    total_downtime=time.time() - self.recovery_start_time)
    
    async def _health_check_loop(self):
        """Periodic health check loop"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                if self.state == ConnectionState.CONNECTED:
                    # Perform health check
                    healthy = await self._perform_health_check()
                    
                    if not healthy:
                        logger.warning("Health check failed, triggering recovery")
                        await self.handle_connection_lost("Health check failed")
                
            except Exception as e:
                logger.error("Health check loop error", error=str(e))
    
    async def _perform_health_check(self) -> bool:
        """Perform actual health check"""
        try:
            # This is a placeholder - implement actual health check logic
            # Could be a ping, simple query, or connection test
            await asyncio.sleep(0.1)  # Simulate health check
            
            self.last_successful_operation = time.time()
            return True
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False
    
    async def _process_queued_events(self):
        """Process all queued events after reconnection"""
        queued_events = self.event_queue.dequeue_all()
        
        if not queued_events:
            return
        
        logger.info("Processing queued events",
                   count=len(queued_events),
                   overflow_count=self.event_queue.overflow_count)
        
        # Filter events within catch-up window
        current_time = time.time()
        cutoff_time = current_time - self.config.catch_up_window
        
        valid_events = [
            event for event in queued_events
            if event.get('timestamp', 0) / 1000 > cutoff_time
        ]
        
        if len(valid_events) < len(queued_events):
            logger.info("Filtered old events from queue",
                       total=len(queued_events),
                       valid=len(valid_events))
        
        # Process valid events
        for event in valid_events:
            try:
                await self._process_single_event(event)
            except Exception as e:
                logger.error("Failed to process queued event",
                           event_id=event.get('eventId'),
                           error=str(e))
    
    async def _process_single_event(self, event: Dict[str, Any]):
        """Process a single event"""
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Event handler failed during recovery",
                           event_id=event.get('eventId'),
                           handler=handler.__name__,
                           error=str(e))
    
    async def _trigger_state_resync(self):
        """Trigger state resynchronization after reconnection"""
        logger.info("Triggering state resynchronization")
        
        # This is a placeholder - implement actual state resync logic
        # Could involve requesting current state from server, comparing with local state, etc.
        try:
            # Simulate state resync
            await asyncio.sleep(0.1)
            logger.info("State resynchronization completed")
            
        except Exception as e:
            logger.error("State resynchronization failed", error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current connection status and metrics"""
        return {
            "state": self.state.value,
            "is_healthy": self.state == ConnectionState.CONNECTED,
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "successful_connections": self.metrics.successful_connections,
                "failed_connections": self.metrics.failed_connections,
                "disconnections": self.metrics.disconnections,
                "success_rate": round(self.metrics.success_rate() * 100, 2),
                "current_uptime": round(self.metrics.uptime(), 2),
                "total_downtime": round(self.metrics.total_downtime, 2),
                "consecutive_failures": self.metrics.consecutive_failures,
                "current_retry_count": self.metrics.current_retry_count
            },
            "queue": {
                "size": self.event_queue.size(),
                "overflow_count": self.event_queue.overflow_count,
                "max_size": self.config.max_queued_events
            },
            "recovery": {
                "is_recovering": self.state == ConnectionState.RECONNECTING,
                "recovery_start_time": self.recovery_start_time,
                "time_in_recovery": (
                    time.time() - self.recovery_start_time 
                    if self.recovery_start_time else 0
                )
            }
        }
    
    def reset_metrics(self):
        """Reset connection metrics"""
        self.metrics = ConnectionMetrics()
        self.event_queue.clear()
        self.event_queue.overflow_count = 0
        logger.info("Connection metrics reset")


# Global recovery manager instance
connection_recovery = ConnectionRecoveryManager()