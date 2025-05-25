"""
Bridge Connector - Integrates event bridge with existing bridge manager
"""
import asyncio
from typing import Any, Dict, Optional

import structlog

from .adk_adapter import adk_adapter
from .event_queue import priority_queue  
from .event_logger import event_logger
from .event_handlers import handler_registry

logger = structlog.get_logger(__name__)


class EventBridgeConnector:
    """Connects the new event bridge architecture with the existing bridge manager"""
    
    def __init__(self, bridge_manager=None):
        self.bridge_manager = bridge_manager
        self.is_connected = False
        self.event_handler_registered = False
        
    async def initialize(self, bridge_manager):
        """Initialize the connector with the bridge manager"""
        self.bridge_manager = bridge_manager
        
        # Start event bridge components
        await event_logger.start()
        await adk_adapter.start()
        await priority_queue.start()
        
        # Register default handlers
        adk_adapter.register_default_handlers()
        
        # Connect to bridge manager's event system
        await self._connect_to_bridge_events()
        
        self.is_connected = True
        logger.info("EventBridgeConnector initialized and connected")
    
    async def _connect_to_bridge_events(self):
        """Connect to the bridge manager's event system"""
        if not self.bridge_manager:
            logger.warning("No bridge manager available for event connection")
            return
        
        # Register with the bridge manager to receive events
        if hasattr(self.bridge_manager, 'register_event_handler'):
            # Register for all minecraft: events
            self.bridge_manager.register_event_handler('minecraft_event', self._handle_bridge_event)
            self.event_handler_registered = True
            logger.info("Registered event handler with bridge manager")
        else:
            logger.warning("Bridge manager does not support event handler registration")
    
    async def _handle_bridge_event(self, event_data: Dict[str, Any]):
        """Handle events from the bridge manager"""
        try:
            # Enqueue the event for processing
            success = await priority_queue.enqueue(event_data)
            
            if success:
                logger.debug("Event enqueued from bridge",
                           event_type=event_data.get('event'),
                           event_id=event_data.get('eventId'))
            else:
                logger.warning("Failed to enqueue event from bridge",
                             event_data=event_data)
        
        except Exception as e:
            logger.error("Error handling bridge event",
                        event_data=event_data,
                        error=str(e))
    
    async def process_minecraft_event_direct(self, event_data: Dict[str, Any]) -> Optional[Any]:
        """
        Process a Minecraft event directly through the event bridge
        
        Args:
            event_data: Event data from JavaScript
            
        Returns:
            Processing result from ADK adapter
        """
        if not self.is_connected:
            logger.warning("Connector not initialized, dropping event",
                          event_data=event_data)
            return None
        
        try:
            # Process through ADK adapter
            result = await adk_adapter.process_minecraft_event(event_data)
            return result
            
        except Exception as e:
            logger.error("Direct event processing failed",
                        event_data=event_data,
                        error=str(e))
            return None
    
    def register_queue_handler(self, event_type: str, handler):
        """Register a handler with the priority queue"""
        priority_queue.register_handler(event_type, handler)
        logger.info("Handler registered with priority queue",
                   event_type=event_type,
                   handler=getattr(handler, '__name__', str(handler)))
    
    def get_bridge_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all bridge components"""
        return {
            "connector": {
                "is_connected": self.is_connected,
                "event_handler_registered": self.event_handler_registered,
                "has_bridge_manager": self.bridge_manager is not None
            },
            "adk_adapter": adk_adapter.get_stats() if adk_adapter else {},
            "priority_queue": priority_queue.get_stats() if priority_queue else {},
            "event_logger": event_logger.get_performance_summary() if event_logger else {},
            "handler_registry": handler_registry.get_handler_stats() if handler_registry else {}
        }
    
    async def shutdown(self):
        """Shutdown all event bridge components"""
        logger.info("Shutting down event bridge connector")
        
        try:
            # Stop components in reverse order
            if priority_queue:
                await priority_queue.stop()
            
            if adk_adapter:
                await adk_adapter.stop()
            
            if event_logger:
                await event_logger.stop()
            
            self.is_connected = False
            logger.info("Event bridge connector shutdown complete")
            
        except Exception as e:
            logger.error("Error during connector shutdown", error=str(e))


# Global connector instance
bridge_connector = EventBridgeConnector()


async def initialize_event_bridge(bridge_manager=None):
    """Initialize the complete event bridge system"""
    logger.info("Initializing complete event bridge system")
    
    try:
        await bridge_connector.initialize(bridge_manager)
        logger.info("Event bridge system initialized successfully")
        return bridge_connector
        
    except Exception as e:
        logger.error("Failed to initialize event bridge system", error=str(e))
        raise


async def shutdown_event_bridge():
    """Shutdown the complete event bridge system"""
    logger.info("Shutting down complete event bridge system")
    
    try:
        await bridge_connector.shutdown()
        logger.info("Event bridge system shutdown complete")
        
    except Exception as e:
        logger.error("Error shutting down event bridge system", error=str(e))