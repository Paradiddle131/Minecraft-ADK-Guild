"""
Event Registry - Centralized event definitions and metadata for Minecraft-ADK bridge
"""
from dataclasses import dataclass
from typing import Any, Dict, Type, Optional
from pydantic import BaseModel
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EventMetadata:
    """Metadata for a registered event type"""
    description: str
    payload_schema: Type[BaseModel]
    adk_state_mapping: Dict[str, str]
    priority: int = 0  # Higher priority events processed first
    batch_enabled: bool = False  # Can this event be batched
    sampling_rate: float = 1.0  # Rate at which to sample this event (0.0-1.0)


class MinecraftSpawnPayload(BaseModel):
    """Payload for minecraft:spawn event"""
    spawned: bool
    position: Optional[Dict[str, float]] = None
    time: int


class MinecraftChatPayload(BaseModel):
    """Payload for minecraft:chat event"""
    username: str
    message: str
    time: int


class MinecraftPlayerJoinedPayload(BaseModel):
    """Payload for minecraft:player_joined event"""
    username: str
    uuid: str
    time: int


class MinecraftPlayerLeftPayload(BaseModel):
    """Payload for minecraft:player_left event"""
    username: str
    uuid: str
    time: int


class MinecraftPositionPayload(BaseModel):
    """Payload for minecraft:position event"""
    x: float
    y: float
    z: float
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    time: int


class MinecraftHealthPayload(BaseModel):
    """Payload for minecraft:health event"""
    health: float
    food: int
    saturation: float
    time: int


class MinecraftBlockUpdatePayload(BaseModel):
    """Payload for minecraft:block_update event"""
    position: Dict[str, int]
    old_block: Optional[str] = None
    new_block: str
    time: int


class MinecraftEntitySpawnPayload(BaseModel):
    """Payload for minecraft:entity_spawn event"""
    entity_id: int
    entity_type: str
    position: Dict[str, float]
    time: int


class MinecraftEntityDeathPayload(BaseModel):
    """Payload for minecraft:entity_death event"""
    entity_id: int
    entity_type: str
    position: Dict[str, float]
    time: int


class MinecraftInventoryChangePayload(BaseModel):
    """Payload for minecraft:inventory_change event"""
    slot: int
    item_name: Optional[str] = None
    count: int
    time: int


