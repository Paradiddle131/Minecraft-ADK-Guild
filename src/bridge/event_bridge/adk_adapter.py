"""
ADK Event Adapter - Bridge Minecraft events to Google ADK EventActions
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Callable

import structlog
from google.cloud import adk

from .event_registry import event_registry, EventRegistry
from .event_logger import event_logger
from .payload_schemas import payload_validator, ValidationResult
from .state_sync import state_synchronizer

logger = structlog.get_logger(__name__)


class ADKEventAdapter:
    """Converts Minecraft events to ADK EventActions with state management"""
    
    def __init__(self, session_service=None, registry: EventRegistry = None):
        self.session_service = session_service
        self.registry = registry or event_registry
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.is_running = False
        
        # Performance tracking
        self.processed_events = 0
        self.failed_events = 0
        self.start_time = time.time()
        
        logger.info("ADKEventAdapter initialized")
    
    async def start(self):
        """Start the event adapter"""
        self.is_running = True
        await event_logger.start()
        logger.info("ADKEventAdapter started")
    
    async def stop(self):
        """Stop the event adapter"""
        self.is_running = False
        await event_logger.stop()
        logger.info("ADKEventAdapter stopped")
    
    async def process_minecraft_event(self, event_data: Dict[str, Any]) -> Optional[adk.EventActions]:
        """
        Process a Minecraft event and convert to ADK EventActions
        
        Args:
            event_data: Raw event data from JavaScript bridge
            
        Returns:
            EventActions object or None if event should be ignored
        """
        if not self.is_running:
            logger.warning("Received event while adapter stopped", event_data=event_data)
            return None
        
        start_time = time.time()
        event_type = event_data.get('event')
        event_id = event_data.get('eventId')
        
        if not event_type or not event_id:
            logger.error("Invalid event data - missing type or ID", event_data=event_data)
            return None
        
        try:
            # Log event reception
            processing_time = time.time() - event_data.get('timestamp', time.time()) / 1000
            event_logger.log_event_received(event_id, processing_time)
            
            # Validate event against registry
            metadata = self.registry.get_event_metadata(event_type)
            if not metadata:
                logger.warning("Unknown event type", event_type=event_type, event_id=event_id)
                event_logger.log_event_failed(event_id, f"Unknown event type: {event_type}")
                return None
            
            # Validate payload using both registry and common validators
            payload_data = event_data.get('data', {})
            
            # First, use common payload validator
            validation_result = payload_validator.validate_payload(event_type, payload_data)
            
            if not validation_result.valid:
                logger.error("Common payload validation failed", 
                           event_type=event_type, event_id=event_id, 
                           errors=validation_result.errors)
                event_logger.log_event_failed(event_id, f"Payload validation failed: {validation_result.errors}")
                return None
            
            # Log any warnings
            if validation_result.warnings:
                logger.warning("Payload validation warnings",
                             event_type=event_type, event_id=event_id,
                             warnings=validation_result.warnings)
            
            # Use normalized payload if available
            if validation_result.normalized_payload:
                payload_data = validation_result.normalized_payload
            
            # Then, validate against registry schema
            try:
                validated_payload = self.registry.validate_event_payload(event_type, payload_data)
                logger.debug("Event payload validated", event_type=event_type, event_id=event_id)
            except ValueError as e:
                logger.error("Registry payload validation failed", 
                           event_type=event_type, event_id=event_id, error=str(e))
                event_logger.log_event_failed(event_id, f"Registry validation failed: {e}")
                return None
            
            # Generate state delta
            state_changes = self.registry.get_adk_state_mapping(event_type, payload_data)
            
            # Log processing
            event_logger.log_event_processed(event_id, state_changes)
            
            # Create EventActions
            event_actions = adk.EventActions()
            
            if state_changes:
                event_actions.state_delta = state_changes
                logger.debug("Generated state delta", 
                           event_type=event_type, 
                           event_id=event_id,
                           state_keys=list(state_changes.keys()))
            
            # Add event metadata to state
            event_actions.state_delta.update({
                "minecraft.events.last_event_type": event_type,
                "minecraft.events.last_event_time": payload_data.get('time', time.time()),
                "minecraft.events.last_event_id": event_id
            })
            
            # Synchronize state changes
            await state_synchronizer.apply_state_delta(
                event_actions.state_delta,
                event_id=event_id,
                source="adk_adapter"
            )
            
            # Call registered handlers
            await self._call_event_handlers(event_type, event_data, event_actions)
            
            # Record success
            self.processed_events += 1
            event_logger.log_event_completed(event_id)
            
            total_time = time.time() - start_time
            logger.debug("Event processed successfully",
                        event_type=event_type,
                        event_id=event_id,
                        processing_time_ms=round(total_time * 1000, 2),
                        state_changes=len(state_changes))
            
            return event_actions
            
        except Exception as e:
            self.failed_events += 1
            error_msg = f"Failed to process event: {e}"
            logger.error("Event processing failed",
                        event_type=event_type,
                        event_id=event_id,
                        error=str(e),
                        exc_info=True)
            
            event_logger.log_event_failed(event_id, error_msg)
            return None
    
    async def _call_event_handlers(self, event_type: str, event_data: Dict[str, Any], 
                                 event_actions: adk.EventActions):
        """Call registered event handlers"""
        handlers = self.event_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event_data)
                else:
                    result = handler(event_data)
                
                # Merge handler results into event_actions
                if isinstance(result, adk.EventActions):
                    if result.state_delta:
                        event_actions.state_delta.update(result.state_delta)
                    # Could merge other EventActions fields here
                    
            except Exception as e:
                logger.error("Event handler failed",
                           event_type=event_type,
                           handler=handler.__name__,
                           error=str(e))
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for specific event types"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info("Registered event handler",
                   event_type=event_type,
                   handler=handler.__name__)
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """Unregister an event handler"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                logger.info("Unregistered event handler",
                           event_type=event_type,
                           handler=handler.__name__)
            except ValueError:
                logger.warning("Handler not found for unregistration",
                             event_type=event_type,
                             handler=handler.__name__)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics"""
        uptime = time.time() - self.start_time
        return {
            "is_running": self.is_running,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "success_rate": self.processed_events / (self.processed_events + self.failed_events) * 100 
                          if (self.processed_events + self.failed_events) > 0 else 0,
            "events_per_second": self.processed_events / uptime if uptime > 0 else 0,
            "uptime_seconds": round(uptime, 2),
            "registered_handlers": {
                event_type: len(handlers) 
                for event_type, handlers in self.event_handlers.items()
            }
        }
    
    async def handle_spawn_event(self, event_data: Dict[str, Any]) -> adk.EventActions:
        """Special handler for spawn events - critical for bot initialization"""
        event_actions = adk.EventActions()
        
        spawn_data = event_data.get('data', {})
        
        # Set comprehensive spawn state
        event_actions.state_delta = {
            "minecraft.spawned": True,
            "minecraft.bot.ready": True,
            "minecraft.connection.status": "connected",
            "minecraft.spawn_time": spawn_data.get('time', time.time()),
        }
        
        # Add position if available
        if 'position' in spawn_data and spawn_data['position']:
            pos = spawn_data['position']
            event_actions.state_delta.update({
                "minecraft.bot.position.x": pos.get('x', 0),
                "minecraft.bot.position.y": pos.get('y', 0), 
                "minecraft.bot.position.z": pos.get('z', 0),
                "minecraft.bot.position.last_update": spawn_data.get('time', time.time())
            })
        
        # Add health if available
        if 'health' in spawn_data:
            event_actions.state_delta["minecraft.bot.health"] = spawn_data['health']
        if 'food' in spawn_data:
            event_actions.state_delta["minecraft.bot.food"] = spawn_data['food']
        
        logger.info("Processed spawn event with comprehensive state",
                   event_id=event_data.get('eventId'),
                   state_keys=list(event_actions.state_delta.keys()))
        
        return event_actions
    
    async def handle_chat_event(self, event_data: Dict[str, Any]) -> adk.EventActions:
        """Special handler for chat events"""
        event_actions = adk.EventActions()
        
        chat_data = event_data.get('data', {})
        username = chat_data.get('username', 'unknown')
        message = chat_data.get('message', '')
        
        # Store recent chat history
        event_actions.state_delta = {
            f"minecraft.chat.recent.{username}": {
                "message": message,
                "time": chat_data.get('time', time.time())
            },
            "minecraft.chat.last_message": message,
            "minecraft.chat.last_speaker": username,
            "minecraft.chat.last_time": chat_data.get('time', time.time())
        }
        
        # Trigger chat processing flag for agents
        if message.strip():
            event_actions.state_delta["minecraft.chat.needs_response"] = True
        
        return event_actions
    
    def register_default_handlers(self):
        """Register default event handlers for common events"""
        self.register_handler("minecraft:spawn", self.handle_spawn_event)
        self.register_handler("minecraft:chat", self.handle_chat_event)
        
        logger.info("Registered default event handlers",
                   handlers=["spawn", "chat"])


# Global adapter instance
adk_adapter = ADKEventAdapter()