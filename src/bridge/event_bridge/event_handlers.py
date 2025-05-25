"""
Event Handler Decorators - Simplified event handler registration
"""
import asyncio
import functools
from typing import Any, Callable, Dict, Optional, Union

import structlog
from google.cloud import adk

from .adk_adapter import adk_adapter
from .event_registry import event_registry

logger = structlog.get_logger(__name__)


def minecraft_event(event_type: str, 
                   priority: int = 0,
                   auto_register: bool = True,
                   validate_payload: bool = True):
    """
    Decorator for registering Minecraft event handlers
    
    Args:
        event_type: The event type to handle (e.g., "minecraft:spawn")
        priority: Handler priority (higher = called first)
        auto_register: Whether to automatically register with adapter
        validate_payload: Whether to validate event payload
        
    Usage:
        @minecraft_event("minecraft:spawn")
        async def handle_spawn(event_data: dict) -> EventActions:
            return EventActions(state_delta={"spawned": True})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(event_data: Dict[str, Any]) -> Optional[adk.EventActions]:
            start_time = asyncio.get_event_loop().time()
            event_id = event_data.get('eventId', 'unknown')
            
            try:
                # Validate payload if requested
                if validate_payload:
                    payload_data = event_data.get('data', {})
                    try:
                        event_registry.validate_event_payload(event_type, payload_data)
                    except ValueError as e:
                        logger.error("Handler payload validation failed",
                                   event_type=event_type,
                                   handler=func.__name__,
                                   event_id=event_id,
                                   error=str(e))
                        return None
                
                # Call the handler
                if asyncio.iscoroutinefunction(func):
                    result = await func(event_data)
                else:
                    result = func(event_data)
                
                # Ensure result is EventActions
                if result is None:
                    result = adk.EventActions()
                elif not isinstance(result, adk.EventActions):
                    logger.warning("Handler returned non-EventActions result",
                                 event_type=event_type,
                                 handler=func.__name__,
                                 result_type=type(result).__name__)
                    result = adk.EventActions()
                
                processing_time = asyncio.get_event_loop().time() - start_time
                logger.debug("Event handler completed",
                           event_type=event_type,
                           handler=func.__name__,
                           event_id=event_id,
                           processing_time_ms=round(processing_time * 1000, 2))
                
                return result
                
            except Exception as e:
                logger.error("Event handler failed",
                           event_type=event_type,
                           handler=func.__name__,
                           event_id=event_id,
                           error=str(e),
                           exc_info=True)
                return None
        
        # Store metadata on the function
        wrapper._minecraft_event_type = event_type
        wrapper._minecraft_event_priority = priority
        wrapper._minecraft_event_auto_register = auto_register
        wrapper._minecraft_event_validate_payload = validate_payload
        
        # Auto-register if requested
        if auto_register and adk_adapter:
            adk_adapter.register_handler(event_type, wrapper)
            logger.info("Auto-registered event handler",
                       event_type=event_type,
                       handler=func.__name__,
                       priority=priority)
        
        return wrapper
    
    return decorator


def priority_event_handler(event_type: str, priority: int = 100):
    """
    Decorator for high-priority event handlers
    
    Args:
        event_type: The event type to handle
        priority: Handler priority (default 100 for high priority)
    """
    return minecraft_event(event_type, priority=priority, auto_register=True)


def background_event_handler(event_type: str):
    """
    Decorator for background/low-priority event handlers
    
    Args:
        event_type: The event type to handle
    """
    return minecraft_event(event_type, priority=-10, auto_register=True)


def batch_event_handler(event_types: list, batch_window_ms: int = 100):
    """
    Decorator for handling multiple event types in batches
    
    Args:
        event_types: List of event types to batch
        batch_window_ms: Time window for batching events
        
    Note: This is a placeholder for future batch processing implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(event_batch: list) -> Optional[adk.EventActions]:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(event_batch)
                else:
                    result = func(event_batch)
                
                if not isinstance(result, adk.EventActions):
                    result = adk.EventActions()
                
                return result
                
            except Exception as e:
                logger.error("Batch event handler failed",
                           event_types=event_types,
                           handler=func.__name__,
                           batch_size=len(event_batch),
                           error=str(e))
                return None
        
        # Store metadata
        wrapper._minecraft_batch_event_types = event_types
        wrapper._minecraft_batch_window_ms = batch_window_ms
        
        # TODO: Implement batch registration
        logger.info("Batch event handler registered (not yet implemented)",
                   event_types=event_types,
                   handler=func.__name__)
        
        return wrapper
    
    return decorator


