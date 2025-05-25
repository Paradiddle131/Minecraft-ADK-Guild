"""
Event metrics collection and dashboard system.

This module provides comprehensive metrics collection for the event bridge system,
including real-time statistics, performance monitoring, and health dashboards.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import statistics
import json
from pathlib import Path

from .payload_schemas import BaseEventPayload


@dataclass
class EventMetrics:
    """Metrics for a specific event type."""
    event_type: str
    total_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    max_processing_time: float = 0.0
    last_processed: Optional[datetime] = None
    processing_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def update_processing_time(self, processing_time: float):
        """Update processing time statistics."""
        self.processing_times.append(processing_time)
        self.min_processing_time = min(self.min_processing_time, processing_time)
        self.max_processing_time = max(self.max_processing_time, processing_time)
        self.avg_processing_time = statistics.mean(self.processing_times)
        self.last_processed = datetime.now()


@dataclass
class SystemMetrics:
    """Overall system metrics."""
    total_events_processed: int = 0
    events_per_second: float = 0.0
    current_queue_depth: int = 0
    max_queue_depth: int = 0
    active_connections: int = 0
    circuit_breaker_trips: int = 0
    compression_ratio: float = 0.0
    memory_usage_mb: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: Optional[datetime] = None


class EventMetricsCollector:
    """Collects and aggregates event metrics."""
    
    def __init__(self, window_size: int = 300):
        self.window_size = window_size  # 5 minutes default
        self.event_metrics: Dict[str, EventMetrics] = {}
        self.system_metrics = SystemMetrics()
        self.start_time = time.time()
        
        # Time-series data for rate calculations
        self.event_timestamps: deque = deque(maxlen=10000)
        self.queue_depth_history: deque = deque(maxlen=1000)
        
        # Callbacks for external metrics
        self.queue_depth_callback: Optional[Callable[[], int]] = None
        self.memory_callback: Optional[Callable[[], float]] = None
        self.connection_callback: Optional[Callable[[], int]] = None
    
    def record_event_start(self, event_type: str) -> str:
        """Record the start of event processing and return a tracking ID."""
        tracking_id = f"{event_type}_{time.time()}_{id(self)}"
        if event_type not in self.event_metrics:
            self.event_metrics[event_type] = EventMetrics(event_type=event_type)
        
        self.event_metrics[event_type].total_count += 1
        self.event_timestamps.append(time.time())
        return tracking_id
    
    def record_event_success(self, event_type: str, tracking_id: str, processing_time: float):
        """Record successful event processing."""
        if event_type in self.event_metrics:
            metrics = self.event_metrics[event_type]
            metrics.success_count += 1
            metrics.update_processing_time(processing_time)
        
        self.system_metrics.total_events_processed += 1
        self._update_system_metrics()
    
    def record_event_error(self, event_type: str, tracking_id: str, error: Exception):
        """Record event processing error."""
        if event_type in self.event_metrics:
            self.event_metrics[event_type].error_count += 1
        
        self._update_system_metrics()
    
    def record_circuit_breaker_trip(self):
        """Record a circuit breaker activation."""
        self.system_metrics.circuit_breaker_trips += 1
    
    def record_compression_ratio(self, ratio: float):
        """Record compression efficiency."""
        self.system_metrics.compression_ratio = ratio
    
    def _update_system_metrics(self):
        """Update system-wide metrics."""
        now = time.time()
        
        # Calculate events per second over the last minute
        minute_ago = now - 60
        recent_events = [ts for ts in self.event_timestamps if ts > minute_ago]
        self.system_metrics.events_per_second = len(recent_events) / 60.0
        
        # Update queue depth if callback is available
        if self.queue_depth_callback:
            current_depth = self.queue_depth_callback()
            self.system_metrics.current_queue_depth = current_depth
            self.system_metrics.max_queue_depth = max(
                self.system_metrics.max_queue_depth, current_depth
            )
            self.queue_depth_history.append(current_depth)
        
        # Update memory usage if callback is available
        if self.memory_callback:
            self.system_metrics.memory_usage_mb = self.memory_callback()
        
        # Update active connections if callback is available
        if self.connection_callback:
            self.system_metrics.active_connections = self.connection_callback()
        
        # Update uptime
        self.system_metrics.uptime_seconds = now - self.start_time
        self.system_metrics.last_updated = datetime.now()
    
    def get_event_metrics(self, event_type: str) -> Optional[EventMetrics]:
        """Get metrics for a specific event type."""
        return self.event_metrics.get(event_type)
    
    def get_all_event_metrics(self) -> Dict[str, EventMetrics]:
        """Get metrics for all event types."""
        return self.event_metrics.copy()
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        self._update_system_metrics()
        return self.system_metrics
    
    def get_top_events_by_volume(self, limit: int = 10) -> List[EventMetrics]:
        """Get top events by total count."""
        return sorted(
            self.event_metrics.values(),
            key=lambda m: m.total_count,
            reverse=True
        )[:limit]
    
    def get_top_events_by_errors(self, limit: int = 10) -> List[EventMetrics]:
        """Get top events by error count."""
        return sorted(
            self.event_metrics.values(),
            key=lambda m: m.error_count,
            reverse=True
        )[:limit]
    
    def get_slowest_events(self, limit: int = 10) -> List[EventMetrics]:
        """Get events with highest average processing time."""
        return sorted(
            [m for m in self.event_metrics.values() if m.avg_processing_time > 0],
            key=lambda m: m.avg_processing_time,
            reverse=True
        )[:limit]


class MetricsDashboard:
    """Console and file-based metrics dashboard."""
    
    def __init__(self, collector: EventMetricsCollector, output_dir: Optional[Path] = None):
        self.collector = collector
        self.output_dir = output_dir or Path("monitoring/metrics")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.running = False
        self.update_interval = 30  # seconds
    
    async def start_dashboard(self):
        """Start the dashboard update loop."""
        self.running = True
        while self.running:
            try:
                await self._update_dashboard()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                print(f"Dashboard update error: {e}")
                await asyncio.sleep(5)
    
    def stop_dashboard(self):
        """Stop the dashboard update loop."""
        self.running = False
    
    async def _update_dashboard(self):
        """Update dashboard displays."""
        await asyncio.gather(
            self._update_console_display(),
            self._update_json_export(),
            self._update_csv_export()
        )
    
    async def _update_console_display(self):
        """Update console dashboard display."""
        system_metrics = self.collector.get_system_metrics()
        
        print("\n" + "="*80)
        print("EVENT BRIDGE METRICS DASHBOARD")
        print("="*80)
        
        # System overview
        print(f"\n📊 SYSTEM OVERVIEW")
        print(f"   Uptime: {timedelta(seconds=int(system_metrics.uptime_seconds))}")
        print(f"   Events/sec: {system_metrics.events_per_second:.2f}")
        print(f"   Total Events: {system_metrics.total_events_processed:,}")
        print(f"   Queue Depth: {system_metrics.current_queue_depth} (max: {system_metrics.max_queue_depth})")
        print(f"   Active Connections: {system_metrics.active_connections}")
        print(f"   Circuit Breaker Trips: {system_metrics.circuit_breaker_trips}")
        print(f"   Compression Ratio: {system_metrics.compression_ratio:.2f}")
        print(f"   Memory Usage: {system_metrics.memory_usage_mb:.1f} MB")
        
        # Top events by volume
        top_events = self.collector.get_top_events_by_volume(5)
        if top_events:
            print(f"\n🔥 TOP EVENTS BY VOLUME")
            for i, event in enumerate(top_events, 1):
                error_rate = (event.error_count / event.total_count * 100) if event.total_count > 0 else 0
                print(f"   {i}. {event.event_type}")
                print(f"      Count: {event.total_count:,} | Errors: {event.error_count} ({error_rate:.1f}%)")
                print(f"      Avg Time: {event.avg_processing_time:.3f}s")
        
        # Error summary
        error_events = self.collector.get_top_events_by_errors(3)
        error_events = [e for e in error_events if e.error_count > 0]
        if error_events:
            print(f"\n⚠️  EVENTS WITH ERRORS")
            for event in error_events:
                error_rate = event.error_count / event.total_count * 100
                print(f"   {event.event_type}: {event.error_count} errors ({error_rate:.1f}%)")
        
        # Performance summary
        slow_events = self.collector.get_slowest_events(3)
        if slow_events:
            print(f"\n🐌 SLOWEST EVENTS")
            for event in slow_events:
                print(f"   {event.event_type}: {event.avg_processing_time:.3f}s avg")
                print(f"      Range: {event.min_processing_time:.3f}s - {event.max_processing_time:.3f}s")
    
    async def _update_json_export(self):
        """Export metrics to JSON file."""
        system_metrics = self.collector.get_system_metrics()
        event_metrics = self.collector.get_all_event_metrics()
        
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": {
                "total_events_processed": system_metrics.total_events_processed,
                "events_per_second": system_metrics.events_per_second,
                "current_queue_depth": system_metrics.current_queue_depth,
                "max_queue_depth": system_metrics.max_queue_depth,
                "active_connections": system_metrics.active_connections,
                "circuit_breaker_trips": system_metrics.circuit_breaker_trips,
                "compression_ratio": system_metrics.compression_ratio,
                "memory_usage_mb": system_metrics.memory_usage_mb,
                "uptime_seconds": system_metrics.uptime_seconds
            },
            "event_metrics": {}
        }
        
        for event_type, metrics in event_metrics.items():
            export_data["event_metrics"][event_type] = {
                "total_count": metrics.total_count,
                "success_count": metrics.success_count,
                "error_count": metrics.error_count,
                "avg_processing_time": metrics.avg_processing_time,
                "min_processing_time": metrics.min_processing_time if metrics.min_processing_time != float('inf') else 0,
                "max_processing_time": metrics.max_processing_time,
                "last_processed": metrics.last_processed.isoformat() if metrics.last_processed else None
            }
        
        output_file = self.output_dir / "current_metrics.json"
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    async def _update_csv_export(self):
        """Export time-series metrics to CSV."""
        import csv
        
        system_metrics = self.collector.get_system_metrics()
        timestamp = datetime.now()
        
        # System metrics CSV
        system_csv = self.output_dir / "system_metrics.csv"
        write_header = not system_csv.exists()
        
        with open(system_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow([
                    'timestamp', 'total_events_processed', 'events_per_second',
                    'current_queue_depth', 'max_queue_depth', 'active_connections',
                    'circuit_breaker_trips', 'compression_ratio', 'memory_usage_mb',
                    'uptime_seconds'
                ])
            
            writer.writerow([
                timestamp.isoformat(),
                system_metrics.total_events_processed,
                system_metrics.events_per_second,
                system_metrics.current_queue_depth,
                system_metrics.max_queue_depth,
                system_metrics.active_connections,
                system_metrics.circuit_breaker_trips,
                system_metrics.compression_ratio,
                system_metrics.memory_usage_mb,
                system_metrics.uptime_seconds
            ])


class MetricsMiddleware:
    """Middleware to automatically collect metrics from event processing."""
    
    def __init__(self, collector: EventMetricsCollector):
        self.collector = collector
    
    async def process_event(self, event_type: str, event_data: Dict[str, Any], 
                          handler: Callable) -> Any:
        """Process an event and collect metrics."""
        tracking_id = self.collector.record_event_start(event_type)
        start_time = time.time()
        
        try:
            result = await handler(event_data)
            processing_time = time.time() - start_time
            self.collector.record_event_success(event_type, tracking_id, processing_time)
            return result
        except Exception as e:
            self.collector.record_event_error(event_type, tracking_id, e)
            raise


# Global metrics collector instance
_global_collector: Optional[EventMetricsCollector] = None
_global_dashboard: Optional[MetricsDashboard] = None


def get_metrics_collector() -> EventMetricsCollector:
    """Get the global metrics collector instance."""
    global _global_collector
    if _global_collector is None:
        _global_collector = EventMetricsCollector()
    return _global_collector


def get_metrics_dashboard() -> MetricsDashboard:
    """Get the global metrics dashboard instance."""
    global _global_dashboard, _global_collector
    if _global_dashboard is None:
        if _global_collector is None:
            _global_collector = EventMetricsCollector()
        _global_dashboard = MetricsDashboard(_global_collector)
    return _global_dashboard


async def start_metrics_system():
    """Start the global metrics collection system."""
    dashboard = get_metrics_dashboard()
    await dashboard.start_dashboard()


def stop_metrics_system():
    """Stop the global metrics collection system."""
    dashboard = get_metrics_dashboard()
    dashboard.stop_dashboard()