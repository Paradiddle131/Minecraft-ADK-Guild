"""
Circuit Breaker Pattern - Prevents cascade failures in event processing
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 3      # Successes needed to close from half-open
    timeout: float = 30.0           # Operation timeout in seconds
    
    # Advanced configuration
    failure_rate_threshold: float = 0.5  # Percentage of failures to open
    minimum_requests: int = 10           # Minimum requests before rate calculation
    sliding_window_size: int = 100       # Size of sliding window for stats
    
    # Exponential backoff
    max_recovery_timeout: float = 300.0  # Maximum recovery timeout
    backoff_multiplier: float = 2.0      # Backoff multiplier


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    
    def failure_rate(self) -> float:
        """Calculate current failure rate"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def success_rate(self) -> float:
        """Calculate current success rate"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class CircuitBreaker:
    """Circuit breaker implementation for event processing"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        
        # State management
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.next_attempt_time = 0
        
        # Sliding window for advanced statistics
        self.request_history: List[Dict[str, Any]] = []
        
        # Fallback mechanism
        self.fallback_handler: Optional[Callable] = None
        
        logger.info("Circuit breaker initialized",
                   name=self.name,
                   config=self.config)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        current_time = time.time()
        
        # Check if circuit should transition states
        self._update_state(current_time)
        
        # Record request
        self.stats.total_requests += 1
        
        # Handle based on current state
        if self.state == CircuitState.OPEN:
            logger.debug("Circuit breaker open, rejecting request",
                        name=self.name,
                        next_attempt=self.next_attempt_time - current_time)
            
            # Try fallback if available
            if self.fallback_handler:
                try:
                    return await self._execute_fallback(*args, **kwargs)
                except Exception as e:
                    logger.error("Fallback handler failed",
                               name=self.name, error=str(e))
            
            raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")
        
        # Execute the function with timeout
        try:
            result = await asyncio.wait_for(
                self._execute_function(func, *args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            self._record_success(current_time)
            return result
            
        except asyncio.TimeoutError:
            self.stats.timeouts += 1
            self._record_failure(current_time, "timeout")
            raise CircuitBreakerTimeoutError(f"Operation timed out after {self.config.timeout}s")
            
        except Exception as e:
            self._record_failure(current_time, str(e))
            raise
    
    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the actual function"""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    async def _execute_fallback(self, *args, **kwargs) -> Any:
        """Execute fallback handler"""
        if asyncio.iscoroutinefunction(self.fallback_handler):
            return await self.fallback_handler(*args, **kwargs)
        else:
            return self.fallback_handler(*args, **kwargs)
    
    def _record_success(self, current_time: float):
        """Record a successful operation"""
        self.stats.successful_requests += 1
        self.stats.last_success_time = current_time
        
        # Add to sliding window
        self.request_history.append({
            "timestamp": current_time,
            "success": True
        })
        self._cleanup_history(current_time)
        
        # State transition logic
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _record_failure(self, current_time: float, error: str):
        """Record a failed operation"""
        self.stats.failed_requests += 1
        self.stats.last_failure_time = current_time
        self.last_failure_time = current_time
        
        # Add to sliding window
        self.request_history.append({
            "timestamp": current_time,
            "success": False,
            "error": error
        })
        self._cleanup_history(current_time)
        
        # State transition logic
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            
            # Check if we should open the circuit
            if self._should_open_circuit():
                self._transition_to_open()
                
        elif self.state == CircuitState.HALF_OPEN:
            # Go back to open on any failure in half-open state
            self._transition_to_open()
    
    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened"""
        # Simple threshold check
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Advanced rate-based check
        if len(self.request_history) >= self.config.minimum_requests:
            failure_rate = self._calculate_recent_failure_rate()
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _calculate_recent_failure_rate(self) -> float:
        """Calculate failure rate from recent requests"""
        if not self.request_history:
            return 0.0
        
        recent_requests = self.request_history[-self.config.sliding_window_size:]
        if not recent_requests:
            return 0.0
        
        failures = sum(1 for req in recent_requests if not req["success"])
        return failures / len(recent_requests)
    
    def _cleanup_history(self, current_time: float):
        """Remove old entries from request history"""
        # Keep only recent requests (last hour)
        cutoff_time = current_time - 3600
        self.request_history = [
            req for req in self.request_history
            if req["timestamp"] > cutoff_time
        ]
        
        # Limit size to prevent memory issues
        if len(self.request_history) > self.config.sliding_window_size * 2:
            self.request_history = self.request_history[-self.config.sliding_window_size:]
    
    def _update_state(self, current_time: float):
        """Update circuit breaker state based on time and conditions"""
        if self.state == CircuitState.OPEN and current_time >= self.next_attempt_time:
            self._transition_to_half_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        previous_state = self.state
        self.state = CircuitState.OPEN
        self.stats.circuit_opens += 1
        
        # Calculate next attempt time with exponential backoff
        base_timeout = self.config.recovery_timeout
        backoff_factor = min(self.stats.circuit_opens, 5)  # Cap at 5 for reasonable limits
        timeout = min(
            base_timeout * (self.config.backoff_multiplier ** backoff_factor),
            self.config.max_recovery_timeout
        )
        
        self.next_attempt_time = time.time() + timeout
        
        logger.warning("Circuit breaker opened",
                      name=self.name,
                      previous_state=previous_state.value,
                      failure_count=self.failure_count,
                      next_attempt_in=timeout)
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        previous_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        
        logger.info("Circuit breaker half-open",
                   name=self.name,
                   previous_state=previous_state.value)
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        previous_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.stats.circuit_closes += 1
        
        logger.info("Circuit breaker closed",
                   name=self.name,
                   previous_state=previous_state.value)
    
    def set_fallback(self, fallback_handler: Callable):
        """Set fallback handler for when circuit is open"""
        self.fallback_handler = fallback_handler
        logger.info("Fallback handler set", name=self.name)
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.next_attempt_time = 0
        self.request_history.clear()
        
        logger.info("Circuit breaker reset", name=self.name)
    
    def force_open(self):
        """Force circuit breaker to open (for testing/maintenance)"""
        self._transition_to_open()
        logger.warning("Circuit breaker forced open", name=self.name)
    
    def force_close(self):
        """Force circuit breaker to close (for testing/recovery)"""
        self._transition_to_closed()
        logger.info("Circuit breaker forced closed", name=self.name)
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state and statistics"""
        current_time = time.time()
        
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "timeouts": self.stats.timeouts,
                "circuit_opens": self.stats.circuit_opens,
                "circuit_closes": self.stats.circuit_closes,
                "failure_rate": round(self.stats.failure_rate() * 100, 2),
                "success_rate": round(self.stats.success_rate() * 100, 2)
            },
            "timing": {
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "next_attempt_time": self.next_attempt_time if self.state == CircuitState.OPEN else None,
                "time_until_next_attempt": max(0, self.next_attempt_time - current_time) if self.state == CircuitState.OPEN else 0
            },
            "recent_failure_rate": round(self._calculate_recent_failure_rate() * 100, 2),
            "has_fallback": self.fallback_handler is not None
        }


class CircuitBreakerManager:
    """Manages multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
            logger.info("Created new circuit breaker", name=name)
        
        return self.breakers[name]
    
    def remove_breaker(self, name: str) -> bool:
        """Remove a circuit breaker"""
        if name in self.breakers:
            del self.breakers[name]
            logger.info("Removed circuit breaker", name=name)
            return True
        return False
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()
        logger.info("Reset all circuit breakers")
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state information for all circuit breakers"""
        return {
            name: breaker.get_state_info()
            for name, breaker in self.breakers.items()
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all circuit breakers"""
        total_breakers = len(self.breakers)
        open_breakers = sum(1 for b in self.breakers.values() if b.state == CircuitState.OPEN)
        half_open_breakers = sum(1 for b in self.breakers.values() if b.state == CircuitState.HALF_OPEN)
        closed_breakers = total_breakers - open_breakers - half_open_breakers
        
        return {
            "total_breakers": total_breakers,
            "states": {
                "open": open_breakers,
                "half_open": half_open_breakers,
                "closed": closed_breakers
            },
            "breaker_names": list(self.breakers.keys())
        }


# Custom exceptions
class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors"""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Raised when operation times out"""
    pass


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


# Decorator for easy circuit breaker usage
def circuit_breaker(name: str, config: CircuitBreakerConfig = None, fallback: Callable = None):
    """Decorator to add circuit breaker protection to functions"""
    def decorator(func):
        breaker = circuit_breaker_manager.get_breaker(name, config)
        if fallback:
            breaker.set_fallback(fallback)
        
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper._circuit_breaker = breaker
        
        return wrapper
    
    return decorator


# Convenience functions
def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get a circuit breaker instance"""
    return circuit_breaker_manager.get_breaker(name, config)


def reset_circuit_breaker(name: str):
    """Reset a specific circuit breaker"""
    if name in circuit_breaker_manager.breakers:
        circuit_breaker_manager.breakers[name].reset()


def get_all_circuit_breaker_states() -> Dict[str, Dict[str, Any]]:
    """Get states of all circuit breakers"""
    return circuit_breaker_manager.get_all_states()