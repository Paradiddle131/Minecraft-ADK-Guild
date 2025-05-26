"""
Event Compression System - Optimizes network usage for event streaming
"""
import gzip
import json
import lz4.frame
import pickle
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import structlog
import msgpack

logger = structlog.get_logger(__name__)


class CompressionType(Enum):
    """Supported compression algorithms"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    LZ4 = "lz4"


class SerializationType(Enum):
    """Supported serialization formats"""
    JSON = "json"
    MSGPACK = "msgpack"
    PICKLE = "pickle"


@dataclass
class CompressionConfig:
    """Configuration for event compression"""
    enabled: bool = True
    compression_type: CompressionType = CompressionType.LZ4
    serialization_type: SerializationType = SerializationType.MSGPACK
    min_size_threshold: int = 1024  # Minimum bytes to compress
    compression_level: Optional[int] = None  # Algorithm-specific level
    batch_compression: bool = True  # Compress batches separately
    
    def __post_init__(self):
        # Set default compression levels
        if self.compression_level is None:
            if self.compression_type == CompressionType.GZIP:
                self.compression_level = 6
            elif self.compression_type == CompressionType.ZLIB:
                self.compression_level = 6
            # LZ4 doesn't use compression levels


@dataclass
class CompressionResult:
    """Result of compression operation"""
    compressed_data: bytes
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_type: CompressionType
    serialization_type: SerializationType
    metadata: Dict[str, Any]
    
    def space_saved_percent(self) -> float:
        """Calculate percentage of space saved"""
        if self.original_size == 0:
            return 0
        return ((self.original_size - self.compressed_size) / self.original_size) * 100


class EventCompressor:
    """Handles compression and decompression of event data"""
    
    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()
        self.stats = {
            "total_compressed": 0,
            "total_decompressed": 0,
            "total_bytes_in": 0,
            "total_bytes_out": 0,
            "compression_errors": 0,
            "decompression_errors": 0
        }
    
    def compress_event(self, event_data: Dict[str, Any]) -> Union[CompressionResult, Dict[str, Any]]:
        """Compress a single event"""
        if not self.config.enabled:
            return event_data
        
        try:
            # Serialize data first
            serialized_data = self._serialize_data(event_data)
            
            # Check size threshold
            if len(serialized_data) < self.config.min_size_threshold:
                logger.debug("Event below compression threshold",
                           size=len(serialized_data),
                           threshold=self.config.min_size_threshold)
                return event_data
            
            # Compress serialized data
            compressed_data = self._compress_data(serialized_data)
            
            # Calculate compression ratio
            compression_ratio = len(compressed_data) / len(serialized_data)
            
            # Update statistics
            self.stats["total_compressed"] += 1
            self.stats["total_bytes_in"] += len(serialized_data)
            self.stats["total_bytes_out"] += len(compressed_data)
            
            result = CompressionResult(
                compressed_data=compressed_data,
                original_size=len(serialized_data),
                compressed_size=len(compressed_data),
                compression_ratio=compression_ratio,
                compression_type=self.config.compression_type,
                serialization_type=self.config.serialization_type,
                metadata={
                    "event_type": event_data.get("event"),
                    "event_id": event_data.get("eventId"),
                    "timestamp": event_data.get("timestamp")
                }
            )
            
            logger.debug("Event compressed",
                        event_type=event_data.get("event"),
                        original_size=result.original_size,
                        compressed_size=result.compressed_size,
                        ratio=round(compression_ratio, 3),
                        space_saved=round(result.space_saved_percent(), 1))
            
            return result
            
        except Exception as e:
            self.stats["compression_errors"] += 1
            logger.error("Event compression failed",
                        event_data=event_data,
                        error=str(e))
            return event_data  # Return original on error
    
    def decompress_event(self, compressed_result: CompressionResult) -> Dict[str, Any]:
        """Decompress an event"""
        try:
            # Decompress data
            decompressed_data = self._decompress_data(
                compressed_result.compressed_data,
                compressed_result.compression_type
            )
            
            # Deserialize data
            event_data = self._deserialize_data(
                decompressed_data,
                compressed_result.serialization_type
            )
            
            # Update statistics
            self.stats["total_decompressed"] += 1
            
            logger.debug("Event decompressed",
                        event_type=compressed_result.metadata.get("event_type"),
                        decompressed_size=len(decompressed_data))
            
            return event_data
            
        except Exception as e:
            self.stats["decompression_errors"] += 1
            logger.error("Event decompression failed",
                        metadata=compressed_result.metadata,
                        error=str(e))
            raise
    
    def compress_batch(self, events: List[Dict[str, Any]]) -> Union[CompressionResult, List[Dict[str, Any]]]:
        """Compress a batch of events together"""
        if not self.config.enabled or not self.config.batch_compression:
            return events
        
        try:
            # Create batch structure
            batch_data = {
                "events": events,
                "batch_size": len(events),
                "batch_timestamp": events[0].get("timestamp") if events else None,
                "compression_metadata": {
                    "type": "batch",
                    "version": "1.0"
                }
            }
            
            # Serialize batch
            serialized_data = self._serialize_data(batch_data)
            
            # Check size threshold
            if len(serialized_data) < self.config.min_size_threshold:
                return events
            
            # Compress batch
            compressed_data = self._compress_data(serialized_data)
            compression_ratio = len(compressed_data) / len(serialized_data)
            
            # Update statistics
            self.stats["total_compressed"] += 1
            self.stats["total_bytes_in"] += len(serialized_data)
            self.stats["total_bytes_out"] += len(compressed_data)
            
            result = CompressionResult(
                compressed_data=compressed_data,
                original_size=len(serialized_data),
                compressed_size=len(compressed_data),
                compression_ratio=compression_ratio,
                compression_type=self.config.compression_type,
                serialization_type=self.config.serialization_type,
                metadata={
                    "type": "batch",
                    "event_count": len(events),
                    "batch_timestamp": batch_data["batch_timestamp"]
                }
            )
            
            logger.debug("Batch compressed",
                        event_count=len(events),
                        original_size=result.original_size,
                        compressed_size=result.compressed_size,
                        ratio=round(compression_ratio, 3))
            
            return result
            
        except Exception as e:
            self.stats["compression_errors"] += 1
            logger.error("Batch compression failed",
                        batch_size=len(events),
                        error=str(e))
            return events
    
    def decompress_batch(self, compressed_result: CompressionResult) -> List[Dict[str, Any]]:
        """Decompress a batch of events"""
        try:
            # Decompress data
            decompressed_data = self._decompress_data(
                compressed_result.compressed_data,
                compressed_result.compression_type
            )
            
            # Deserialize batch
            batch_data = self._deserialize_data(
                decompressed_data,
                compressed_result.serialization_type
            )
            
            # Extract events from batch
            events = batch_data.get("events", [])
            
            # Update statistics
            self.stats["total_decompressed"] += 1
            
            logger.debug("Batch decompressed",
                        event_count=len(events),
                        decompressed_size=len(decompressed_data))
            
            return events
            
        except Exception as e:
            self.stats["decompression_errors"] += 1
            logger.error("Batch decompression failed",
                        metadata=compressed_result.metadata,
                        error=str(e))
            raise
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data using configured format"""
        if self.config.serialization_type == SerializationType.JSON:
            return json.dumps(data, separators=(',', ':')).encode('utf-8')
        elif self.config.serialization_type == SerializationType.MSGPACK:
            return msgpack.packb(data, use_bin_type=True)
        elif self.config.serialization_type == SerializationType.PICKLE:
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            raise ValueError(f"Unsupported serialization type: {self.config.serialization_type}")
    
    def _deserialize_data(self, data: bytes, serialization_type: SerializationType) -> Any:
        """Deserialize data using specified format"""
        if serialization_type == SerializationType.JSON:
            return json.loads(data.decode('utf-8'))
        elif serialization_type == SerializationType.MSGPACK:
            return msgpack.unpackb(data, raw=False)
        elif serialization_type == SerializationType.PICKLE:
            return pickle.loads(data)
        else:
            raise ValueError(f"Unsupported serialization type: {serialization_type}")
    
    def _compress_data(self, data: bytes) -> bytes:
        """Compress data using configured algorithm"""
        if self.config.compression_type == CompressionType.GZIP:
            return gzip.compress(data, compresslevel=self.config.compression_level)
        elif self.config.compression_type == CompressionType.ZLIB:
            return zlib.compress(data, level=self.config.compression_level)
        elif self.config.compression_type == CompressionType.LZ4:
            return lz4.frame.compress(data)
        elif self.config.compression_type == CompressionType.NONE:
            return data
        else:
            raise ValueError(f"Unsupported compression type: {self.config.compression_type}")
    
    def _decompress_data(self, data: bytes, compression_type: CompressionType) -> bytes:
        """Decompress data using specified algorithm"""
        if compression_type == CompressionType.GZIP:
            return gzip.decompress(data)
        elif compression_type == CompressionType.ZLIB:
            return zlib.decompress(data)
        elif compression_type == CompressionType.LZ4:
            return lz4.frame.decompress(data)
        elif compression_type == CompressionType.NONE:
            return data
        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        total_in = self.stats["total_bytes_in"]
        total_out = self.stats["total_bytes_out"]
        
        return {
            "config": {
                "enabled": self.config.enabled,
                "compression_type": self.config.compression_type.value,
                "serialization_type": self.config.serialization_type.value,
                "min_size_threshold": self.config.min_size_threshold
            },
            "stats": self.stats.copy(),
            "efficiency": {
                "overall_compression_ratio": total_out / total_in if total_in > 0 else 0,
                "space_saved_bytes": total_in - total_out,
                "space_saved_percent": ((total_in - total_out) / total_in * 100) if total_in > 0 else 0,
                "average_compression_ratio": (
                    total_out / total_in if total_in > 0 else 0
                ),
                "error_rate": (
                    (self.stats["compression_errors"] + self.stats["decompression_errors"]) /
                    max(self.stats["total_compressed"] + self.stats["total_decompressed"], 1) * 100
                )
            }
        }
    
    def reset_stats(self):
        """Reset compression statistics"""
        self.stats = {
            "total_compressed": 0,
            "total_decompressed": 0,
            "total_bytes_in": 0,
            "total_bytes_out": 0,
            "compression_errors": 0,
            "decompression_errors": 0
        }


