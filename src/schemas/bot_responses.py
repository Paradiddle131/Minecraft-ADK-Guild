"""Response schemas for bot operations - internal Pydantic models."""

from typing import Optional, Dict, Any, List, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime

from .bot_commands import Position3D


class BaseResponse(BaseModel):
    """Base response for all bot commands."""
    status: Literal["success", "error", "timeout", "partial"]
    timestamp: datetime = Field(default_factory=datetime.now)
    execution_time_ms: Optional[int] = Field(None, description="Command execution time")


class ErrorDetails(BaseModel):
    """Detailed error information."""
    error_type: str = Field(..., description="Error classification")
    message: str = Field(..., description="Human-readable error message")
    suggestion: Optional[str] = Field(None, description="Suggested action to resolve")
    retry_after_ms: Optional[int] = Field(None, description="Suggested retry delay")


class TimeoutError(ErrorDetails):
    """Timeout-specific error details."""
    error_type: Literal["timeout"] = "timeout"
    timeout_ms: int = Field(..., description="Timeout duration that was exceeded")
    elapsed_ms: int = Field(..., description="Actual time elapsed")
    last_known_position: Optional[Position3D] = None


# Movement Responses
class MoveToResponse(BaseResponse):
    """Response from movement command."""
    target_position: Position3D
    actual_position: Optional[Position3D] = Field(None, description="Final position reached")
    distance_traveled: Optional[float] = Field(None, description="Custom calculated distance")
    error_details: Optional[Union[ErrorDetails, TimeoutError]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "target_position": {"x": 100, "y": 64, "z": 100},
                "actual_position": {"x": 100.5, "y": 64, "z": 100.5},
                "distance_traveled": 50.2
            }
        }


# Block Interaction Responses
class DigBlockResponse(BaseResponse):
    """Response from dig command."""
    position: Position3D
    block_type: Optional[str] = Field(None, description="Type of block that was dug")
    drops: Optional[List[Dict[str, Any]]] = Field(None, description="Items dropped")
    tool_used: Optional[str] = Field(None, description="Tool that was used")
    dig_time_ms: Optional[int] = Field(None, description="Time taken to dig")
    error_details: Optional[ErrorDetails] = None


class PlaceBlockResponse(BaseResponse):
    """Response from place block command."""
    position: Position3D
    block_placed: Optional[str] = Field(None, description="Name of block placed")
    error_details: Optional[ErrorDetails] = None


# Craft Response
class CraftItemResponse(BaseResponse):
    """Response from craft command."""
    item_name: str
    count_requested: int
    count_crafted: Optional[int] = Field(None, description="Actual number crafted")
    recipes_used: Optional[List[str]] = Field(None, description="Recipe names used")
    error_details: Optional[ErrorDetails] = None


# Inventory Responses  
class InventoryItem(BaseModel):
    """Single inventory item."""
    name: str
    count: int
    slot: int
    metadata: Optional[Dict[str, Any]] = None
    

class GetInventoryResponse(BaseResponse):
    """Response from inventory query."""
    items: List[InventoryItem] = Field(default_factory=list)
    empty_slots: int = Field(..., description="Number of empty inventory slots")
    categories: Optional[Dict[str, List[InventoryItem]]] = None
    error_details: Optional[ErrorDetails] = None


# Position Response
class GetPositionResponse(BaseResponse):
    """Response from position query."""
    position: Optional[Position3D] = None
    error_details: Optional[ErrorDetails] = None