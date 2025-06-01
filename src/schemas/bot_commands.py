"""Command schemas for bot operations - matches Mineflayer API exactly."""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal, Union
from enum import Enum


class Position3D(BaseModel):
    """3D position in Minecraft world."""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate") 
    z: float = Field(..., description="Z coordinate")
    
    @validator('y')
    def validate_y_bounds(cls, v):
        if v < -64 or v > 320:
            raise ValueError(f"Y coordinate {v} out of bounds (-64 to 320)")
        return v


# Movement Commands
class MoveToCommand(BaseModel):
    """Command to move bot to coordinates."""
    position: Position3D
    timeout_ms: Optional[int] = Field(None, description="Override default timeout")
    sprint: bool = Field(False, description="Whether to sprint")


# Block Interaction Commands
class DigBlockCommand(BaseModel):
    """Command to dig/mine a block - matches Mineflayer API."""
    position: Position3D
    force_look: bool = Field(True, description="Whether to look at block first")
    dig_face: Optional[str] = Field(None, description="Which face to dig from")


class PlaceBlockCommand(BaseModel):
    """Command to place a block."""
    reference_position: Position3D
    face: str = Field(..., description="Block face to place against")
    item_name: str = Field(..., description="Name of block/item to place")


# Craft Command with Proper Validation
class CraftItemCommand(BaseModel):
    """Command to craft items using bot.craft()."""
    recipe_name: str = Field(..., description="Recipe/item name to craft")
    count: int = Field(1, ge=1, le=64, description="Number to craft")
    crafting_table: Optional[Position3D] = Field(None, description="Position of crafting table if required")


# Inventory Commands
class EquipItemCommand(BaseModel):
    """Command to equip an item."""
    item: Union[str, int] = Field(..., description="Item name or ID")
    destination: Literal["hand", "head", "torso", "legs", "feet", "off-hand"]


class GetInventoryCommand(BaseModel):
    """Command to get inventory - no parameters needed."""
    pass