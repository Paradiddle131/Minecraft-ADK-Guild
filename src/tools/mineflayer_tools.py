"""
Mineflayer Tools for Google ADK - Wraps Minecraft bot commands as ADK tools
"""
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from ..agents.state_schema import StateKeys
from ..logging_config import get_logger
from ..minecraft_bot_controller import BotController
from ..minecraft_data_service import MinecraftDataService

logger = get_logger(__name__)

# Global references for tool functions
_bot_controller: Optional[BotController] = None
_mc_data_service: Optional[MinecraftDataService] = None


def _set_bot_controller(controller: BotController):
    """Set the global bot controller for tool functions"""
    global _bot_controller
    _bot_controller = controller


def _set_minecraft_data_service(mc_data: MinecraftDataService):
    """Set the global minecraft data service for tool functions"""
    global _mc_data_service
    _mc_data_service = mc_data


async def move_to(
    x: int, y: int, z: int, timeout: Optional[int] = None, tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Move bot to specified coordinates using pathfinding.

    Enhanced version that uses BotController and provides additional context.

    Args:
        x: Target X coordinate
        y: Target Y coordinate
        z: Target Z coordinate
        timeout: Maximum time in milliseconds to wait for movement (default from env var)

    Returns:
        Dictionary with movement result including actual final position
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    # Use config for default timeout
    if timeout is None:
        # Get timeout from config if available
        try:
            from ..config import get_config

            config = get_config()
            timeout = config.pathfinder_timeout_ms
        except Exception:
            # Fallback to 30 seconds if config fails
            timeout = 30000

    try:
        # Get current position for distance calculation
        current_pos = await _bot_controller.get_position()
        start_distance = (
            (x - current_pos["x"]) ** 2 + (y - current_pos["y"]) ** 2 + (z - current_pos["z"]) ** 2
        ) ** 0.5

        logger.info(f"Starting movement to ({x}, {y}, {z}), distance: {start_distance:.1f}")

        # Store movement start in state
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state[StateKeys.MOVEMENT_IN_PROGRESS] = {
                "target": {"x": x, "y": y, "z": z},
                "start_position": current_pos,
                "start_time": __import__("time").time(),
                "start_distance": start_distance,
            }

        # Use BotController for movement, passing the timeout
        # Progress updates are now handled entirely in JavaScript
        result = await _bot_controller.move_to(x, y, z, timeout=timeout)

        # Update state based on result
        if result.get("status") == "success":
            # Get actual position after movement
            actual_pos = await _bot_controller.get_position()

            # Update position in state
            if tool_context and hasattr(tool_context, "state"):
                tool_context.state[StateKeys.MINECRAFT_POSITION] = {
                    "x": actual_pos["x"],
                    "y": actual_pos["y"],
                    "z": actual_pos["z"],
                    "timestamp": __import__("time").time(),
                }
                tool_context.state[StateKeys.MOVEMENT_IN_PROGRESS] = None

            return {
                "status": "success",
                "target_position": {"x": x, "y": y, "z": z},
                "actual_position": actual_pos,
                "distance_traveled": start_distance,
            }
        else:
            # Movement failed
            # Check if it's a timeout error
            error_msg = result.get("error", "")
            if "timeout" in error_msg.lower():
                # It's a timeout - get current position for reporting
                try:
                    actual_pos = await _bot_controller.get_position()
                except Exception:
                    actual_pos = {"x": 0, "y": 0, "z": 0}

                return {
                    "status": "error",
                    "error": f"Movement command timed out after {timeout}ms",
                    "target_position": {"x": x, "y": y, "z": z},
                    "actual_position": actual_pos,
                    "timeout_ms": timeout,
                    "suggestion": "Either call the movement command again or increase MINECRAFT_AGENT_PATHFINDER_TIMEOUT_MS",
                }
            else:
                # Other failure
                return result

    except Exception as e:
        logger.error(f"Movement failed: {e}")
        return {"status": "error", "error": str(e)}


async def dig_block(x: int, y: int, z: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Dig a block at specified coordinates.

    Enhanced version that provides block information from MinecraftDataService.

    Args:
        x: Block X coordinate
        y: Block Y coordinate
        z: Block Z coordinate

    Returns:
        Dictionary with dig result and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Get block information first
        block_info = await _bot_controller.get_block_at(x, y, z)

        # Handle proxy objects from JSPyBridge
        if block_info is None:
            block_name = "unknown"
        elif isinstance(block_info, dict):
            block_name = block_info.get("name", "unknown")
        else:
            # Try to access as attribute for proxy objects
            try:
                block_name = getattr(block_info, "name", "unknown")
            except Exception:
                block_name = "unknown"

        if block_name == "air":
            return {"status": "error", "error": "No block to dig at this position"}

        # Get additional block data from MinecraftDataService
        block_data = None
        if _mc_data_service and block_name != "unknown":
            block_data = _mc_data_service.get_block_by_name(block_name)

        logger.info(f"Digging {block_name} at ({x}, {y}, {z})")

        # Start digging
        result = await _bot_controller.dig_block(x, y, z)

        if result.get("status") == "success":
            response = {"status": "success", "block": block_name, "position": {"x": x, "y": y, "z": z}}

            # Add enriched block data if available
            if block_data:
                response["block_data"] = {
                    "hardness": block_data.get("hardness", 0),
                    "material": block_data.get("material", "unknown"),
                    "drops": block_data.get("drops", []),
                }

            return response
        else:
            return result

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

    Enhanced version that validates blocks using MinecraftDataService and uses BotController.

    Args:
        x: Reference block X coordinate
        y: Reference block Y coordinate
        z: Reference block Z coordinate
        block_type: Type of block to place
        face: Which face of the reference block to place against

    Returns:
        Dictionary with place result and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Normalize and validate block type using MinecraftDataService
        normalized_block = block_type
        block_data = None
        if _mc_data_service:
            block_data = _mc_data_service.get_block_by_name(block_type)
            if not block_data:
                # Try to find similar block names
                all_blocks = _mc_data_service.get_all_blocks()
                similar_blocks = [b for b in all_blocks if block_type.lower() in b.get("name", "").lower()]
                if similar_blocks:
                    return {
                        "status": "error",
                        "error": f"Block '{block_type}' not found. Similar blocks: {[b['name'] for b in similar_blocks[:3]]}",
                    }
                else:
                    return {"status": "error", "error": f"Unknown block type: {block_type}"}
            else:
                normalized_block = block_data.get("name", block_type)

        # Check inventory for the block
        inventory = await _bot_controller.get_inventory_items()
        has_block = any(item["name"] == normalized_block for item in inventory)

        if not has_block:
            # Check for alternative block names in inventory
            inventory_names = [item["name"] for item in inventory]
            return {
                "status": "error",
                "error": f"No {normalized_block} in inventory. Available blocks: {[name for name in inventory_names if 'block' in name.lower() or any(material in name for material in ['wood', 'stone', 'dirt', 'sand'])]}",
                "inventory_blocks": [name for name in inventory_names if "block" in name.lower()],
            }

        # Convert face string to face vector for BotController
        face_vectors = {
            "top": [0, 1, 0],
            "bottom": [0, -1, 0],
            "north": [0, 0, -1],
            "south": [0, 0, 1],
            "east": [1, 0, 0],
            "west": [-1, 0, 0],
        }
        face_vector = face_vectors.get(face.lower(), [0, 1, 0])  # Default to top

        # Equip the block
        equip_result = await _bot_controller.equip_item(normalized_block, "hand")
        if equip_result.get("status") != "success":
            return {
                "status": "error",
                "error": f"Failed to equip {normalized_block}: {equip_result.get('error', 'Unknown error')}",
            }

        # Place the block using BotController
        place_result = await _bot_controller.place_block([x, y, z], face_vector)

        if place_result.get("status") == "success":
            logger.info(f"Placed {normalized_block} at ({x}, {y}, {z}) on {face} face")

            response = {
                "status": "success",
                "block": normalized_block,
                "position": {"x": x, "y": y, "z": z},
                "face": face,
                "face_vector": face_vector,
            }

            # Add enriched block data if available
            if block_data:
                response["block_data"] = {
                    "hardness": block_data.get("hardness", 0),
                    "material": block_data.get("material", "unknown"),
                    "stack_size": block_data.get("stackSize", 64),
                    "transparent": block_data.get("transparent", False),
                }

            return response
        else:
            return place_result

    except Exception as e:
        logger.error(f"Place failed: {e}")
        return {"status": "error", "error": str(e)}


async def get_position(tool_context=None) -> Dict[str, Any]:
    """Get the bot's current position in the world.

    Enhanced version that uses BotController.

    Args:
        tool_context: Optional ADK tool context for state management

    Returns:
        Dictionary with bot's coordinates
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        position = await _bot_controller.get_position()

        if position:
            return {
                "status": "success",
                "position": position,
                "x": position.get("x"),
                "y": position.get("y"),
                "z": position.get("z"),
            }
        else:
            return {"status": "error", "error": "Unable to get position"}

    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return {"status": "error", "error": str(e)}


async def get_movement_status(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Check if the bot is currently moving and get movement details.

    Enhanced version that works with BotController and session state.

    Returns:
        Dictionary with movement status and details
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Get current position for movement detection
        current_pos = await _bot_controller.get_position()

        result = {"status": "success", "current_position": current_pos, "is_moving": False, "has_goal": False}

        # Check session state for movement tracking
        if tool_context and hasattr(tool_context, "state"):
            movement_progress = tool_context.state.get(StateKeys.MOVEMENT_IN_PROGRESS)
            if movement_progress:
                # Calculate if we're still moving based on session state
                current_time = __import__("time").time()
                movement_duration = current_time - movement_progress["start_time"]
                start_position = movement_progress["start_position"]
                target = movement_progress["target"]

                # Calculate distance from start and to target
                distance_from_start = (
                    (current_pos["x"] - start_position["x"]) ** 2
                    + (current_pos["y"] - start_position["y"]) ** 2
                    + (current_pos["z"] - start_position["z"]) ** 2
                ) ** 0.5

                distance_to_target = (
                    (current_pos["x"] - target["x"]) ** 2
                    + (current_pos["y"] - target["y"]) ** 2
                    + (current_pos["z"] - target["z"]) ** 2
                ) ** 0.5

                # Consider moving if we haven't reached target and it's been recent
                result["is_moving"] = distance_to_target > 1.0 and movement_duration < 60  # 60 second timeout
                result["has_goal"] = True
                result["session_movement"] = {
                    "target": target,
                    "distance_to_target": distance_to_target,
                    "distance_from_start": distance_from_start,
                    "movement_duration": movement_duration,
                    "start_distance": movement_progress.get("start_distance", 0),
                }

                # Calculate movement progress
                if movement_progress.get("start_distance", 0) > 0:
                    progress_percent = min(100, (distance_from_start / movement_progress["start_distance"]) * 100)
                    result["session_movement"]["progress_percent"] = progress_percent

        # Try to get pathfinder status if available (fallback to bridge)
        try:
            bridge_manager = _bot_controller.bridge_manager_instance
            pathfinder_info = await bridge_manager.execute_command("pathfinder.isMoving")
            if pathfinder_info:
                result["pathfinder_status"] = {
                    "is_moving": pathfinder_info.get("isMoving", False),
                    "has_goal": pathfinder_info.get("goal") is not None,
                }
                # Override our detection with pathfinder if available
                result["is_moving"] = pathfinder_info.get("isMoving", result["is_moving"])
                result["has_goal"] = pathfinder_info.get("goal") is not None or result["has_goal"]

                if pathfinder_info.get("goal"):
                    result["pathfinder_goal"] = pathfinder_info["goal"]
        except Exception as pathfinder_error:
            logger.debug(f"Could not get pathfinder status: {pathfinder_error}")
            # Not a critical error, continue with session-based detection

        return result

    except Exception as e:
        logger.error(f"Error getting movement status: {e}")
        return {"status": "error", "error": str(e)}


async def find_blocks(
    block_name: str,
    max_distance: int,
    count: int,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Find blocks of a specific type near the bot.

    Enhanced version that validates blocks using MinecraftDataService and uses BotController.

    Args:
        block_name: Name of block to find (e.g. "oak_log", "stone")
        max_distance: Maximum search distance
        count: Maximum number of blocks to return

    Returns:
        Dictionary with found blocks and block information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Handle patterns and wildcards using MinecraftDataService
        block_ids = []
        matching_blocks = []

        if _mc_data_service:
            # Check if it's a pattern (contains wildcards or generic terms)
            if "*" in block_name or block_name.lower() in ["log", "logs", "plank", "planks"]:
                # Get blocks matching the pattern
                matching_blocks = _mc_data_service.get_blocks_by_pattern(block_name)
                if matching_blocks:
                    block_ids = [block.get("id") for block in matching_blocks if "id" in block]
                    logger.info(
                        f"Pattern '{block_name}' matched {len(matching_blocks)} block types: {[b['name'] for b in matching_blocks[:5]]}"
                    )
                else:
                    logger.warning(f"No blocks found matching pattern '{block_name}'")
                    return {
                        "status": "success",
                        "block_type": block_name,
                        "original_query": block_name,
                        "count": 0,
                        "positions": [],
                        "search_radius": max_distance,
                    }
            else:
                # Single block lookup
                block_data = _mc_data_service.get_block_by_name(block_name)
                if block_data:
                    block_ids = [block_data.get("id")]
                    matching_blocks = [block_data]
                    logger.info(
                        f"Searching for {block_data.get('name')} (ID: {block_data.get('id')}) within {max_distance} blocks"
                    )
                else:
                    logger.warning(f"Unknown block type '{block_name}'")
                    return {"status": "error", "error": f"Unknown block type: {block_name}"}

        if not block_ids:
            return {"status": "error", "error": f"Could not resolve block name/pattern: {block_name}"}

        # Use BotController to find blocks by names (JavaScript will resolve to IDs)
        block_names = [block.get("name") for block in matching_blocks if block.get("name")]
        logger.info(f"Sending block names to JavaScript: {block_names}")
        block_list = await _bot_controller.find_blocks(block_names, max_distance, count)

        # Convert JSPyBridge Proxy object to Python list if needed
        if not isinstance(block_list, list):
            if hasattr(block_list, "__len__"):
                # Already a Python object with len()
                block_list = list(block_list)
            else:
                # Proxy object - convert to list by iterating
                converted_list = []
                try:
                    # Try to iterate over the proxy object
                    for block in block_list:
                        converted_list.append(block)
                    block_list = converted_list
                except TypeError:
                    # If it's not iterable, it might be a single object or empty
                    if block_list:
                        block_list = [block_list]
                    else:
                        block_list = []

        response = {
            "status": "success",
            "block_type": block_name if len(matching_blocks) != 1 else matching_blocks[0].get("name", block_name),
            "original_query": block_name,
            "count": len(block_list),
            "positions": block_list,
            "search_radius": max_distance,
        }

        # Add information about matched block types
        if matching_blocks:
            response["matched_blocks"] = [
                {
                    "name": block.get("name"),
                    "id": block.get("id"),
                    "hardness": block.get("hardness", 0),
                    "material": block.get("material", "unknown"),
                }
                for block in matching_blocks[:10]  # Limit to first 10 to avoid huge responses
            ]

        logger.info(f"Found {len(block_list)} blocks matching '{block_name}' within {max_distance} blocks")
        return response

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

    Enhanced version that provides rich item information from MinecraftDataService.

    Returns:
        Dictionary with inventory items and enriched data
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        items = await _bot_controller.get_inventory_items()

        # Organize by item type with enhanced data
        inventory_summary = {}
        enriched_items = []
        item_categories = {
            "tools": [],
            "weapons": [],
            "armor": [],
            "blocks": [],
            "food": [],
            "materials": [],
            "other": [],
        }
        craftable_items = []

        for item in items:
            name = item["name"]
            count = item["count"]

            # Basic summary
            if name not in inventory_summary:
                inventory_summary[name] = 0
            inventory_summary[name] += count

            # Enrich with MinecraftDataService data
            enriched_item = item.copy()
            if _mc_data_service:
                item_data = _mc_data_service.get_item_by_name(name)
                if item_data:
                    enriched_item["item_data"] = {
                        "stack_size": item_data.get("stackSize", 64),
                        "max_durability": item_data.get("maxDurability", None),
                        "creative_tab": item_data.get("creative_tab", "misc"),
                        "material": item_data.get("material", "unknown"),
                    }

                    # Categorize items
                    if "sword" in name or "bow" in name or "crossbow" in name or "trident" in name:
                        item_categories["weapons"].append({"name": name, "count": count})
                    elif any(tool in name for tool in ["pickaxe", "axe", "shovel", "hoe", "shears"]):
                        item_categories["tools"].append({"name": name, "count": count})
                    elif any(armor in name for armor in ["helmet", "chestplate", "leggings", "boots"]):
                        item_categories["armor"].append({"name": name, "count": count})
                    elif any(
                        food in name for food in ["bread", "apple", "meat", "fish", "stew", "cake"]
                    ) or "food" in item_data.get("category", ""):
                        item_categories["food"].append({"name": name, "count": count})
                    elif "block" in item_data.get("type", "") or name.endswith("_block"):
                        item_categories["blocks"].append({"name": name, "count": count})
                    elif any(
                        material in name
                        for material in ["ingot", "gem", "dust", "nugget", "stick", "string", "leather"]
                    ):
                        item_categories["materials"].append({"name": name, "count": count})
                    else:
                        item_categories["other"].append({"name": name, "count": count})

                # Check what can be crafted with this item
                recipes = _mc_data_service.get_recipes_for_item_name(name)
                if recipes:
                    for recipe in recipes[:3]:  # Limit to first 3 recipes
                        result_item = recipe.get("result", {}).get("name", "unknown")
                        if result_item not in [c["result"] for c in craftable_items]:
                            craftable_items.append(
                                {
                                    "ingredient": name,
                                    "result": result_item,
                                    "result_count": recipe.get("result", {}).get("count", 1),
                                }
                            )

            enriched_items.append(enriched_item)

        # Calculate inventory statistics
        total_items = sum(item["count"] for item in items)
        unique_items = len(inventory_summary)

        # Identify valuable items
        valuable_items = []
        if _mc_data_service:
            for name, count in inventory_summary.items():
                item_data = _mc_data_service.get_item_by_name(name)
                if item_data:
                    # Consider items valuable if they're rare materials or tools
                    if any(valuable in name for valuable in ["diamond", "netherite", "gold", "emerald", "enchanted"]):
                        valuable_items.append({"name": name, "count": count, "type": "precious_material"})
                    elif item_data.get("maxDurability", 0) > 100:  # Durable tools/weapons
                        valuable_items.append({"name": name, "count": count, "type": "durable_tool"})

        result = {
            "status": "success",
            "items": enriched_items,
            "summary": inventory_summary,
            "statistics": {
                "total_items": total_items,
                "unique_items": unique_items,
                "inventory_slots_used": len(items),
            },
            "categories": {k: v for k, v in item_categories.items() if v},  # Only include non-empty categories
            "valuable_items": valuable_items,
            "craftable_with_inventory": craftable_items[:10],  # Limit to 10 most relevant
        }

        # Save structured inventory data to session state if tool_context is provided
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state[StateKeys.MINECRAFT_INVENTORY] = {
                "items": enriched_items,
                "summary": inventory_summary,
                "statistics": result["statistics"],
                "categories": result["categories"],
                "timestamp": __import__("time").time(),
            }
            logger.info("Saved enriched inventory data to session state")

        return result

    except Exception as e:
        logger.error(f"Inventory query failed: {e}")
        error_result = {"status": "error", "error": str(e)}

        # Save error state if tool_context is provided
        if tool_context and hasattr(tool_context, "state"):
            tool_context.state[StateKeys.MINECRAFT_INVENTORY] = {
                "error": str(e),
                "timestamp": __import__("time").time(),
            }

        return error_result


async def craft_item(recipe: str, count: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Craft an item using available materials with fully generic logic.

    Uses generic fuzzy matching and recipe selection without any hardcoded item handling.

    Args:
        recipe: Name of item to craft
        count: Number to craft

    Returns:
        Dictionary with craft result and recipe information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        logger.info(f"Attempting to craft {count} {recipe}")

        # Get current inventory
        inventory = await _bot_controller.get_inventory_items()
        inventory_summary = {}
        for item in inventory:
            name = item["name"]
            inventory_summary[name] = inventory_summary.get(name, 0) + item["count"]

        # Generic item resolution
        normalized_recipe = recipe
        if _mc_data_service:
            # First try generic item request handler
            generic_result = _mc_data_service.handle_generic_item_request(recipe, inventory_summary)
            if generic_result:
                normalized_recipe = generic_result
                logger.info(f"Resolved generic '{recipe}' to specific '{normalized_recipe}'")
            else:
                # Use generic normalization and fuzzy matching
                normalized_recipe = _mc_data_service.normalize_item_name(recipe)
                if normalized_recipe == recipe:
                    # If normalization didn't change it, try fuzzy matching
                    fuzzy_match = _mc_data_service.fuzzy_match_item_name(recipe)
                    if fuzzy_match:
                        normalized_recipe = fuzzy_match
                        logger.info(f"Fuzzy matched '{recipe}' to '{normalized_recipe}'")

        # Generic recipe selection and validation
        recipe_data = None
        selected_recipe = None
        if _mc_data_service:
            # Use generic recipe selection algorithm
            selected_recipe = _mc_data_service.select_best_recipe(normalized_recipe, inventory_summary)

            if not selected_recipe:
                # No craftable recipe, get recipes for information
                recipes = _mc_data_service.get_recipes_for_item(normalized_recipe)
                if recipes:
                    recipe_data = recipes[0]
                else:
                    # Generic recipe suggestion using fuzzy matching
                    all_recipes = _mc_data_service.get_all_recipes()
                    suggestions = []

                    # Score all recipes by similarity to request
                    for r in all_recipes:
                        result_name = r.get("result", {}).get("name", "")
                        # Generic similarity check
                        similarity_score = 0

                        # Substring matching
                        if recipe.lower() in result_name.lower():
                            similarity_score += 0.5
                        if result_name.lower() in recipe.lower():
                            similarity_score += 0.3

                        # Word overlap
                        recipe_words = set(recipe.lower().split())
                        result_words = set(result_name.lower().replace("_", " ").split())
                        common_words = recipe_words & result_words
                        if common_words:
                            similarity_score += len(common_words) / max(len(recipe_words), len(result_words))

                        if similarity_score > 0.3:
                            suggestions.append((result_name, similarity_score))

                    if suggestions:
                        # Sort by score and take top suggestions
                        suggestions.sort(key=lambda x: x[1], reverse=True)
                        similar_recipes = [s[0] for s in suggestions[:10]]
                        return {
                            "status": "error",
                            "error": f"Recipe '{recipe}' not found. Similar recipes: {similar_recipes}",
                        }
                    else:
                        logger.warning(f"No recipe found for '{normalized_recipe}', attempting to craft anyway")
            else:
                recipe_data = selected_recipe
                logger.info(f"Selected best recipe for {normalized_recipe}")

        # Generic material validation
        missing_materials = {}
        if recipe_data and _mc_data_service:
            # Use generic recipe material extraction
            materials_needed = _mc_data_service.get_recipe_materials(recipe_data)
            result_count = recipe_data.get("result", {}).get("count", 1)
            batches_needed = (count + result_count - 1) // result_count

            # Generic material availability check
            for material, qty_per_batch in materials_needed.items():
                total_needed = qty_per_batch * batches_needed
                available = inventory_summary.get(material, 0)
                if available < total_needed:
                    missing_materials[material] = total_needed - available

            if missing_materials:
                response = {
                    "status": "error",
                    "error": f"Insufficient materials to craft {count} {normalized_recipe}",
                    "missing_materials": missing_materials,
                    "current_inventory": inventory_summary,
                    "recipe_info": {
                        "materials_per_craft": materials_needed,
                        "result_count": result_count,
                        "batches_needed": batches_needed,
                        "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                    },
                }
                return response

        # Execute craft command

        bridge_manager = _bot_controller.bridge_manager_instance
        result = await bridge_manager.execute_command("craft", recipe=normalized_recipe, count=count)

        # Generic result handling
        if result is None:
            logger.error("Craft command returned None")
            return {
                "status": "error",
                "error": "Craft command failed - no response from bot",
                "recipe_attempted": normalized_recipe,
            }

        # Generic proxy/dict result extraction
        success = False
        crafted_count = 0
        error_msg = None

        # Try to extract result generically
        if hasattr(result, "__dict__"):
            # Object with attributes
            for success_key in ["success", "successful", "ok", "done"]:
                if hasattr(result, success_key):
                    success = getattr(result, success_key)
                    break
            for count_key in ["crafted", "count", "amount", "quantity"]:
                if hasattr(result, count_key):
                    crafted_count = getattr(result, count_key)
                    break
            for error_key in ["error", "message", "msg", "reason"]:
                if hasattr(result, error_key):
                    error_msg = getattr(result, error_key)
                    break
        elif isinstance(result, dict):
            # Dictionary result
            for success_key in ["success", "successful", "ok", "done"]:
                if success_key in result:
                    success = result[success_key]
                    break
            for count_key in ["crafted", "count", "amount", "quantity"]:
                if count_key in result:
                    crafted_count = result[count_key]
                    break
            for error_key in ["error", "message", "msg", "reason"]:
                if error_key in result:
                    error_msg = result[error_key]
                    break

        if success:
            logger.info(f"Successfully crafted {crafted_count} {normalized_recipe}")
            response = {
                "status": "success",
                "crafted": normalized_recipe,
                "count": crafted_count,
                "original_request": recipe,
            }

            # Add generic recipe data if available
            if recipe_data and _mc_data_service:
                materials = _mc_data_service.get_recipe_materials(recipe_data)
                response["recipe_data"] = {
                    "materials": materials,
                    "result_count": recipe_data.get("result", {}).get("count", 1),
                    "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                }

            return response
        else:
            # Crafting failed
            if not error_msg:
                error_msg = f"Failed to craft {normalized_recipe}"

            response = {
                "status": "error",
                "error": error_msg,
                "recipe_attempted": normalized_recipe,
                "current_inventory": inventory_summary,
            }

            # Add generic recipe info for debugging
            if recipe_data and _mc_data_service:
                materials = _mc_data_service.get_recipe_materials(recipe_data)
                response["recipe_info"] = {
                    "required_materials": materials,
                    "result_count": recipe_data.get("result", {}).get("count", 1),
                    "requires_crafting_table": _mc_data_service.needs_crafting_table(normalized_recipe),
                }
                # Generic material shortage calculation
                missing = {}
                for mat, qty in materials.items():
                    if inventory_summary.get(mat, 0) < qty:
                        missing[mat] = qty - inventory_summary.get(mat, 0)
                if missing:
                    response["missing_materials"] = missing

            return response

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Crafting exception: {error_msg}", exc_info=True)

        response = {"status": "error", "error": f"Crafting failed: {error_msg}", "recipe_attempted": recipe}

        # Generic recipe suggestions on error
        if _mc_data_service:
            try:
                all_recipes = _mc_data_service.get_all_recipes()
                suggestions = []

                # Generic word-based suggestion algorithm
                recipe_words = set(recipe.lower().replace("_", " ").split())
                for r in all_recipes:
                    result_name = r.get("result", {}).get("name", "")
                    result_words = set(result_name.lower().replace("_", " ").split())

                    # Calculate word overlap score
                    common_words = recipe_words & result_words
                    if common_words:
                        score = len(common_words) / max(len(recipe_words), len(result_words))
                        if score > 0.2:
                            suggestions.append((result_name, score))

                if suggestions:
                    suggestions.sort(key=lambda x: x[1], reverse=True)
                    response["suggested_recipes"] = [s[0] for s in suggestions[:10]]
            except Exception as suggest_error:
                logger.debug(f"Could not get recipe suggestions: {suggest_error}")

        return response


async def send_chat(message: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Send a chat message.

    Enhanced version that uses BotController.

    Args:
        message: Message to send

    Returns:
        Dictionary with send result
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        result = await _bot_controller.chat(message)

        if result.get("status") == "success":
            return {"status": "success", "message": message}
        else:
            return result

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {"status": "error", "error": str(e)}


async def toss_item(
    item_type: str, count: int = 1, metadata: Optional[int] = None, tool_context: Optional[ToolContext] = None
) -> Dict[str, Any]:
    """Toss specific amount of an item from inventory.

    Enhanced version that validates items using MinecraftDataService and uses BotController.

    Args:
        item_type: Name of item to toss (e.g. "dirt", "oak_log")
        count: Number of items to toss (default 1)
        metadata: Optional metadata for the item (default None matches any)

    Returns:
        Dictionary with toss result and item information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Normalize and validate item name using MinecraftDataService
        normalized_item = item_type
        item_data = None
        if _mc_data_service:
            item_data = _mc_data_service.get_item_by_name(item_type)
            if not item_data:
                # Try fuzzy matching
                fuzzy_match = _mc_data_service.fuzzy_match_item_name(item_type)
                if fuzzy_match:
                    normalized_item = fuzzy_match
                    logger.info(f"Fuzzy matched '{item_type}' to '{normalized_item}'")
                    item_data = _mc_data_service.get_item_by_name(normalized_item)
                else:
                    # Try to find similar item names
                    all_items = _mc_data_service.get_all_items()
                    similar_items = [i for i in all_items if item_type.lower() in i.get("name", "").lower()]
                    if similar_items:
                        return {
                            "status": "error",
                            "error": f"Item '{item_type}' not found. Similar items: {[i['name'] for i in similar_items[:3]]}",
                        }
                    else:
                        logger.warning(f"Unknown item type '{item_type}', attempting to toss anyway")
            else:
                normalized_item = item_data.get("name", item_type)

        # Check current inventory first
        inventory = await _bot_controller.get_inventory_items()
        has_item = any(item["name"] == normalized_item for item in inventory)

        if not has_item:
            inventory_names = [item["name"] for item in inventory]
            return {
                "status": "error",
                "error": f"No {normalized_item} in inventory. Available items: {inventory_names[:10]}",
                "available_items": inventory_names,
            }

        # Check if we have enough of the item
        available_count = sum(item["count"] for item in inventory if item["name"] == normalized_item)
        if available_count < count:
            return {
                "status": "error",
                "error": f"Only have {available_count} {normalized_item}, cannot toss {count}",
                "available_count": available_count,
            }

        logger.info(f"Tossing {count} {normalized_item}")

        # Use BotController to toss the items
        result = await _bot_controller.toss_item(normalized_item, count, metadata)

        if result.get("status") == "success":
            response = {
                "status": "success",
                "item": normalized_item,
                "original_request": item_type,
                "count": result.get("tossed", count),
            }

            # Add enriched item data if available
            if item_data:
                response["item_data"] = {
                    "stack_size": item_data.get("stackSize", 64),
                    "material": item_data.get("material", "unknown"),
                    "max_durability": item_data.get("maxDurability", None),
                }

            logger.info(f"Successfully tossed {result.get('tossed', count)} {normalized_item}")
            return response
        else:
            return result

    except Exception as e:
        logger.error(f"Toss item failed: {e}")
        return {"status": "error", "error": str(e)}


async def toss_stack(slot_index: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Toss entire stack from specific inventory slot.

    Enhanced version that provides slot and item information.

    Args:
        slot_index: Inventory slot index (0-based, typically 0-35 for main inventory)

    Returns:
        Dictionary with toss result and slot information
    """
    if not _bot_controller:
        return {"status": "error", "error": "BotController not initialized"}

    try:
        # Validate slot index range
        if not (0 <= slot_index <= 45):  # 0-35 main inventory, 36-44 hotbar, 45 offhand
            return {
                "status": "error",
                "error": f"Invalid slot index {slot_index}. Valid range is 0-45",
                "valid_range": "0-35 (main inventory), 36-44 (hotbar), 45 (offhand)",
            }

        # Get current inventory to check what's in the slot
        inventory = await _bot_controller.get_inventory_items()

        # For enhanced error reporting, try to identify what's in nearby slots if target is empty
        slot_info = None
        if inventory:
            # Check if we can identify the item in this slot
            for item in inventory:
                if item.get("slot") == slot_index:
                    slot_info = item
                    break

        if not slot_info:
            # Provide helpful information about nearby slots
            nearby_items = [
                item
                for item in inventory
                if item.get("slot", -1) in range(max(0, slot_index - 2), min(46, slot_index + 3))
            ]
            return {
                "status": "error",
                "error": f"No item in slot {slot_index}",
                "slot": slot_index,
                "nearby_slots": [
                    {"slot": item.get("slot"), "item": item.get("name"), "count": item.get("count")}
                    for item in nearby_items
                ],
            }

        item_name = slot_info.get("name", "unknown")
        item_count = slot_info.get("count", 0)

        logger.info(f"Tossing stack of {item_count} {item_name} from slot {slot_index}")

        # Use BotController to toss the stack
        result = await _bot_controller.toss_stack(slot_index)

        if result.get("status") == "success":
            response = {
                "status": "success",
                "slot": slot_index,
                "item": result.get("item", item_name),
                "count": result.get("tossed", item_count),
            }

            # Add enriched item data if available
            if _mc_data_service and item_name != "unknown":
                item_data = _mc_data_service.get_item_by_name(item_name)
                if item_data:
                    response["item_data"] = {
                        "stack_size": item_data.get("stackSize", 64),
                        "material": item_data.get("material", "unknown"),
                        "max_durability": item_data.get("maxDurability", None),
                    }

            logger.info(
                f"Successfully tossed stack of {result.get('tossed', item_count)} {item_name} from slot {slot_index}"
            )
            return response
        else:
            return result

    except Exception as e:
        logger.error(f"Toss stack failed: {e}")
        return {"status": "error", "error": str(e)}


def create_mineflayer_tools(bot_controller: BotController, mc_data_service: MinecraftDataService) -> List:
    """Create enhanced Mineflayer tools with BotController and MinecraftDataService integration.

    Args:
        bot_controller: BotController instance
        mc_data_service: MinecraftDataService instance

    Returns:
        List of tool functions (ADK will automatically wrap them)
    """
    # Set the global references
    _set_bot_controller(bot_controller)
    _set_minecraft_data_service(mc_data_service)

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
        toss_item,
        toss_stack,
    ]
