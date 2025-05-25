"""
Event Registry - Centralized event definitions and metadata for Minecraft-ADK bridge
"""
from dataclasses import dataclass
from typing import Any, Dict, Type, Optional, List
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


class MinecraftPlayerUpdatedPayload(BaseModel):
    """Payload for minecraft:player_updated event"""
    username: str
    uuid: str
    position: Optional[Dict[str, float]] = None
    ping: Optional[int] = None
    gamemode: Optional[str] = None
    time: int


class MinecraftEntityMovePayload(BaseModel):
    """Payload for minecraft:entity_move event"""
    entity_id: int
    entity_type: str
    old_position: Dict[str, float]
    new_position: Dict[str, float]
    velocity: Optional[Dict[str, float]] = None
    time: int


class MinecraftEntityDamagePayload(BaseModel):
    """Payload for minecraft:entity_damage event"""
    entity_id: int
    entity_type: str
    damage: float
    cause: Optional[str] = None
    attacker_id: Optional[int] = None
    time: int


class MinecraftBotDeathPayload(BaseModel):
    """Payload for minecraft:bot_death event"""
    cause: str
    position: Dict[str, float]
    killer: Optional[str] = None
    time: int


class MinecraftBotRespawnPayload(BaseModel):
    """Payload for minecraft:bot_respawn event"""
    position: Dict[str, float]
    dimension: str
    time: int


class MinecraftBlockBreakPayload(BaseModel):
    """Payload for minecraft:block_break event"""
    position: Dict[str, int]
    block_type: str
    block_name: str
    tool_used: Optional[str] = None
    player: Optional[str] = None
    time: int


class MinecraftBlockPlacePayload(BaseModel):
    """Payload for minecraft:block_place event"""
    position: Dict[str, int]
    block_type: str
    block_name: str
    placed_by: Optional[str] = None
    time: int


class MinecraftExplosionPayload(BaseModel):
    """Payload for minecraft:explosion event"""
    position: Dict[str, float]
    power: float
    affected_blocks: List[Dict[str, int]]
    cause: Optional[str] = None
    time: int


class MinecraftWeatherChangePayload(BaseModel):
    """Payload for minecraft:weather_change event"""
    old_weather: str
    new_weather: str
    thundering: bool
    raining: bool
    time: int


class MinecraftTimeChangePayload(BaseModel):
    """Payload for minecraft:time_change event"""
    time_of_day: int
    age: int
    is_day: bool
    is_night: bool
    time: int


class MinecraftChunkLoadPayload(BaseModel):
    """Payload for minecraft:chunk_load event"""
    chunk_x: int
    chunk_z: int
    dimension: str
    time: int


class MinecraftChunkUnloadPayload(BaseModel):
    """Payload for minecraft:chunk_unload event"""
    chunk_x: int
    chunk_z: int
    dimension: str
    time: int


class MinecraftContainerOpenPayload(BaseModel):
    """Payload for minecraft:container_open event"""
    container_type: str
    container_position: Optional[Dict[str, int]] = None
    container_size: int
    time: int


class MinecraftContainerClosePayload(BaseModel):
    """Payload for minecraft:container_close event"""
    container_type: str
    container_position: Optional[Dict[str, int]] = None
    time: int


class MinecraftItemDropPayload(BaseModel):
    """Payload for minecraft:item_drop event"""
    item_name: str
    count: int
    position: Dict[str, float]
    entity_id: Optional[int] = None
    time: int


class MinecraftItemPickupPayload(BaseModel):
    """Payload for minecraft:item_pickup event"""
    item_name: str
    count: int
    position: Dict[str, float]
    entity_id: Optional[int] = None
    time: int


class MinecraftItemCraftPayload(BaseModel):
    """Payload for minecraft:item_craft event"""
    recipe_name: str
    result_item: str
    result_count: int
    ingredients: List[Dict[str, Any]]
    time: int


