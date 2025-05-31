"""Schema definitions for Minecraft bot commands and responses."""

from .bot_commands import *
from .bot_responses import *
from .progress import *

__all__ = [
    # Commands
    "Position3D",
    "MoveToCommand", 
    "DigBlockCommand",
    "PlaceBlockCommand",
    "CraftItemCommand",
    "EquipItemCommand",
    "GetInventoryCommand",
    # Responses
    "BaseResponse",
    "ErrorDetails",
    "TimeoutError",
    "MoveToResponse",
    "DigBlockResponse",
    "PlaceBlockResponse",
    "CraftItemResponse",
    "GetInventoryResponse",
    "GetPositionResponse",
    "InventoryItem",
    # Progress
    "ProgressUpdate",
    "PathfindingProgress",
]