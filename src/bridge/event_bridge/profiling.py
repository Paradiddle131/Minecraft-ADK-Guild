"""
Performance profiling system for the event bridge.

This module provides detailed performance profiling capabilities including
CPU profiling, memory profiling, and custom performance measurements.
"""

import time
import asyncio
import cProfile
import pstats
import io
import tracemalloc
import psutil
import gc
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
import json

from .metrics import EventMetricsCollector


@dataclass
class ProfileResult:
    """Result of a profiling session."""
    profile_id: str
    profile_type: str
    start_time: float
    end_time: float
    duration_ms: float
    operation_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[Path] = None


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: float
    current_mb: float
    peak_mb: float
    rss_mb: float
    vms_mb: float
    available_mb: float
    gc_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class CPUSnapshot:
    """CPU usage snapshot."""
    timestamp: float
    cpu_percent: float
    cpu_count: int
    load_avg: Optional[List[float]] = None
    threads: int = 0


class PerformanceProfiler:
    """Main performance profiling system."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("monitoring/profiling")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.enabled = True
        self.profile_threshold_ms = 100  # Only profile operations > 100ms
        self.memory_tracking = False
        self.cpu_tracking = False
        
        # Storage
        self.profile_results: List[ProfileResult] = []
        self.memory_snapshots: List[MemorySnapshot] = []
        self.cpu_snapshots: List[CPUSnapshot] = []
        
        # Active profiles
        self.active_profiles: Dict[str, Any] = {}
        
        # Background monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 5.0  # seconds
        
        # Initialize process monitoring
        try:
            self.process = psutil.Process()
        except:
            self.process = None
    
    def start_monitoring(self):
        """Start background performance monitoring."""
        if not self._monitoring_task:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None
    
    def enable_memory_tracking(self):
        """Enable detailed memory tracking."""
        self.memory_tracking = True
        tracemalloc.start()
    
    def disable_memory_tracking(self):
        """Disable detailed memory tracking."""
        self.memory_tracking = False
        if tracemalloc.is_tracing():
            tracemalloc.stop()
    
    def enable_cpu_tracking(self):
        """Enable CPU usage tracking."""
        self.cpu_tracking = True
    
    def disable_cpu_tracking(self):
        """Disable CPU usage tracking."""
        self.cpu_tracking = False
    
    @contextmanager
    def profile_cpu(self, operation_name: str, profile_id: Optional[str] = None):
        """Context manager for CPU profiling."""
        if not self.enabled:
            yield
            return
        
        profile_id = profile_id or f"cpu_{operation_name}_{int(time.time() * 1000)}"
        profiler = cProfile.Profile()
        start_time = time.time()
        
        try:
            profiler.enable()
            yield profile_id
        finally:
            profiler.disable()
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Only save if above threshold
            if duration_ms >= self.profile_threshold_ms:
                self._save_cpu_profile(profiler, profile_id, operation_name, 
                                     start_time, end_time, duration_ms)
    
    @contextmanager
    def profile_memory(self, operation_name: str, profile_id: Optional[str] = None):
        """Context manager for memory profiling."""
        if not self.enabled or not self.memory_tracking:
            yield
            return
        
        profile_id = profile_id or f"mem_{operation_name}_{int(time.time() * 1000)}"
        start_time = time.time()
        
        # Take initial snapshot
        if tracemalloc.is_tracing():
            start_snapshot = tracemalloc.take_snapshot()
        else:
            start_snapshot = None
        
        initial_memory = self._get_memory_usage()
        
        try:
            yield profile_id
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Take final snapshot
            final_memory = self._get_memory_usage()
            
            if start_snapshot and tracemalloc.is_tracing():
                end_snapshot = tracemalloc.take_snapshot()
                self._save_memory_profile(start_snapshot, end_snapshot, profile_id,
                                        operation_name, start_time, end_time, 
                                        duration_ms, initial_memory, final_memory)
    
    @contextmanager
    def profile_operation(self, operation_name: str, profile_id: Optional[str] = None):
        """Context manager for combined CPU and memory profiling."""
        if not self.enabled:
            yield
            return
        
        profile_id = profile_id or f"op_{operation_name}_{int(time.time() * 1000)}"
        
        with self.profile_cpu(operation_name, f"{profile_id}_cpu"):
            with self.profile_memory(operation_name, f"{profile_id}_mem"):
                yield profile_id
    
    def profile_function(self, operation_name: Optional[str] = None):
        """Decorator for profiling functions."""
        def decorator(func):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.profile_operation(op_name):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.profile_operation(op_name):
                        return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    def take_memory_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot."""
        memory_info = self._get_memory_usage()
        
        # Get garbage collection stats
        gc_stats = {}
        for i in range(3):  # GC generations 0, 1, 2
            gc_stats[f"gen_{i}"] = len(gc.get_objects(i))
        gc_stats["total_collections"] = sum(gc.get_stats()[i]["collections"] for i in range(3))
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            current_mb=memory_info["current_mb"],
            peak_mb=memory_info["peak_mb"],
            rss_mb=memory_info["rss_mb"],
            vms_mb=memory_info["vms_mb"],
            available_mb=memory_info["available_mb"],
            gc_stats=gc_stats
        )
        
        self.memory_snapshots.append(snapshot)
        return snapshot
    
    def take_cpu_snapshot(self) -> CPUSnapshot:
        """Take a CPU usage snapshot."""
        snapshot = CPUSnapshot(
            timestamp=time.time(),
            cpu_percent=self.process.cpu_percent() if self.process else 0.0,
            cpu_count=psutil.cpu_count(),
            threads=self.process.num_threads() if self.process else 0
        )
        
        # Get load average on Unix systems
        try:
            snapshot.load_avg = list(psutil.getloadavg())
        except:
            snapshot.load_avg = None
        
        self.cpu_snapshots.append(snapshot)
        return snapshot
    
    def get_profile_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get profiling summary for the last N hours."""
        cutoff_time = time.time() - (hours * 3600)
        
        recent_profiles = [p for p in self.profile_results if p.start_time > cutoff_time]
        recent_memory = [s for s in self.memory_snapshots if s.timestamp > cutoff_time]
        recent_cpu = [s for s in self.cpu_snapshots if s.timestamp > cutoff_time]
        
        # Profile statistics
        total_profiles = len(recent_profiles)
        cpu_profiles = len([p for p in recent_profiles if p.profile_type == "cpu"])
        memory_profiles = len([p for p in recent_profiles if p.profile_type == "memory"])
        
        durations = [p.duration_ms for p in recent_profiles]
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        # Memory statistics
        if recent_memory:
            current_memory = recent_memory[-1].current_mb
            peak_memory = max(s.peak_mb for s in recent_memory)
            avg_memory = sum(s.current_mb for s in recent_memory) / len(recent_memory)
        else:
            current_memory = peak_memory = avg_memory = 0
        
        # CPU statistics
        if recent_cpu:
            current_cpu = recent_cpu[-1].cpu_percent
            peak_cpu = max(s.cpu_percent for s in recent_cpu)
            avg_cpu = sum(s.cpu_percent for s in recent_cpu) / len(recent_cpu)
        else:
            current_cpu = peak_cpu = avg_cpu = 0
        
        return {
            "period_hours": hours,
            "profiling": {
                "total_profiles": total_profiles,
                "cpu_profiles": cpu_profiles,
                "memory_profiles": memory_profiles,
                "avg_duration_ms": avg_duration,
                "max_duration_ms": max_duration
            },
            "memory": {
                "current_mb": current_memory,
                "peak_mb": peak_memory,
                "avg_mb": avg_memory,
                "tracking_enabled": self.memory_tracking
            },
            "cpu": {
                "current_percent": current_cpu,
                "peak_percent": peak_cpu,
                "avg_percent": avg_cpu,
                "tracking_enabled": self.cpu_tracking
            },
            "system": {
                "cpu_count": psutil.cpu_count(),
                "total_memory_gb": psutil.virtual_memory().total / (1024**3)
            }
        }
    
    def get_slowest_operations(self, limit: int = 10) -> List[ProfileResult]:
        """Get the slowest profiled operations."""
        return sorted(self.profile_results, key=lambda p: p.duration_ms, reverse=True)[:limit]
    
    def get_memory_intensive_operations(self, limit: int = 10) -> List[ProfileResult]:
        """Get the most memory-intensive operations."""
        memory_profiles = [p for p in self.profile_results 
                          if p.profile_type == "memory" and "memory_delta_mb" in p.metadata]
        return sorted(memory_profiles, 
                     key=lambda p: p.metadata.get("memory_delta_mb", 0), 
                     reverse=True)[:limit]
    
    def export_profiles(self, format: str = "json") -> Path:
        """Export profiling data to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "json":
            filename = f"profile_export_{timestamp}.json"
            output_file = self.output_dir / filename
            
            export_data = {
                "export_time": datetime.now().isoformat(),
                "summary": self.get_profile_summary(24),  # Last 24 hours
                "profiles": [
                    {
                        "profile_id": p.profile_id,
                        "profile_type": p.profile_type,
                        "operation_name": p.operation_name,
                        "start_time": p.start_time,
                        "duration_ms": p.duration_ms,
                        "metadata": p.metadata
                    }
                    for p in self.profile_results[-1000:]  # Last 1000 profiles
                ],
                "memory_snapshots": [
                    {
                        "timestamp": s.timestamp,
                        "current_mb": s.current_mb,
                        "peak_mb": s.peak_mb,
                        "rss_mb": s.rss_mb,
                        "gc_stats": s.gc_stats
                    }
                    for s in self.memory_snapshots[-1000:]  # Last 1000 snapshots
                ],
                "cpu_snapshots": [
                    {
                        "timestamp": s.timestamp,
                        "cpu_percent": s.cpu_percent,
                        "threads": s.threads,
                        "load_avg": s.load_avg
                    }
                    for s in self.cpu_snapshots[-1000:]  # Last 1000 snapshots
                ]
            }
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
        
        return output_file
    
    def _save_cpu_profile(self, profiler: cProfile.Profile, profile_id: str, 
                         operation_name: str, start_time: float, end_time: float, 
                         duration_ms: float):
        """Save CPU profile results."""
        # Save profile stats to file
        output_file = self.output_dir / f"{profile_id}.prof"
        profiler.dump_stats(str(output_file))
        
        # Generate text report
        stats_stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats('cumulative').print_stats(20)  # Top 20 functions
        
        # Extract key statistics
        total_calls = stats.total_calls
        primitive_calls = stats.prim_calls
        
        result = ProfileResult(
            profile_id=profile_id,
            profile_type="cpu",
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            operation_name=operation_name,
            metadata={
                "total_calls": total_calls,
                "primitive_calls": primitive_calls,
                "stats_report": stats_stream.getvalue()[:5000]  # Truncate for storage
            },
            file_path=output_file
        )
        
        self.profile_results.append(result)
    
    def _save_memory_profile(self, start_snapshot, end_snapshot, profile_id: str,
                           operation_name: str, start_time: float, end_time: float,
                           duration_ms: float, initial_memory: Dict, final_memory: Dict):
        """Save memory profile results."""
        # Calculate memory delta
        memory_delta = final_memory["current_mb"] - initial_memory["current_mb"]
        
        # Get top memory allocations
        top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')[:10]
        
        # Format top allocations
        allocations = []
        for stat in top_stats:
            allocations.append({
                "file": stat.traceback.format()[-1] if stat.traceback else "unknown",
                "size_mb": stat.size / (1024 * 1024),
                "count": stat.count
            })
        
        result = ProfileResult(
            profile_id=profile_id,
            profile_type="memory",
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            operation_name=operation_name,
            metadata={
                "memory_delta_mb": memory_delta,
                "initial_memory_mb": initial_memory["current_mb"],
                "final_memory_mb": final_memory["current_mb"],
                "peak_memory_mb": final_memory["peak_mb"],
                "top_allocations": allocations
            }
        )
        
        self.profile_results.append(result)
    
    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage information."""
        if self.process:
            memory_info = self.process.memory_info()
            rss_mb = memory_info.rss / (1024 * 1024)
            vms_mb = memory_info.vms / (1024 * 1024)
        else:
            rss_mb = vms_mb = 0
        
        # Get system memory
        virtual_memory = psutil.virtual_memory()
        available_mb = virtual_memory.available / (1024 * 1024)
        
        # Get tracemalloc info if available
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / (1024 * 1024)
            peak_mb = peak / (1024 * 1024)
        else:
            current_mb = peak_mb = rss_mb
        
        return {
            "current_mb": current_mb,
            "peak_mb": peak_mb,
            "rss_mb": rss_mb,
            "vms_mb": vms_mb,
            "available_mb": available_mb
        }
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                if self.memory_tracking:
                    self.take_memory_snapshot()
                
                if self.cpu_tracking:
                    self.take_cpu_snapshot()
                
                await asyncio.sleep(self._monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)


# Global profiler instance
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Get the global profiler instance."""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def start_profiling():
    """Start the global profiling system."""
    profiler = get_profiler()
    profiler.start_monitoring()


def stop_profiling():
    """Stop the global profiling system."""
    profiler = get_profiler()
    profiler.stop_monitoring()


def profile_operation(operation_name: str):
    """Decorator for profiling operations."""
    return get_profiler().profile_function(operation_name)


# Convenience context managers
def profile_cpu(operation_name: str):
    """Context manager for CPU profiling."""
    return get_profiler().profile_cpu(operation_name)


def profile_memory(operation_name: str):
    """Context manager for memory profiling."""
    return get_profiler().profile_memory(operation_name)


def profile_full(operation_name: str):
    """Context manager for full profiling."""
    return get_profiler().profile_operation(operation_name)