def conditional_event_handler(event_type: str, condition: Callable[[Dict[str, Any]], bool]):
    """
    Decorator for conditional event handlers
    
    Args:
        event_type: The event type to handle
        condition: Function that returns True if handler should run
    """
    def decorator(func: Callable) -> Callable:
        @minecraft_event(event_type, auto_register=False)
        async def wrapper(event_data: Dict[str, Any]) -> Optional[adk.EventActions]:
            # Check condition first
            try:
                should_handle = condition(event_data)
            except Exception as e:
                logger.error("Event condition check failed",
                           event_type=event_type,
                           handler=func.__name__,
                           error=str(e))
                return None
            
            if not should_handle:
                logger.debug("Event condition not met, skipping handler",
                           event_type=event_type,
                           handler=func.__name__,
                           event_id=event_data.get('eventId'))
                return None
            
            # Call the actual handler
            if asyncio.iscoroutinefunction(func):
                return await func(event_data)
            else:
                return func(event_data)
        
        # Register the conditional wrapper
        if adk_adapter:
            adk_adapter.register_handler(event_type, wrapper)
            logger.info("Registered conditional event handler",
                       event_type=event_type,
                       handler=func.__name__)
        
        return wrapper
    
    return decorator


def state_based_handler(event_type: str, required_state: Dict[str, Any]):
    """
    Decorator for handlers that only run when certain state conditions are met
    
    Args:
        event_type: The event type to handle
        required_state: Dict of state keys and required values
    """
    def state_condition(event_data: Dict[str, Any]) -> bool:
        # TODO: Implement state checking against session state
        # For now, always return True
        return True
    
    return conditional_event_handler(event_type, state_condition)


