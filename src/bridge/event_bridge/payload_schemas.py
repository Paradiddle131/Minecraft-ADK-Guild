"""
Common Payload Structures and Base Classes for Event Bridge
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger(__name__)


class BaseEventPayload(BaseModel):
    """Base payload structure for all Minecraft events"""
    
    time: int = Field(..., description="Event timestamp in milliseconds")
    
    class Config:
        extra = "forbid"  # Reject any extra fields not defined in schema
        validate_assignment = True  # Validate when fields are assigned
    
    @validator('time')
    def validate_time(cls, v):
        """Validate timestamp is reasonable"""
        if v <= 0:
            raise ValueError("Timestamp must be positive")
        # Check if timestamp is within reasonable bounds (not too far in future)
        current_ms = int(datetime.now().timestamp() * 1000)
        if v > current_ms + 60000:  # Allow 1 minute future tolerance
            raise ValueError("Timestamp cannot be more than 1 minute in the future")
        return v


class PositionModel(BaseModel):
    """Standardized position model"""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate") 
    z: float = Field(..., description="Z coordinate")
    
    @validator('x', 'y', 'z')
    def validate_coordinates(cls, v):
        """Validate coordinates are finite numbers"""
        if not isinstance(v, (int, float)):
            raise ValueError("Coordinates must be numbers")
        if abs(v) > 30000000:  # Minecraft world border limit
            raise ValueError("Coordinate exceeds world boundary")
        return float(v)


class BlockPositionModel(BaseModel):
    """Standardized block position model (integer coordinates)"""
    x: int = Field(..., description="Block X coordinate")
    y: int = Field(..., description="Block Y coordinate")
    z: int = Field(..., description="Block Z coordinate")
    
    @validator('x', 'z')
    def validate_horizontal_coords(cls, v):
        """Validate horizontal coordinates within world bounds"""
        if abs(v) > 29999984:  # Minecraft world limit
            raise ValueError("Block coordinate exceeds world boundary")
        return v
    
    @validator('y')
    def validate_vertical_coord(cls, v):
        """Validate Y coordinate within build limits"""
        if v < -2048 or v > 2047:  # Extended height limits
            raise ValueError("Y coordinate must be between -2048 and 2047")
        return v


class ItemModel(BaseModel):
    """Standardized item model"""
    name: str = Field(..., description="Item name/type")
    count: int = Field(1, description="Item count", ge=0, le=64)
    slot: Optional[int] = Field(None, description="Inventory slot", ge=0, le=255)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional item data")
    
    @validator('name')
    def validate_item_name(cls, v):
        """Validate item name format"""
        if not v or not isinstance(v, str):
            raise ValueError("Item name must be a non-empty string")
        # Basic validation - could be enhanced with actual item registry
        if len(v) > 100:
            raise ValueError("Item name too long")
        return v.lower().strip()


class PlayerModel(BaseModel):
    """Standardized player model"""
    username: str = Field(..., description="Player username")
    uuid: str = Field(..., description="Player UUID")
    position: Optional[PositionModel] = Field(None, description="Player position")
    ping: Optional[int] = Field(None, description="Player ping in ms", ge=0, le=10000)
    gamemode: Optional[str] = Field(None, description="Player gamemode")
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format"""
        if not v or len(v) < 3 or len(v) > 16:
            raise ValueError("Username must be 3-16 characters")
        return v.strip()
    
    @validator('uuid')
    def validate_uuid(cls, v):
        """Validate UUID format"""
        if not v or len(v) < 32:
            raise ValueError("UUID must be at least 32 characters")
        return v.strip()


class EntityModel(BaseModel):
    """Standardized entity model"""
    entity_id: int = Field(..., description="Entity ID")
    entity_type: str = Field(..., description="Entity type")
    position: PositionModel = Field(..., description="Entity position")
    velocity: Optional[PositionModel] = Field(None, description="Entity velocity")
    health: Optional[float] = Field(None, description="Entity health", ge=0)
    
    @validator('entity_id')
    def validate_entity_id(cls, v):
        """Validate entity ID"""
        if v < 0:
            raise ValueError("Entity ID must be non-negative")
        return v
    
    @validator('entity_type')
    def validate_entity_type(cls, v):
        """Validate entity type"""
        if not v or not isinstance(v, str):
            raise ValueError("Entity type must be a non-empty string")
        return v.lower().strip()


