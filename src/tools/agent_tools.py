"""
Agent-enhanced Mineflayer tools with state management
Wraps existing tools with agent-specific state updates
"""

from typing import Any, Dict, List, Optional

from google.adk.tools.tool_context import ToolContext

from ..agents.state_schema import ResultStatus, StateKeys, create_craft_result
from ..logging_config import get_logger
from ..minecraft_bot_controller import BotController
from ..minecraft_data_service import MinecraftDataService
from .mineflayer_tools import create_mineflayer_tools

logger = get_logger(__name__)


def create_gatherer_tools(bot_controller: BotController, mc_data_service: MinecraftDataService) -> List[Any]:
    """Create enhanced tools for GathererAgent with state management

    Args:
        bridge_manager: BridgeManager instance for Minecraft interaction
        mc_data_service: MinecraftDataService instance (optional)

    Returns:
        List of tools enhanced for gathering operations
    """
    # Get base tools
    base_tools = create_mineflayer_tools(bot_controller, mc_data_service)

    # Create tool name mapping for easy lookup
    tool_map = {tool.__name__: tool for tool in base_tools}

    # Enhanced tools list
    enhanced_tools = []

    # Enhance find_blocks with gathering context
    if "find_blocks" in tool_map:
        original_find_blocks = tool_map["find_blocks"]

        async def find_blocks_enhanced(
            block_name: str, max_distance: int = 32, count: int = 1, tool_context: Optional[ToolContext] = None
        ) -> Dict[str, Any]:
            """Enhanced find_blocks that updates gathering state"""
            result = await original_find_blocks(block_name, max_distance, count, tool_context)

            # Update state with found blocks
            if tool_context and result.get("status") == "success":
                positions = result.get("positions", [])
                tool_context.state[StateKeys.GATHER_TARGET] = {
                    "block_name": block_name,
                    "found_count": len(positions),
                    "locations": positions,
                }
                logger.info(f"Found {len(positions)} {block_name} blocks for gathering")

            return result

        find_blocks_enhanced.__name__ = "find_blocks"
        enhanced_tools.append(find_blocks_enhanced)

    # Enhance dig_block with gathering progress
    if "dig_block" in tool_map:
        original_dig_block = tool_map["dig_block"]

        async def dig_block_enhanced(
            x: int, y: int, z: int, tool_context: Optional[ToolContext] = None
        ) -> Dict[str, Any]:
            """Enhanced dig_block that tracks gathering progress"""
            result = await original_dig_block(x, y, z, tool_context)

            # Update gathering progress
            if tool_context and result.get("status") == "success":
                # Update progress counter
                current_progress = tool_context.state.get(StateKeys.GATHER_PROGRESS, {})
                gathered_count = current_progress.get("count", 0) + 1

                tool_context.state[StateKeys.GATHER_PROGRESS] = {
                    "count": gathered_count,
                    "last_position": {"x": x, "y": y, "z": z},
                }

                logger.info(f"Gathered item #{gathered_count} at ({x}, {y}, {z})")

            return result

        dig_block_enhanced.__name__ = "dig_block"
        enhanced_tools.append(dig_block_enhanced)

    # Enhance get_inventory for gathering verification
    if "get_inventory" in tool_map:
        original_get_inventory = tool_map["get_inventory"]

        async def get_inventory_enhanced(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
            """Enhanced get_inventory that updates minecraft inventory state"""
            result = await original_get_inventory(tool_context)

            # Update state with current inventory
            if tool_context and result.get("status") == "success":
                inventory = result.get("inventory", [])

                # Create inventory summary
                inventory_summary = {}
                for item in inventory:
                    name = item.get("name", "unknown")
                    count = item.get("count", 0)
                    inventory_summary[name] = inventory_summary.get(name, 0) + count

                tool_context.state[StateKeys.MINECRAFT_INVENTORY] = inventory_summary
                logger.info(f"Updated inventory state: {len(inventory_summary)} item types")

            return result

        get_inventory_enhanced.__name__ = "get_inventory"
        enhanced_tools.append(get_inventory_enhanced)

    if "get_position" in tool_map:
        original_get_position = tool_map["get_position"]

        async def get_position_enhanced(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
            """Enhanced get_position that updates minecraft position state"""
            result = await original_get_position(tool_context)

            # Update state with current position
            if tool_context and result.get("status") == "success":
                position = result.get("position", {})
                tool_context.state[StateKeys.MINECRAFT_POSITION] = position
                logger.info(f"Updated position state: {position}")

            return result

        get_position_enhanced.__name__ = "get_position"
        enhanced_tools.append(get_position_enhanced)

    required_tools = ["move_to", "place_block", "send_chat", "toss_item", "toss_stack"]
    missing_tools = []

    for tool_name in required_tools:
        if tool_name in tool_map:
            enhanced_tools.append(tool_map[tool_name])
        else:
            missing_tools.append(tool_name)
            logger.warning(f"Tool '{tool_name}' not found in base tools for GathererAgent")

    if missing_tools:
        logger.error(f"GathererAgent missing required tools: {missing_tools}")

    return enhanced_tools


def create_crafter_tools(bot_controller: BotController, mc_data_service: MinecraftDataService) -> List[Any]:
    """Create enhanced tools for CrafterAgent with state management

    Args:
        bridge_manager: BridgeManager instance for Minecraft interaction
        mc_data_service: MinecraftDataService instance (optional)

    Returns:
        List of tools enhanced for crafting operations
    """
    # Get base tools
    base_tools = create_mineflayer_tools(bot_controller, mc_data_service)

    # Create tool name mapping
    tool_map = {tool.__name__: tool for tool in base_tools}

    # Enhanced tools list
    enhanced_tools = []

    # Enhance craft_item with state updates
    if "craft_item" in tool_map:
        original_craft_item = tool_map["craft_item"]

        async def craft_item_enhanced(
            recipe: str, count: int = 1, tool_context: Optional[ToolContext] = None
        ) -> Dict[str, Any]:
            """Enhanced craft_item that updates crafting state"""
            # Store crafting intent
            if tool_context:
                tool_context.state[StateKeys.CRAFT_RECIPE] = {"recipe": recipe, "requested_count": count}

            result = await original_craft_item(recipe, count, tool_context)

            # Update state based on result
            if tool_context:
                if result.get("status") == "success":
                    crafted = result.get("crafted", 0)
                    tool_context.state[StateKeys.CRAFT_RESULT] = create_craft_result(
                        status=ResultStatus.SUCCESS, crafted=crafted, item_type=recipe
                    )
                    logger.info(f"Successfully crafted {crafted} {recipe}")
                else:
                    error_msg = result.get("error", "Unknown crafting error")
                    missing_materials = result.get("missing_materials", {})

                    # Convert missing_materials dict to list format expected by create_craft_result
                    missing_list = []
                    if missing_materials:
                        for item, count in missing_materials.items():
                            missing_list.append({"item": item, "count": count})

                    tool_context.state[StateKeys.CRAFT_RESULT] = create_craft_result(
                        status=ResultStatus.ERROR,
                        item_type=recipe,
                        missing_materials=missing_list if missing_list else None,
                        error=error_msg,
                    )
                    logger.error(f"Failed to craft {recipe}: {error_msg}")

            return result

        craft_item_enhanced.__name__ = "craft_item"
        enhanced_tools.append(craft_item_enhanced)

    # Enhance get_inventory for material checking
    if "get_inventory" in tool_map:
        original_get_inventory = tool_map["get_inventory"]

        async def get_inventory_enhanced(tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
            """Enhanced get_inventory for crafting material verification"""
            result = await original_get_inventory(tool_context)

            # Update state with inventory for prerequisite checking
            if tool_context and result.get("status") == "success":
                inventory = result.get("inventory", [])

                # Create material summary
                materials = {}
                for item in inventory:
                    name = item.get("name", "unknown")
                    count = item.get("count", 0)
                    materials[name] = materials.get(name, 0) + count

                tool_context.state[StateKeys.MINECRAFT_INVENTORY] = materials

                # Check if we have crafting table access
                has_crafting_table = any(item.get("name") == "crafting_table" for item in inventory)
                tool_context.state["has_crafting_table"] = has_crafting_table

                logger.info(f"Inventory check for crafting: {len(materials)} material types")

            return result

        get_inventory_enhanced.__name__ = "get_inventory"
        enhanced_tools.append(get_inventory_enhanced)

    # Add other tools without enhancement
    required_tools = ["find_blocks", "place_block", "move_to", "get_position", "send_chat"]
    missing_tools = []

    for tool_name in required_tools:
        if tool_name in tool_map:
            enhanced_tools.append(tool_map[tool_name])
        else:
            missing_tools.append(tool_name)
            logger.warning(f"Tool '{tool_name}' not found in base tools for CrafterAgent")

    if missing_tools:
        logger.error(f"CrafterAgent missing required tools: {missing_tools}")

    return enhanced_tools