class EventRegistry:
    """Registry for all Minecraft event types and their metadata"""
    
    def __init__(self):
        self._events: Dict[str, EventMetadata] = {}
        self._initialize_default_events()
    
    def _initialize_default_events(self):
        """Initialize the default Minecraft events"""
        
        # Core lifecycle events
        self.register_event(
            "minecraft:spawn",
            EventMetadata(
                description="Bot successfully spawned in world",
                payload_schema=MinecraftSpawnPayload,
                adk_state_mapping={
                    "minecraft.spawned": "spawned",
                    "minecraft.position": "position",
                    "minecraft.spawn_time": "time"
                },
                priority=100  # High priority - critical for initialization
            )
        )
        
        # Communication events
        self.register_event(
            "minecraft:chat",
            EventMetadata(
                description="Chat message received",
                payload_schema=MinecraftChatPayload,
                adk_state_mapping={
                    "minecraft.last_chat.username": "username",
                    "minecraft.last_chat.message": "message",
                    "minecraft.last_chat.time": "time"
                },
                priority=50
            )
        )
        
        # Player events
        self.register_event(
            "minecraft:player_joined",
            EventMetadata(
                description="Player joined the server",
                payload_schema=MinecraftPlayerJoinedPayload,
                adk_state_mapping={
                    "minecraft.players.{username}.joined": "time",
                    "minecraft.players.{username}.uuid": "uuid"
                },
                priority=30
            )
        )
        
        self.register_event(
            "minecraft:player_left",
            EventMetadata(
                description="Player left the server",
                payload_schema=MinecraftPlayerLeftPayload,
                adk_state_mapping={
                    "minecraft.players.{username}.left": "time"
                },
                priority=30
            )
        )
        
        # Bot state events
        self.register_event(
            "minecraft:position",
            EventMetadata(
                description="Bot position updated",
                payload_schema=MinecraftPositionPayload,
                adk_state_mapping={
                    "minecraft.bot.position.x": "x",
                    "minecraft.bot.position.y": "y", 
                    "minecraft.bot.position.z": "z",
                    "minecraft.bot.position.yaw": "yaw",
                    "minecraft.bot.position.pitch": "pitch",
                    "minecraft.bot.position.last_update": "time"
                },
                priority=5,  # Low priority - high frequency
                batch_enabled=True,
                sampling_rate=0.1  # Sample only 10% of position updates
            )
        )
        
        self.register_event(
            "minecraft:health",
            EventMetadata(
                description="Bot health/hunger updated",
                payload_schema=MinecraftHealthPayload,
                adk_state_mapping={
                    "minecraft.bot.health": "health",
                    "minecraft.bot.food": "food",
                    "minecraft.bot.saturation": "saturation",
                    "minecraft.bot.health_last_update": "time"
                },
                priority=75  # High priority - important for survival
            )
        )
        
        # World events
        self.register_event(
            "minecraft:block_update",
            EventMetadata(
                description="Block changed in loaded chunks",
                payload_schema=MinecraftBlockUpdatePayload,
                adk_state_mapping={
                    "minecraft.world.block_updates.last.position": "position",
                    "minecraft.world.block_updates.last.new_block": "new_block",
                    "minecraft.world.block_updates.last.time": "time"
                },
                priority=10,
                batch_enabled=True
            )
        )
        
        # Entity events
        self.register_event(
            "minecraft:entity_spawn",
            EventMetadata(
                description="New entity spawned",
                payload_schema=MinecraftEntitySpawnPayload,
                adk_state_mapping={
                    "minecraft.entities.{entity_id}.type": "entity_type",
                    "minecraft.entities.{entity_id}.position": "position",
                    "minecraft.entities.{entity_id}.spawn_time": "time"
                },
                priority=20
            )
        )
        
        self.register_event(
            "minecraft:entity_death",
            EventMetadata(
                description="Entity died",
                payload_schema=MinecraftEntityDeathPayload,
                adk_state_mapping={
                    "minecraft.entities.{entity_id}.death_time": "time",
                    "minecraft.entities.{entity_id}.death_position": "position"
                },
                priority=25
            )
        )
        
        # Inventory events
        self.register_event(
            "minecraft:inventory_change",
            EventMetadata(
                description="Inventory slot changed",
                payload_schema=MinecraftInventoryChangePayload,
                adk_state_mapping={
                    "minecraft.bot.inventory.slots.{slot}.item": "item_name",
                    "minecraft.bot.inventory.slots.{slot}.count": "count",
                    "minecraft.bot.inventory.last_change": "time"
                },
                priority=40
            )
        )
    
    def register_event(self, event_type: str, metadata: EventMetadata):
        """Register a new event type"""
        self._events[event_type] = metadata
        logger.debug("Registered event type", event_type=event_type, 
                    description=metadata.description)
    
    def get_event_metadata(self, event_type: str) -> Optional[EventMetadata]:
        """Get metadata for an event type"""
        return self._events.get(event_type)
    
    def validate_event_payload(self, event_type: str, payload: Dict[str, Any]) -> Any:
        """Validate an event payload against its schema"""
        metadata = self.get_event_metadata(event_type)
        if not metadata:
            raise ValueError(f"Unknown event type: {event_type}")
        
        try:
            return metadata.payload_schema(**payload)
        except Exception as e:
            logger.error("Event payload validation failed", 
                        event_type=event_type, payload=payload, error=str(e))
            raise ValueError(f"Invalid payload for {event_type}: {e}")
    
    def get_adk_state_mapping(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get ADK state mappings for an event, with placeholder substitution"""
        metadata = self.get_event_metadata(event_type)
        if not metadata:
            return {}
        
        state_delta = {}
        for state_key, payload_key in metadata.adk_state_mapping.items():
            # Handle placeholder substitution (e.g., {username}, {entity_id})
            resolved_state_key = self._resolve_placeholders(state_key, payload)
            
            if payload_key in payload:
                state_delta[resolved_state_key] = payload[payload_key]
        
        return state_delta
    
    def _resolve_placeholders(self, template: str, payload: Dict[str, Any]) -> str:
        """Resolve placeholders in state key templates"""
        result = template
        for key, value in payload.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    def get_event_priority(self, event_type: str) -> int:
        """Get the priority for an event type"""
        metadata = self.get_event_metadata(event_type)
        return metadata.priority if metadata else 0
    
    def is_batch_enabled(self, event_type: str) -> bool:
        """Check if batching is enabled for an event type"""
        metadata = self.get_event_metadata(event_type)
        return metadata.batch_enabled if metadata else False
    
    def get_sampling_rate(self, event_type: str) -> float:
        """Get the sampling rate for an event type"""
        metadata = self.get_event_metadata(event_type)
        return metadata.sampling_rate if metadata else 1.0
    
    def list_events(self) -> Dict[str, str]:
        """List all registered events with descriptions"""
        return {
            event_type: metadata.description 
            for event_type, metadata in self._events.items()
        }


# Global registry instance
event_registry = EventRegistry()