class AdaptiveCompressor(EventCompressor):
    """Compressor that adapts compression strategy based on performance"""
    
    def __init__(self, config: CompressionConfig = None):
        super().__init__(config)
        self.performance_history = []
        self.adaptation_interval = 100  # Adapt every N compressions
        self.compression_threshold = 0.8  # Switch if ratio > this
    
    def compress_event(self, event_data: Dict[str, Any]) -> Union[CompressionResult, Dict[str, Any]]:
        """Compress with adaptive algorithm selection"""
        result = super().compress_event(event_data)
        
        # Track performance for adaptation
        if isinstance(result, CompressionResult):
            self.performance_history.append({
                "compression_ratio": result.compression_ratio,
                "original_size": result.original_size,
                "compression_type": result.compression_type
            })
            
            # Adapt if we have enough samples
            if (len(self.performance_history) % self.adaptation_interval == 0 and
                len(self.performance_history) > 0):
                self._adapt_compression()
        
        return result
    
    def _adapt_compression(self):
        """Adapt compression strategy based on performance"""
        if not self.performance_history:
            return
        
        # Calculate average compression ratio for recent events
        recent_history = self.performance_history[-self.adaptation_interval:]
        avg_ratio = sum(h["compression_ratio"] for h in recent_history) / len(recent_history)
        
        # If compression isn't effective, consider switching
        if avg_ratio > self.compression_threshold:
            # Try different algorithm or disable compression for small events
            if self.config.compression_type == CompressionType.GZIP:
                self.config.compression_type = CompressionType.LZ4
                logger.info("Adapted compression algorithm to LZ4 for better performance")
            elif self.config.min_size_threshold < 2048:
                self.config.min_size_threshold = 2048
                logger.info("Increased compression threshold to 2048 bytes")
        
        # Clear old history to prevent memory buildup
        if len(self.performance_history) > self.adaptation_interval * 3:
            self.performance_history = self.performance_history[-self.adaptation_interval:]


# Global compressor instances
default_compressor = EventCompressor()
adaptive_compressor = AdaptiveCompressor()


def compress_event_data(event_data: Dict[str, Any], 
                       use_adaptive: bool = False) -> Union[CompressionResult, Dict[str, Any]]:
    """Convenience function to compress event data"""
    compressor = adaptive_compressor if use_adaptive else default_compressor
    return compressor.compress_event(event_data)


def decompress_event_data(compressed_result: CompressionResult,
                         use_adaptive: bool = False) -> Dict[str, Any]:
    """Convenience function to decompress event data"""
    compressor = adaptive_compressor if use_adaptive else default_compressor
    return compressor.decompress_event(compressed_result)