class EventHandlerRegistry:
    """Registry for managing event handlers with metadata"""
    
    def __init__(self):
        self.handlers: Dict[str, list] = {}
        self.handler_metadata: Dict[str, Dict[str, Any]] = {}
    
    def register_handler(self, event_type: str, handler: Callable, metadata: Dict[str, Any] = None):
        """Register a handler with optional metadata"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        
        if metadata:
            handler_key = f"{event_type}:{handler.__name__}"
            self.handler_metadata[handler_key] = metadata
        
        logger.info("Handler registered in registry",
                   event_type=event_type,
                   handler=handler.__name__)
    
    def get_handlers(self, event_type: str) -> list:
        """Get all handlers for an event type, sorted by priority"""
        handlers = self.handlers.get(event_type, [])
        
        # Sort by priority if available
        def get_priority(handler):
            return getattr(handler, '_minecraft_event_priority', 0)
        
        return sorted(handlers, key=get_priority, reverse=True)
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """Unregister a specific handler"""
        if event_type in self.handlers:
            try:
                self.handlers[event_type].remove(handler)
                logger.info("Handler unregistered from registry",
                           event_type=event_type,
                           handler=handler.__name__)
            except ValueError:
                logger.warning("Handler not found in registry",
                             event_type=event_type,
                             handler=handler.__name__)
    
    def list_handlers(self) -> Dict[str, list]:
        """List all registered handlers"""
        return {
            event_type: [h.__name__ for h in handlers]
            for event_type, handlers in self.handlers.items()
        }
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        total_handlers = sum(len(handlers) for handlers in self.handlers.values())
        
        return {
            "total_handlers": total_handlers,
            "event_types": len(self.handlers),
            "handlers_by_type": {
                event_type: len(handlers)
                for event_type, handlers in self.handlers.items()
            },
            "handler_metadata_count": len(self.handler_metadata)
        }


# Global registry instance
handler_registry = EventHandlerRegistry()


# Example handlers for common events
@minecraft_event("minecraft:spawn", priority=100)
async def handle_bot_spawn(event_data: Dict[str, Any]) -> adk.EventActions:
    """Default spawn handler - sets basic bot state"""
    spawn_data = event_data.get('data', {})
    
    state_delta = {
        "minecraft.bot.spawned": True,
        "minecraft.bot.ready": True,
        "minecraft.spawn_completed_at": spawn_data.get('time', 0)
    }
    
    # Add position if available
    if 'position' in spawn_data and spawn_data['position']:
        pos = spawn_data['position']
        state_delta.update({
            "minecraft.bot.spawn_position.x": pos.get('x', 0),
            "minecraft.bot.spawn_position.y": pos.get('y', 0),
            "minecraft.bot.spawn_position.z": pos.get('z', 0)
        })
    
    logger.info("Bot spawn processed by default handler",
               event_id=event_data.get('eventId'),
               position=spawn_data.get('position'))
    
    return adk.EventActions(state_delta=state_delta)


@minecraft_event("minecraft:health", priority=75)
async def handle_health_change(event_data: Dict[str, Any]) -> adk.EventActions:
    """Default health handler - tracks bot health"""
    health_data = event_data.get('data', {})
    
    state_delta = {
        "minecraft.bot.health": health_data.get('health', 20),
        "minecraft.bot.food": health_data.get('food', 20),
        "minecraft.bot.saturation": health_data.get('saturation', 5.0),
        "minecraft.bot.health_last_update": health_data.get('time', 0)
    }
    
    # Add health status flags
    health = health_data.get('health', 20)
    state_delta.update({
        "minecraft.bot.health_critical": health <= 4,
        "minecraft.bot.health_low": health <= 10,
        "minecraft.bot.health_full": health >= 20
    })
    
    return adk.EventActions(state_delta=state_delta)


@background_event_handler("minecraft:position")
async def handle_position_update(event_data: Dict[str, Any]) -> adk.EventActions:
    """Background position handler - low priority position tracking"""
    pos_data = event_data.get('data', {})
    
    state_delta = {
        "minecraft.bot.position.x": pos_data.get('x', 0),
        "minecraft.bot.position.y": pos_data.get('y', 0),
        "minecraft.bot.position.z": pos_data.get('z', 0),
        "minecraft.bot.position.last_update": pos_data.get('time', 0)
    }
    
    # Add optional rotation
    if 'yaw' in pos_data:
        state_delta["minecraft.bot.position.yaw"] = pos_data['yaw']
    if 'pitch' in pos_data:
        state_delta["minecraft.bot.position.pitch"] = pos_data['pitch']
    
    return adk.EventActions(state_delta=state_delta)


# Conditional handler example
def is_important_chat(event_data: Dict[str, Any]) -> bool:
    """Condition: only handle chat that mentions the bot or contains commands"""
    chat_data = event_data.get('data', {})
    message = chat_data.get('message', '').lower()
    
    # Check if message contains bot name or command prefix
    bot_name = event_data.get('botId', '').lower()
    return (bot_name in message or 
            message.startswith('!') or 
            message.startswith('/') or
            'help' in message)


@conditional_event_handler("minecraft:chat", is_important_chat)
async def handle_important_chat(event_data: Dict[str, Any]) -> adk.EventActions:
    """Handle only important chat messages"""
    chat_data = event_data.get('data', {})
    
    state_delta = {
        "minecraft.chat.important_message": chat_data.get('message', ''),
        "minecraft.chat.important_speaker": chat_data.get('username', ''),
        "minecraft.chat.needs_attention": True,
        "minecraft.chat.last_important_time": chat_data.get('time', 0)
    }
    
    logger.info("Important chat message detected",
               username=chat_data.get('username'),
               message=chat_data.get('message'))
    
    return adk.EventActions(state_delta=state_delta)