class MinecraftItemConsumePayload(BaseModel):
    """Payload for minecraft:item_consume event"""
    item_name: str
    food_points: Optional[int] = None
    saturation: Optional[float] = None
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
                    "minecraft.players.{username}.uuid": "uuid",
                    "minecraft.players.{username}.online": True
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
                    "minecraft.players.{username}.left": "time",
                    "minecraft.players.{username}.online": False
                },
                priority=30
            )
        )
        
        self.register_event(
            "minecraft:player_updated",
            EventMetadata(
                description="Player information updated",
                payload_schema=MinecraftPlayerUpdatedPayload,
                adk_state_mapping={
                    "minecraft.players.{username}.position": "position",
                    "minecraft.players.{username}.ping": "ping",
                    "minecraft.players.{username}.gamemode": "gamemode",
                    "minecraft.players.{username}.last_update": "time"
                },
                priority=10,
                batch_enabled=True,
                sampling_rate=0.2  # Sample 20% of player updates
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
        
        self.register_event(
            "minecraft:block_break",
            EventMetadata(
                description="Block broken by player or bot",
                payload_schema=MinecraftBlockBreakPayload,
                adk_state_mapping={
                    "minecraft.world.last_block_break.position": "position",
                    "minecraft.world.last_block_break.block_type": "block_type",
                    "minecraft.world.last_block_break.player": "player",
                    "minecraft.world.last_block_break.time": "time"
                },
                priority=40
            )
        )
        
        self.register_event(
            "minecraft:block_place",
            EventMetadata(
                description="Block placed by player or bot",
                payload_schema=MinecraftBlockPlacePayload,
                adk_state_mapping={
                    "minecraft.world.last_block_place.position": "position",
                    "minecraft.world.last_block_place.block_type": "block_type",
                    "minecraft.world.last_block_place.player": "placed_by",
                    "minecraft.world.last_block_place.time": "time"
                },
                priority=40
            )
        )
        
        self.register_event(
            "minecraft:explosion",
            EventMetadata(
                description="Explosion occurred in world",
                payload_schema=MinecraftExplosionPayload,
                adk_state_mapping={
                    "minecraft.world.last_explosion.position": "position",
                    "minecraft.world.last_explosion.power": "power",
                    "minecraft.world.last_explosion.cause": "cause",
                    "minecraft.world.last_explosion.time": "time",
                    "minecraft.world.last_explosion.affected_blocks_count": lambda payload: len(payload.get('affected_blocks', []))
                },
                priority=80
            )
        )
        
        self.register_event(
            "minecraft:weather_change",
            EventMetadata(
                description="Weather conditions changed",
                payload_schema=MinecraftWeatherChangePayload,
                adk_state_mapping={
                    "minecraft.world.weather.current": "new_weather",
                    "minecraft.world.weather.previous": "old_weather",
                    "minecraft.world.weather.thundering": "thundering",
                    "minecraft.world.weather.raining": "raining",
                    "minecraft.world.weather.last_change": "time"
                },
                priority=20
            )
        )
        
        self.register_event(
            "minecraft:time_change",
            EventMetadata(
                description="World time changed",
                payload_schema=MinecraftTimeChangePayload,
                adk_state_mapping={
                    "minecraft.world.time.time_of_day": "time_of_day",
                    "minecraft.world.time.age": "age",
                    "minecraft.world.time.is_day": "is_day",
                    "minecraft.world.time.is_night": "is_night",
                    "minecraft.world.time.last_update": "time"
                },
                priority=5,
                batch_enabled=True,
                sampling_rate=0.1  # Sample 10% of time updates
            )
        )
        
        self.register_event(
            "minecraft:chunk_load",
            EventMetadata(
                description="Chunk loaded into memory",
                payload_schema=MinecraftChunkLoadPayload,
                adk_state_mapping={
                    "minecraft.world.chunks.loaded.{chunk_x}_{chunk_z}": True,
                    "minecraft.world.chunks.load_time.{chunk_x}_{chunk_z}": "time"
                },
                priority=15,
                batch_enabled=True
            )
        )
        
        self.register_event(
            "minecraft:chunk_unload",
            EventMetadata(
                description="Chunk unloaded from memory",
                payload_schema=MinecraftChunkUnloadPayload,
                adk_state_mapping={
                    "minecraft.world.chunks.loaded.{chunk_x}_{chunk_z}": False,
                    "minecraft.world.chunks.unload_time.{chunk_x}_{chunk_z}": "time"
                },
                priority=15,
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
                    "minecraft.entities.{entity_id}.spawn_time": "time",
                    "minecraft.entities.{entity_id}.alive": True
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
                    "minecraft.entities.{entity_id}.death_position": "position",
                    "minecraft.entities.{entity_id}.alive": False
                },
                priority=25
            )
        )
        
        self.register_event(
            "minecraft:entity_move",
            EventMetadata(
                description="Entity moved to new position",
                payload_schema=MinecraftEntityMovePayload,
                adk_state_mapping={
                    "minecraft.entities.{entity_id}.position": "new_position",
                    "minecraft.entities.{entity_id}.velocity": "velocity",
                    "minecraft.entities.{entity_id}.last_move": "time"
                },
                priority=5,
                batch_enabled=True,
                sampling_rate=0.1  # Sample 10% of entity movements
            )
        )
        
        self.register_event(
            "minecraft:entity_damage",
            EventMetadata(
                description="Entity took damage",
                payload_schema=MinecraftEntityDamagePayload,
                adk_state_mapping={
                    "minecraft.entities.{entity_id}.last_damage": "damage",
                    "minecraft.entities.{entity_id}.damage_cause": "cause",
                    "minecraft.entities.{entity_id}.damage_time": "time"
                },
                priority=30
            )
        )
        
        # Bot lifecycle events
        self.register_event(
            "minecraft:bot_death",
            EventMetadata(
                description="Bot died",
                payload_schema=MinecraftBotDeathPayload,
                adk_state_mapping={
                    "minecraft.bot.alive": False,
                    "minecraft.bot.death_cause": "cause",
                    "minecraft.bot.death_position": "position",
                    "minecraft.bot.death_time": "time",
                    "minecraft.bot.killer": "killer"
                },
                priority=100  # Critical event
            )
        )
        
        self.register_event(
            "minecraft:bot_respawn",
            EventMetadata(
                description="Bot respawned",
                payload_schema=MinecraftBotRespawnPayload,
                adk_state_mapping={
                    "minecraft.bot.alive": True,
                    "minecraft.bot.respawn_position": "position",
                    "minecraft.bot.dimension": "dimension",
                    "minecraft.bot.respawn_time": "time"
                },
                priority=90
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
        
        # Container events
        self.register_event(
            "minecraft:container_open",
            EventMetadata(
                description="Container/chest opened",
                payload_schema=MinecraftContainerOpenPayload,
                adk_state_mapping={
                    "minecraft.containers.current.type": "container_type",
                    "minecraft.containers.current.position": "container_position",
                    "minecraft.containers.current.size": "container_size",
                    "minecraft.containers.current.opened_at": "time",
                    "minecraft.containers.current.is_open": True
                },
                priority=50
            )
        )
        
        self.register_event(
            "minecraft:container_close",
            EventMetadata(
                description="Container/chest closed",
                payload_schema=MinecraftContainerClosePayload,
                adk_state_mapping={
                    "minecraft.containers.current.is_open": False,
                    "minecraft.containers.current.closed_at": "time"
                },
                priority=45
            )
        )
        
        # Item interaction events
        self.register_event(
            "minecraft:item_drop",
            EventMetadata(
                description="Item dropped on ground",
                payload_schema=MinecraftItemDropPayload,
                adk_state_mapping={
                    "minecraft.items.last_dropped.name": "item_name",
                    "minecraft.items.last_dropped.count": "count",
                    "minecraft.items.last_dropped.position": "position",
                    "minecraft.items.last_dropped.time": "time"
                },
                priority=35
            )
        )
        
        self.register_event(
            "minecraft:item_pickup",
            EventMetadata(
                description="Item picked up from ground",
                payload_schema=MinecraftItemPickupPayload,
                adk_state_mapping={
                    "minecraft.items.last_pickup.name": "item_name",
                    "minecraft.items.last_pickup.count": "count",
                    "minecraft.items.last_pickup.position": "position",
                    "minecraft.items.last_pickup.time": "time"
                },
                priority=35
            )
        )
        
        self.register_event(
            "minecraft:item_craft",
            EventMetadata(
                description="Item crafted by player or bot",
                payload_schema=MinecraftItemCraftPayload,
                adk_state_mapping={
                    "minecraft.crafting.last_recipe": "recipe_name",
                    "minecraft.crafting.last_result": "result_item",
                    "minecraft.crafting.last_count": "result_count",
                    "minecraft.crafting.last_time": "time"
                },
                priority=60
            )
        )
        
        self.register_event(
            "minecraft:item_consume",
            EventMetadata(
                description="Item consumed (food, potion, etc.)",
                payload_schema=MinecraftItemConsumePayload,
                adk_state_mapping={
                    "minecraft.consumption.last_item": "item_name",
                    "minecraft.consumption.food_points": "food_points",
                    "minecraft.consumption.saturation": "saturation",
                    "minecraft.consumption.last_time": "time"
                },
                priority=55
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