class ContainerModel(BaseModel):
    """Standardized container model"""
    container_type: str = Field(..., description="Container type")
    container_size: int = Field(..., description="Container size", ge=0, le=256)
    container_position: Optional[BlockPositionModel] = Field(None, description="Container position")
    
    @validator('container_type')
    def validate_container_type(cls, v):
        """Validate container type"""
        if not v:
            raise ValueError("Container type cannot be empty")
        return v.lower().strip()


class StandardEventMetadata(BaseModel):
    """Standard metadata included with all events"""
    event_id: str = Field(..., description="Unique event identifier")
    bot_id: str = Field(..., description="Bot identifier")
    timestamp: int = Field(..., description="Event timestamp")
    world_time: Optional[int] = Field(None, description="Minecraft world time")
    dimension: Optional[str] = Field(None, description="Current dimension")
    server_version: Optional[str] = Field(None, description="Server version")
    
    @validator('event_id')
    def validate_event_id(cls, v):
        """Validate event ID format"""
        if not v or len(v) < 10:
            raise ValueError("Event ID must be at least 10 characters")
        return v
    
    @validator('bot_id')
    def validate_bot_id(cls, v):
        """Validate bot ID"""
        if not v:
            raise ValueError("Bot ID cannot be empty")
        return v.strip()


class EventPayloadWrapper(BaseModel):
    """Wrapper for complete event payloads"""
    event: str = Field(..., description="Event type")
    data: BaseEventPayload = Field(..., description="Event data")
    metadata: StandardEventMetadata = Field(..., description="Event metadata")
    priority: Optional[int] = Field(0, description="Event priority")
    batch_id: Optional[str] = Field(None, description="Batch identifier")
    
    @validator('event')
    def validate_event_type(cls, v):
        """Validate event type format"""
        if not v or not v.startswith('minecraft:'):
            raise ValueError("Event type must start with 'minecraft:'")
        return v.lower()


