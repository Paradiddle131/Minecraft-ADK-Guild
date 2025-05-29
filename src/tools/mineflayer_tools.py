"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from ..logging_config import get_logger

logger = get_logger(__name__)

# Global bridge reference for tool functions
_bridge_manager = None

def _set_bridge_manager(bridge):
    """Set the global bridge manager for tool functions"""
    global _bridge_manager
    _bridge_manager = bridge


async def move_to(x: int, y: int, z: int, timeout: int = 30000, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Move bot to specified coordinates using pathfinding.
    
    This tool now properly waits for the bot to reach the destination before returning.
    The bot will pathfind to the target coordinates and return when movement is complete.
    Includes timeout protection to prevent infinite waits if pathfinding gets stuck.

    Args:
        x: Target X coordinate
        y: Target Y coordinate  
        z: Target Z coordinate
        timeout: Maximum time in milliseconds to wait for movement (default: 30000ms = 30s)

    Returns:
        Dictionary with movement result including actual final position
    """
    try:
        # Get current position for distance calculation
        current_pos = await _bridge_manager.get_position()
        start_distance = (
            (x - current_pos["x"]) ** 2
            + (y - current_pos["y"]) ** 2
            + (z - current_pos["z"]) ** 2
        ) ** 0.5

        logger.info(f"Starting movement to ({x}, {y}, {z}), distance: {start_distance:.1f}")
        
        # Store movement start in state
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['temp:movement_in_progress'] = {
                'target': {'x': x, 'y': y, 'z': z},
                'start_position': current_pos,
                'start_time': __import__('time').time(),
                'start_distance': start_distance
            }

        # Execute movement - this now waits for completion with timeout
        try:
            movement_result = await _bridge_manager.move_to(x, y, z, timeout)
        except TimeoutError as e:
            logger.warning(f"Movement command timed out: {e}")
            # Try to get current position anyway
            try:
                actual_pos = await _bridge_manager.get_position()
                # Check if we're close enough to target
                distance_to_target = (
                    (actual_pos["x"] - x) ** 2
                    + (actual_pos["y"] - y) ** 2
                    + (actual_pos["z"] - z) ** 2
                ) ** 0.5
                
                if distance_to_target < 2.0:  # Within 2 blocks is close enough
                    logger.info(f"Movement likely succeeded despite timeout - distance to target: {distance_to_target:.1f}")
                    movement_result = {
                        'actual_position': actual_pos,
                        'status': 'completed_with_timeout',
                        'message': 'Reached target despite timeout'
                    }
                else:
                    raise  # Re-raise the timeout error
            except Exception:
                raise e  # Re-raise original timeout
        
        # The bridge.move_to already handles the pathfinder.goto command and waits for completion
        # The result should contain the actual position after movement
        
        # Handle the movement result - it should be a dict from the JS bot
        if isinstance(movement_result, dict):
            actual_pos = movement_result.get('actual_position')
            if not actual_pos:
                # If no actual_position, try to get current position
                actual_pos = await _bridge_manager.get_position()
        else:
            # Fallback - get current position
            actual_pos = await _bridge_manager.get_position()
            
        final_distance = (
            (actual_pos["x"] - current_pos["x"]) ** 2
            + (actual_pos["y"] - current_pos["y"]) ** 2
            + (actual_pos["z"] - current_pos["z"]) ** 2
        ) ** 0.5

        result = {
            "status": "success",
            "target_position": {"x": x, "y": y, "z": z},
            "actual_position": actual_pos,
            "distance_traveled": final_distance
        }
        
        # Add additional info from movement_result if available
        if isinstance(movement_result, dict):
            result["movement_status"] = movement_result.get('status', 'completed')
            result["message"] = movement_result.get('message', 'Movement completed')
            if 'duration_ms' in movement_result:
                result["duration_ms"] = movement_result['duration_ms']
        
        # Update position and clear movement state
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_position'] = {
                'x': actual_pos['x'],
                'y': actual_pos['y'], 
                'z': actual_pos['z'],
                'timestamp': __import__('time').time()
            }
            # Clear temp movement state by setting to None
            tool_context.state['temp:movement_in_progress'] = None
            tool_context.state['temp:last_movement'] = {
                'target': {'x': x, 'y': y, 'z': z},
                'actual': actual_pos,
                'duration_ms': movement_result.get('duration_ms', 0) if isinstance(movement_result, dict) else 0,
                'status': 'completed',
                'timestamp': __import__('time').time()
            }
            logger.info(f"Movement completed to ({actual_pos['x']}, {actual_pos['y']}, {actual_pos['z']})")
        
        return result

    except Exception as e:
        logger.error(f"Movement failed: {e}")
        
        # Attempt recovery for certain failure types
        if "timeout" in str(e).lower() or "no path" in str(e).lower() or "stuck" in str(e).lower():
            logger.info("Attempting movement recovery with adjusted goals")
            
            # Try nearby alternative goals
            for offset in [(0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]:
                alt_x = x + offset[0]
                alt_y = y + offset[1]
                alt_z = z + offset[2]
                
                try:
                    logger.info(f"Trying alternative goal: ({alt_x}, {alt_y}, {alt_z})")
                    recovery_result = await _bridge_manager.move_to(alt_x, alt_y, alt_z, timeout=15000)
                    
                    if 'error' not in recovery_result and 'actual_position' in recovery_result:
                        actual_pos = recovery_result['actual_position']
                        logger.info(f"Recovery successful, reached ({actual_pos['x']}, {actual_pos['y']}, {actual_pos['z']})")
                        
                        # Update state with recovery result
                        if tool_context and hasattr(tool_context, 'state'):
                            tool_context.state['minecraft_position'] = {
                                'x': actual_pos['x'],
                                'y': actual_pos['y'], 
                                'z': actual_pos['z'],
                                'timestamp': __import__('time').time()
                            }
                            tool_context.state['temp:movement_in_progress'] = None
                            tool_context.state['temp:last_movement'] = {
                                'target': {'x': x, 'y': y, 'z': z},
                                'actual': actual_pos,
                                'status': 'completed_with_recovery',
                                'recovery_offset': offset,
                                'timestamp': __import__('time').time()
                            }
                        
                        return {
                            "status": "success",
                            "target_position": {"x": x, "y": y, "z": z},
                            "actual_position": actual_pos,
                            "movement_status": "completed_with_recovery",
                            "message": f"Reached nearby position after recovery (offset: {offset})"
                        }
                        
                except Exception as recovery_error:
                    logger.debug(f"Recovery attempt failed: {recovery_error}")
                    continue
        
        # If recovery failed or wasn't attempted, return error
        error_result = {"status": "error", "error": str(e)}
        
        # Save movement error and clear temp state
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_last_movement_error'] = {
                'error': str(e),
                'target': {'x': x, 'y': y, 'z': z},
                'timestamp': __import__('time').time()
            }
            # Clear temp movement state on error by setting to None
            tool_context.state['temp:movement_in_progress'] = None
        
        return error_result


async def dig_block(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Dig a block at specified coordinates.

    Args:
        x: Block X coordinate
        y: Block Y coordinate
        z: Block Z coordinate

    Returns:
        Dictionary with dig result
    """
    try:
        # Check what block is there first
        block_info = await _bridge_manager.execute_command("world.getBlock", x=x, y=y, z=z)
        block_name = block_info.get("name", "unknown")

        if block_name == "air":
            return {"status": "error", "error": "No block to dig at this position"}

        logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

        # Dig the block
        await _bridge_manager.dig_block(x, y, z)

        return {"status": "success", "block": block_name, "position": {"x": x, "y": y, "z": z}}

    except Exception as e:
        logger.error(f"Dig failed: {e}")
        return {"status": "error", "error": str(e)}


async def place_block(
    x: int,
    y: int,
    z: int,
    block_type: str,
    face: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Place a block at specified coordinates.

    Args:
        x: Reference block X coordinate
        y: Reference block Y coordinate
        z: Reference block Z coordinate
        block_type: Type of block to place
        face: Which face of the reference block to place against

    Returns:
        Dictionary with place result
    """
    try:
        # Check inventory for the block
        inventory = await _bridge_manager.get_inventory()
        has_block = any(item["name"] == block_type for item in inventory)

        if not has_block:
            return {"status": "error", "error": f"No {block_type} in inventory"}

        # Equip the block
        await _bridge_manager.execute_command(
            "inventory.equip", item=block_type, destination="hand"
        )

        # Place the block
        await _bridge_manager.place_block(x, y, z, face)

        logger.info(f"Placed {block_type} at ({x}, {y}, {z})")

        return {
            "status": "success",
            "block": block_type,
            "position": {"x": x, "y": y, "z": z},
            "face": face,
        }

    except Exception as e:
        logger.error(f"Place failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_position() -> Dict[str, Any]:
    """Get the bot's current position in the world.
    
    Returns:
        Dictionary with bot's coordinates
    """
    try:
        position = await _bridge_manager.get_position()
        
        if position:
            return {
                'status': 'success',
                'position': position,
                'x': position.get('x'),
                'y': position.get('y'),
                'z': position.get('z')
            }
        else:
            return {
                'status': 'error',
                'error': 'Unable to get position'
            }
            
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


async def get_movement_status(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Check if the bot is currently moving and get movement details.
    
    Returns:
        Dictionary with movement status and details
    """
    try:
        # Check bot movement status via bridge
        movement_info = await _bridge_manager.execute_command("pathfinder.isMoving")
        
        result = {
            'status': 'success',
            'is_moving': movement_info.get('isMoving', False),
            'has_goal': movement_info.get('goal') is not None
        }
        
        # Add goal information if available
        if movement_info.get('goal'):
            goal = movement_info['goal']
            result['goal'] = goal
            
        # Add session state information if available
        if tool_context and hasattr(tool_context, 'state'):
            movement_progress = tool_context.state.get('temp:movement_in_progress')
            if movement_progress:
                result['session_movement'] = movement_progress
                result['movement_duration'] = __import__('time').time() - movement_progress['start_time']
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting movement status: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


async def find_blocks(
    block_name: str,
    max_distance: int,
    count: int,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Find blocks of a specific type near the bot.

    Args:
        block_name: Name of block to find (e.g. "oak_log", "stone")
        max_distance: Maximum search distance
        count: Maximum number of blocks to return

    Returns:
        Dictionary with found blocks
    """
    try:
        logger.info(f"Searching for {block_name} within {max_distance} blocks")

        blocks = await _bridge_manager.execute_command(
            "world.findBlocks", name=block_name, maxDistance=max_distance, count=count
        )

        # Convert JSPyBridge Proxy object to Python list
        if hasattr(blocks, '__len__'):
            # Already a Python object with len()
            block_list = list(blocks)
        else:
            # Proxy object - convert to list by iterating
            block_list = []
            try:
                # Try to iterate over the proxy object
                for block in blocks:
                    block_list.append(block)
            except TypeError:
                # If it's not iterable, it might be a single object or empty
                if blocks:
                    block_list = [blocks]
                else:
                    block_list = []

        return {
            "status": "success",
            "block_type": block_name,
            "count": len(block_list),
            "positions": block_list,
        }

    except Exception as e:
        logger.error(f"Block search failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_nearby_players(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get information about nearby players.

    Returns:
        Dictionary with player information
    """
    try:
        # This would come from event stream in full implementation
        # For now, return empty list as placeholder
        players = []

        return {"status": "success", "count": len(players), "players": players}

    except Exception as e:
        logger.error(f"Player query failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_inventory(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get current inventory contents.

    Returns:
        Dictionary with inventory items
    """
    try:
        items = await _bridge_manager.get_inventory()

        # Organize by item type
        inventory_summary = {}
        for item in items:
            name = item["name"]
            if name not in inventory_summary:
                inventory_summary[name] = 0
            inventory_summary[name] += item["count"]

        result = {
            "status": "success",
            "items": items,
            "summary": inventory_summary,
            "total_items": sum(item["count"] for item in items),
        }
        
        # Save structured inventory data to session state if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_inventory'] = {
                'items': items,
                'summary': inventory_summary,
                'total_items': result['total_items'],
                'timestamp': __import__('time').time()
            }
            logger.info("Saved inventory data to session state")
        
        return result

    except Exception as e:
        logger.error(f"Inventory query failed: {e}")
        error_result = {"status": "error", "error": str(e)}
        
        # Save error state if tool_context is provided
        if tool_context and hasattr(tool_context, 'state'):
            tool_context.state['minecraft_inventory'] = {
                'error': str(e),
                'timestamp': __import__('time').time()
            }
        
        return error_result


async def craft_item(recipe: str, count: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Craft an item using available materials.

    Args:
        recipe: Name of item to craft
        count: Number to craft

    Returns:
        Dictionary with craft result
    """
    try:
        logger.info(f"Attempting to craft {count} {recipe}")

        # Execute craft command through bridge
        result = await _bridge_manager.execute_command("craft", recipe=recipe, count=count)
        
        # Check if result is valid
        if result is None:
            logger.error("Craft command returned None")
            return {
                "status": "error",
                "error": "Craft command failed - no response from bot"
            }
        
        logger.debug(f"Craft result type: {type(result)}, hasattr success: {hasattr(result, 'success') if result else 'N/A'}")
        
        # Handle JSPyBridge Proxy objects
        if hasattr(result, 'success'):
            # Access proxy properties directly
            success = result.success
            if success:
                crafted_count = result.crafted if hasattr(result, 'crafted') else 0
                logger.info(f"Successfully crafted {crafted_count} {recipe}")
                return {
                    "status": "success",
                    "crafted": recipe,
                    "count": crafted_count
                }
            else:
                # Handle crafting failure
                error_msg = result.error if hasattr(result, 'error') else f"Failed to craft {recipe}"
                missing_materials = result.missing_materials if hasattr(result, 'missing_materials') else {}
                
                # Convert JSPyBridge proxy to dict if needed
                if missing_materials and not isinstance(missing_materials, dict):
                    # Try to convert proxy object to dict
                    try:
                        # JSPyBridge proxy objects need special handling
                        missing_dict = {}
                        
                        # Get the string representation to find what properties exist
                        proxy_str = str(missing_materials)
                        logger.debug(f"Missing materials proxy: {proxy_str}")
                        
                        # Extract properties from the proxy representation
                        # The format is typically: <Proxy(dict) {'item': count, ...}>
                        import re
                        match = re.search(r'\{([^}]+)\}', proxy_str)
                        if match:
                            content = match.group(1)
                            # Parse key-value pairs
                            for pair in content.split(','):
                                if ':' in pair:
                                    key, value = pair.split(':', 1)
                                    key = key.strip().strip("'").strip('"')
                                    value = value.strip()
                                    try:
                                        missing_dict[key] = int(value)
                                    except ValueError:
                                        missing_dict[key] = value
                        
                        # If parsing failed, try direct attribute access for common items
                        if not missing_dict:
                            common_materials = ['planks', 'oak_planks', 'birch_planks', 'spruce_planks', 
                                              'stick', 'sticks', 'oak_log', 'birch_log', 'cobblestone', 
                                              'iron_ingot', 'gold_ingot', 'diamond']
                            for material in common_materials:
                                if hasattr(missing_materials, material):
                                    missing_dict[material] = getattr(missing_materials, material)
                        
                        # If we found something, use it
                        if missing_dict:
                            missing_materials = missing_dict
                        else:
                            missing_materials = {"unknown": "Check inventory for required materials"}
                            
                    except Exception as e:
                        logger.debug(f"Failed to convert missing_materials proxy: {e}")
                        missing_materials = {"unknown": "Unable to determine missing materials"}
                
                logger.error(f"Crafting failed: {error_msg}")
                
                response = {
                    "status": "error",
                    "error": error_msg
                }
                
                # Include missing materials if provided by the bot
                if missing_materials:
                    response["missing_materials"] = missing_materials
                    
                return response
        
        # Fallback for dict-like results
        elif isinstance(result, dict) and "success" in result:
            if result.get("success", False):
                crafted_count = result.get("crafted", 0)
                logger.info(f"Successfully crafted {crafted_count} {recipe}")
                return {
                    "status": "success",
                    "crafted": recipe,
                    "count": crafted_count
                }
            else:
                # Handle dict failure  
                error_msg = result.get("error", f"Failed to craft {recipe}")
                missing_materials = result.get("missing_materials", {})
                
                logger.error(f"Crafting failed: {error_msg}")
                
                response = {
                    "status": "error",
                    "error": error_msg
                }
                
                # Include missing materials if provided by the bot
                if missing_materials:
                    response["missing_materials"] = missing_materials
                    
                return response
        else:
            # Unexpected result format
            logger.error(f"Unexpected craft result format: {type(result)}")
            return {
                "status": "error",
                "error": f"Unexpected result format from craft command: {type(result)}"
            }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Crafting exception: {error_msg}", exc_info=True)
        
        # Try to extract meaningful error information
        return {
            "status": "error",
            "error": f"Crafting failed: {error_msg}"
        }


async def send_chat(message: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Send a chat message.

    Args:
        message: Message to send

    Returns:
        Dictionary with send result
    """
    try:
        await _bridge_manager.chat(message)

        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {"status": "error", "error": str(e)}


def create_mineflayer_tools(bridge_manager) -> List:
    """Create all Mineflayer tools for ADK agents.

    Args:
        bridge_manager: BridgeManager instance

    Returns:
        List of tool functions (ADK will automatically wrap them)
    """
    # Set the global bridge manager
    _set_bridge_manager(bridge_manager)

    # Return list of tool functions - ADK automatically creates FunctionTool objects
    return [
        move_to,
        dig_block,
        place_block,
        get_position,
        get_movement_status,
        find_blocks,
        get_nearby_players,
        get_inventory,
        craft_item,
        send_chat,
    ]
