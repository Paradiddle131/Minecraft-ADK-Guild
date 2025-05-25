#!/usr/bin/env python3
"""
Demo script to test inventory query flow with mocked components
This can run without a Minecraft server to demonstrate the complete flow
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import structlog
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.simple_agent import SimpleMinecraftAgent
from src.config import get_config
from src.tools.mineflayer_tools import create_mineflayer_tools

# Load environment variables
load_dotenv()

# Configure colorful logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def demonstrate_inventory_flow():
    """Demonstrate the complete flow of inventory query"""
    logger.info("=" * 70)
    logger.info("INVENTORY QUERY FLOW DEMONSTRATION")
    logger.info("=" * 70)
    
    # Get config
    config = get_config()
    has_api_key = bool(config.google_ai_api_key and config.google_ai_api_key != "your_gemini_api_key_here")
    
    if not has_api_key:
        logger.warning("No valid Google AI API key found - will use mock ADK responses")
        logger.info("To use real ADK, set MINECRAFT_AGENT_GOOGLE_AI_API_KEY in .env")
    else:
        logger.info(f"Using Google AI with model: {config.default_model}")
    
    # Create mock components
    logger.info("\n1. CREATING MOCK COMPONENTS")
    logger.info("-" * 40)
    
    # Mock bridge
    mock_bridge = MagicMock()
    
    # Mock inventory items
    inventory_items = [
        {"name": "diamond", "count": 5, "slot": 0},
        {"name": "iron_ingot", "count": 64, "slot": 1},
        {"name": "oak_log", "count": 32, "slot": 2},
        {"name": "cobblestone", "count": 128, "slot": 3},
        {"name": "torch", "count": 16, "slot": 4}
    ]
    
    async def mock_get_inventory():
        logger.info("[BRIDGE] get_inventory() called")
        logger.info(f"[BRIDGE] Returning {len(inventory_items)} items")
        return inventory_items
    
    async def mock_get_position():
        position = {"x": 100, "y": 64, "z": 200}
        logger.info("[BRIDGE] get_position() called")
        logger.info(f"[BRIDGE] Returning position: {position}")
        return position
    
    mock_bridge.get_inventory = mock_get_inventory
    mock_bridge.get_position = mock_get_position
    
    # Mock event processor
    mock_event_processor = MagicMock()
    mock_event_processor.get_world_state.return_value = {
        "nearby_players": ["DemoPlayer"],
        "current_position": {"x": 100, "y": 64, "z": 200}
    }
    
    # Create tools
    tools = create_mineflayer_tools(mock_bridge)
    logger.info(f"✓ Created {len(tools)} Mineflayer tools")
    
    # Create mock runner and session
    logger.info("\n2. SIMULATING ADK EXECUTION")
    logger.info("-" * 40)
    
    # Mock session
    session_manager = InMemorySessionService()
    session = await session_manager.create_session(
        app_name="demo_agent",
        user_id="demo_player"
    )
    
    # Mock runner
    mock_runner = AsyncMock(spec=Runner)
    
    async def mock_run_async(user_id, session_id, new_message):
        logger.info("[ADK] Processing message:", message=new_message.parts[0].text)
        
        # Simulate ADK processing
        await asyncio.sleep(0.1)
        
        # Check if inventory query
        if "inventory" in new_message.parts[0].text.lower():
            logger.info("[ADK] Detected inventory query - selecting get_inventory tool")
            
            # Simulate tool execution
            logger.info("[ADK] Executing get_inventory tool...")
            inventory_result = await tools[5]()  # get_inventory is the 6th tool
            
            logger.info(f"[ADK] Tool returned: {inventory_result['status']}")
            
            # Format response
            response_text = "I'll check your inventory for you.\n\n"
            if inventory_result['status'] == 'success':
                response_text += "Your inventory contains:\n"
                for item, count in inventory_result['summary'].items():
                    response_text += f"- {count} {item}\n"
                response_text += f"\nTotal: {inventory_result['total_items']} items across {len(inventory_result['items'])} slots"
            else:
                response_text += f"Error checking inventory: {inventory_result.get('error', 'Unknown error')}"
        else:
            response_text = "I can help you with various tasks in Minecraft!"
        
        logger.info("[ADK] Generated response")
        
        # Create mock response event
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content = types.Content(
            role='assistant',
            parts=[types.Part(text=response_text)]
        )
        
        yield mock_event
    
    mock_runner.run_async = mock_run_async
    
    # Execute query
    logger.info("\n3. EXECUTING INVENTORY QUERY")
    logger.info("-" * 40)
    
    query = "what's in your inventory"
    logger.info(f"User query: '{query}'")
    
    # Create user message
    user_content = types.Content(
        role='user',
        parts=[types.Part(text=query)]
    )
    
    # Process with mock ADK
    logger.info("\n4. PROCESSING FLOW")
    logger.info("-" * 40)
    
    final_response = ""
    async for event in mock_runner.run_async(
        user_id="demo_player",
        session_id=session.id,
        new_message=user_content
    ):
        if event.is_final_response() and event.content:
            final_response = ''.join(
                part.text or '' for part in event.content.parts
            )
    
    logger.info("\n5. AGENT RESPONSE")
    logger.info("-" * 40)
    logger.info(final_response)
    
    # Show execution trace
    logger.info("\n6. EXECUTION TRACE SUMMARY")
    logger.info("-" * 40)
    logger.info("1. User sends query: 'what's in your inventory'")
    logger.info("2. ADK processes natural language and identifies intent")
    logger.info("3. ADK selects get_inventory tool based on query")
    logger.info("4. Tool calls bridge.get_inventory()")
    logger.info("5. Bridge would send command to bot.js via WebSocket")
    logger.info("6. Mineflayer executes bot.inventory.items()")
    logger.info("7. Results flow back through the system")
    logger.info("8. ADK formats the response for the user")
    
    logger.info("\n7. MINEFLAYER EXECUTION (WHAT WOULD HAPPEN)")
    logger.info("-" * 40)
    logger.info("In bot.js, the following would execute:")
    logger.info("```javascript")
    logger.info("case 'getInventory':")
    logger.info("  const items = bot.inventory.items();")
    logger.info("  const itemData = items.map(item => ({")
    logger.info("    name: item.name,")
    logger.info("    count: item.count,")
    logger.info("    slot: item.slot")
    logger.info("  }));")
    logger.info("  return { success: true, data: itemData };")
    logger.info("```")
    
    logger.info("\n" + "=" * 70)
    logger.info("DEMONSTRATION COMPLETE")
    logger.info("=" * 70)


async def main():
    """Main entry point"""
    logger.info("Inventory Query Flow Demonstration")
    logger.info("This demonstrates the complete execution flow")
    logger.info("No Minecraft server required for this demo\n")
    
    await demonstrate_inventory_flow()
    
    logger.info("\nTo run with a real Minecraft server:")
    logger.info("1. Start Minecraft server")
    logger.info("2. Run: node src/minecraft/bot.js")
    logger.info("3. Run: python run_inventory_e2e_test.py")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nDemo interrupted by user")
        sys.exit(0)