class ValidationResult(BaseModel):
    """Result of payload validation"""
    valid: bool = Field(..., description="Whether payload is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    normalized_payload: Optional[Dict[str, Any]] = Field(None, description="Normalized payload")


class PayloadNormalizer:
    """Normalizes event payloads to standard format"""
    
    @staticmethod
    def normalize_position(pos: Union[Dict, PositionModel, None]) -> Optional[PositionModel]:
        """Normalize position data"""
        if pos is None:
            return None
        
        if isinstance(pos, PositionModel):
            return pos
        
        if isinstance(pos, dict):
            try:
                return PositionModel(**pos)
            except Exception as e:
                logger.warning("Failed to normalize position", pos=pos, error=str(e))
                return None
        
        return None
    
    @staticmethod
    def normalize_block_position(pos: Union[Dict, BlockPositionModel, None]) -> Optional[BlockPositionModel]:
        """Normalize block position data"""
        if pos is None:
            return None
        
        if isinstance(pos, BlockPositionModel):
            return pos
        
        if isinstance(pos, dict):
            try:
                # Convert float coordinates to integers
                if 'x' in pos and isinstance(pos['x'], float):
                    pos['x'] = int(pos['x'])
                if 'y' in pos and isinstance(pos['y'], float):
                    pos['y'] = int(pos['y'])
                if 'z' in pos and isinstance(pos['z'], float):
                    pos['z'] = int(pos['z'])
                
                return BlockPositionModel(**pos)
            except Exception as e:
                logger.warning("Failed to normalize block position", pos=pos, error=str(e))
                return None
        
        return None
    
    @staticmethod
    def normalize_item(item: Union[Dict, ItemModel, None]) -> Optional[ItemModel]:
        """Normalize item data"""
        if item is None:
            return None
        
        if isinstance(item, ItemModel):
            return item
        
        if isinstance(item, dict):
            try:
                return ItemModel(**item)
            except Exception as e:
                logger.warning("Failed to normalize item", item=item, error=str(e))
                return None
        
        return None
    
    @staticmethod
    def normalize_player(player: Union[Dict, PlayerModel, None]) -> Optional[PlayerModel]:
        """Normalize player data"""
        if player is None:
            return None
        
        if isinstance(player, PlayerModel):
            return player
        
        if isinstance(player, dict):
            try:
                # Normalize nested position
                if 'position' in player:
                    player['position'] = PayloadNormalizer.normalize_position(player['position'])
                
                return PlayerModel(**player)
            except Exception as e:
                logger.warning("Failed to normalize player", player=player, error=str(e))
                return None
        
        return None
    
    @staticmethod
    def normalize_entity(entity: Union[Dict, EntityModel, None]) -> Optional[EntityModel]:
        """Normalize entity data"""
        if entity is None:
            return None
        
        if isinstance(entity, EntityModel):
            return entity
        
        if isinstance(entity, dict):
            try:
                # Normalize nested positions
                if 'position' in entity:
                    entity['position'] = PayloadNormalizer.normalize_position(entity['position'])
                if 'velocity' in entity:
                    entity['velocity'] = PayloadNormalizer.normalize_position(entity['velocity'])
                
                return EntityModel(**entity)
            except Exception as e:
                logger.warning("Failed to normalize entity", entity=entity, error=str(e))
                return None
        
        return None


class PayloadValidator:
    """Validates event payloads against schemas"""
    
    def __init__(self):
        self.normalizer = PayloadNormalizer()
    
    def validate_payload(self, event_type: str, payload: Dict[str, Any]) -> ValidationResult:
        """Validate a complete event payload"""
        errors = []
        warnings = []
        
        try:
            # Validate basic structure
            if not isinstance(payload, dict):
                errors.append("Payload must be a dictionary")
                return ValidationResult(valid=False, errors=errors)
            
            # Validate required fields exist
            if 'time' not in payload:
                errors.append("Missing required field 'time'")
            
            # Normalize common fields
            normalized = payload.copy()
            
            # Normalize positions
            for pos_field in ['position', 'old_position', 'new_position', 'container_position']:
                if pos_field in normalized:
                    if pos_field.endswith('_position') and pos_field != 'position':
                        # Block positions
                        normalized[pos_field] = self.normalizer.normalize_block_position(
                            normalized[pos_field]
                        )
                    else:
                        # Regular positions
                        normalized[pos_field] = self.normalizer.normalize_position(
                            normalized[pos_field]
                        )
            
            # Normalize items
            for item_field in ['item', 'result_item', 'ingredients']:
                if item_field in normalized:
                    if item_field == 'ingredients' and isinstance(normalized[item_field], list):
                        normalized[item_field] = [
                            self.normalizer.normalize_item(item) 
                            for item in normalized[item_field]
                        ]
                    else:
                        normalized[item_field] = self.normalizer.normalize_item(
                            normalized[item_field]
                        )
            
            # Event-specific validations
            if event_type.endswith(':spawn'):
                if 'spawned' not in normalized:
                    warnings.append("Spawn event missing 'spawned' field")
            
            elif event_type.endswith(':health'):
                health = normalized.get('health')
                if health is not None and (health < 0 or health > 20):
                    warnings.append(f"Health value {health} is outside normal range (0-20)")
            
            elif event_type.endswith(':inventory_change'):
                slot = normalized.get('slot')
                if slot is not None and (slot < 0 or slot > 45):
                    warnings.append(f"Inventory slot {slot} is outside normal range (0-45)")
            
            # Return validation result
            is_valid = len(errors) == 0
            return ValidationResult(
                valid=is_valid,
                errors=errors,
                warnings=warnings,
                normalized_payload=normalized if is_valid else None
            )
            
        except Exception as e:
            errors.append(f"Validation failed with exception: {e}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
    
    def validate_wrapper(self, wrapper_data: Dict[str, Any]) -> ValidationResult:
        """Validate a complete event wrapper"""
        try:
            wrapper = EventPayloadWrapper(**wrapper_data)
            return ValidationResult(
                valid=True,
                normalized_payload=wrapper.dict()
            )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[f"Wrapper validation failed: {e}"]
            )


# Global validator instance
payload_validator = PayloadValidator()