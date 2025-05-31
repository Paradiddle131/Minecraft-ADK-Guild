"""Progress tracking schemas for long-running operations."""

from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

from .bot_commands import Position3D


class ProgressUpdate(BaseModel):
    """Progress update for long-running operations."""
    operation_id: str = Field(..., description="Unique operation identifier")
    operation_type: str = Field(..., description="Type of operation")
    progress_percent: float = Field(..., ge=0, le=100)
    status_message: str
    elapsed_ms: int
    estimated_remaining_ms: Optional[int] = None
    current_state: Optional[Dict[str, Any]] = None
    

class PathfindingProgress(ProgressUpdate):
    """Progress specific to pathfinding - custom tracking only."""
    operation_type: Literal["pathfinding"] = "pathfinding"
    current_position: Position3D
    target_position: Position3D
    distance_remaining: float
    # NOTE: obstacles_encountered, path_recalculations removed - not available from Mineflayer
    status_message: str  # Custom progress messages