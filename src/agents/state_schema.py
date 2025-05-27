"""
Shared State Schema for Multi-Agent Communication
Defines standardized state keys for agent coordination
"""

from typing import Final


class StateKeys:
    """Standardized state keys for agent communication"""
    
    # User context keys
    USER_REQUEST: Final[str] = "user_request"
    USER_ID: Final[str] = "user_id"
    
    # Minecraft world state keys
    MINECRAFT_INVENTORY: Final[str] = "minecraft.inventory"
    MINECRAFT_POSITION: Final[str] = "minecraft.position"
    MINECRAFT_NEARBY_BLOCKS: Final[str] = "minecraft.nearby_blocks"
    MINECRAFT_HEALTH: Final[str] = "minecraft.health"
    MINECRAFT_FOOD: Final[str] = "minecraft.food"
    
    # Task management keys
    CURRENT_TASK: Final[str] = "current_task"
    TASK_STATUS: Final[str] = "task_status"
    TASK_RESULT: Final[str] = "task_result"
    
    # Gatherer-specific keys
    GATHER_TASK: Final[str] = "task.gather"
    GATHER_RESULT: Final[str] = "task.gather.result"
    GATHER_TARGET: Final[str] = "task.gather.target"
    GATHER_PROGRESS: Final[str] = "task.gather.progress"
    
    # Crafter-specific keys
    CRAFT_TASK: Final[str] = "task.craft"
    CRAFT_RESULT: Final[str] = "task.craft.result"
    CRAFT_RECIPE: Final[str] = "task.craft.recipe"
    CRAFT_PREREQUISITES: Final[str] = "task.craft.prerequisites"
    
    # Agent communication keys
    AGENT_TRANSFER_REASON: Final[str] = "agent.transfer_reason"
    AGENT_LAST_ACTION: Final[str] = "agent.last_action"
    AGENT_ERROR: Final[str] = "agent.error"
    
    # Performance tracking keys
    COMMANDS_EXECUTED: Final[str] = "performance.commands_executed"
    SUCCESSFUL_ACTIONS: Final[str] = "performance.successful_actions"
    FAILED_ACTIONS: Final[str] = "performance.failed_actions"


# State value constants
class TaskStatus:
    """Standard task status values"""
    PENDING: Final[str] = "pending"
    IN_PROGRESS: Final[str] = "in_progress"
    COMPLETED: Final[str] = "completed"
    FAILED: Final[str] = "failed"
    CANCELLED: Final[str] = "cancelled"


class ResultStatus:
    """Standard result status values"""
    SUCCESS: Final[str] = "success"
    ERROR: Final[str] = "error"
    PARTIAL: Final[str] = "partial"
    NOT_FOUND: Final[str] = "not_found"
    INSUFFICIENT_RESOURCES: Final[str] = "insufficient_resources"


# Helper functions for state management
def create_gather_result(status: str, gathered: int = 0, item_type: str = "", error: str = "") -> dict:
    """Create a standardized gather result
    
    Args:
        status: Result status (success/error)
        gathered: Number of items gathered
        item_type: Type of item gathered
        error: Error message if failed
        
    Returns:
        Standardized gather result dict
    """
    result = {
        "status": status,
        "gathered": gathered,
        "item_type": item_type
    }
    if error:
        result["error"] = error
    return result


def create_craft_result(status: str, crafted: int = 0, item_type: str = "", 
                       missing_materials: list = None, error: str = "") -> dict:
    """Create a standardized craft result
    
    Args:
        status: Result status (success/error)
        crafted: Number of items crafted
        item_type: Type of item crafted
        missing_materials: List of missing materials
        error: Error message if failed
        
    Returns:
        Standardized craft result dict
    """
    result = {
        "status": status,
        "crafted": crafted,
        "item_type": item_type
    }
    if missing_materials:
        result["missing_materials"] = missing_materials
    if error:
        result["error"] = error
    return result