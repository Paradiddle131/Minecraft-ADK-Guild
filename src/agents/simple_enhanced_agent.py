"""
Simple Enhanced Agent for ADK Pattern Testing
Demonstrates output keys and conversation history without schema restrictions
"""

import asyncio
from typing import Any, Dict

import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from ..config import AgentConfig, get_config, setup_google_ai_credentials
from ..tools.mineflayer_tools import create_mineflayer_tools

logger = structlog.get_logger(__name__)


class SimpleEnhancedAgent:
    """Simple enhanced agent demonstrating ADK patterns without complex schemas"""

    def __init__(self, bridge_manager, config: AgentConfig = None):
        self.bridge = bridge_manager
        self.config = config or get_config()
        self.session_manager = InMemorySessionService()
        self.session = None
        self.agent = None
        self.runner = None

        # Setup Google AI credentials
        try:
            self.ai_credentials = setup_google_ai_credentials(self.config)
            logger.info("Simple enhanced agent: Google AI credentials configured")
        except ValueError as e:
            logger.warning(f"Google AI credentials not configured: {e}")
            self.ai_credentials = None

    async def initialize(self):
        """Initialize the simple enhanced agent"""
        logger.info("Initializing simple enhanced Minecraft agent")

        # Create tools
        tools = create_mineflayer_tools(self.bridge)

        # Simple agent configuration that works with ADK
        agent_config = {
            "name": "SimpleEnhancedAgent",
            "model": self.config.default_model,
            "instruction": self._get_enhanced_instruction(),
            "description": "Enhanced Minecraft bot with conversation history tracking",
            "tools": tools,
            "output_key": "agent_response"
        }

        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)

        self.agent = LlmAgent(**agent_config)

        # Create runner
        self.runner = Runner(
            agent=self.agent,
            app_name="simple_enhanced_agent",
            session_service=self.session_manager
        )

        # Create session
        self.session = await self.session_manager.create_session(
            app_name="simple_enhanced_agent",
            user_id="enhanced_player"
        )

        # Initialize conversation history and context
        self.session.state["conversation_history"] = []
        self.session.state["task_context"] = {}
        self.session.state["performance_metrics"] = {
            "commands_executed": 0,
            "successful_actions": 0,
            "failed_actions": 0
        }

        logger.info(f"Simple enhanced agent initialized with session {self.session.id}")

    def _get_enhanced_instruction(self) -> str:
        """Get enhanced instruction with conversation context"""
        return """You are an enhanced Minecraft bot with memory and planning capabilities.

CURRENT STATE:
- Position: {current_position?}
- Inventory: {current_inventory?}
- Recent conversation: {conversation_history?}
- Task context: {task_context?}
- Performance: {performance_metrics?}

Available tools:
- move_to(x, y, z): Navigate using pathfinding
- dig_block(x, y, z): Mine blocks
- place_block(x, y, z, block_type, face): Build structures  
- find_blocks(block_name, max_distance, count): Locate resources
- get_inventory(): Check current items
- send_chat(message): Communicate with players
- craft_item(recipe, count): Create items

ENHANCED CAPABILITIES:
1. Remember previous conversations and learn from them
2. Track your performance metrics and improve
3. Maintain context about ongoing tasks
4. Plan multi-step operations efficiently
5. Communicate proactively about your status

RESPONSE FORMAT:
Always structure your response with:
1. Analysis of the current situation
2. Clear plan of action
3. Expected outcome and timeline
4. Any relevant observations from conversation history

Be helpful, efficient, and maintain clear communication throughout all tasks."""

    async def process_enhanced_command(self, command: str, player: str = "Player") -> str:
        """Process command with enhanced context tracking"""
        logger.info(f"Processing enhanced command: {command}")

        try:
            # Update session state with current context
            await self._update_session_context(player)

            # Add command to conversation history
            self.session.state["conversation_history"].append({
                "type": "user_command",
                "player": player,
                "command": command,
                "timestamp": asyncio.get_event_loop().time()
            })

            # Keep only last 5 conversation entries to avoid token limits
            if len(self.session.state["conversation_history"]) > 5:
                self.session.state["conversation_history"] = \
                    self.session.state["conversation_history"][-5:]

            # Create user message
            from google.genai import types
            user_content = types.Content(
                role='user',
                parts=[types.Part(text=command)]
            )

            # Execute with ADK runner
            logger.info("Executing enhanced command with context")
            final_response = ""

            async for event in self.runner.run_async(
                user_id=player,
                session_id=self.session.id,
                new_message=user_content
            ):
                if event.is_final_response() and event.content:
                    final_response = ''.join(
                        part.text or '' for part in event.content.parts
                    )

            # Add to conversation history
            self.session.state["conversation_history"].append({
                "type": "agent_response",
                "response": final_response,
                "timestamp": asyncio.get_event_loop().time()
            })

            # Update performance metrics
            self.session.state["performance_metrics"]["commands_executed"] += 1
            if "success" in final_response.lower() or "completed" in final_response.lower():
                self.session.state["performance_metrics"]["successful_actions"] += 1

            logger.info(f"Enhanced response: {final_response}")
            return final_response or "I couldn't process that command properly."

        except Exception as e:
            logger.error(f"Error in enhanced command processing: {e}")
            self.session.state["performance_metrics"]["failed_actions"] += 1
            return f"Sorry, I encountered an error: {str(e)}"

    async def _update_session_context(self, player: str):
        """Update session state with current world context"""
        try:
            # Update current position
            current_pos = await self.bridge.get_position()
            if not isinstance(current_pos, dict) or 'error' not in current_pos:
                self.session.state["current_position"] = current_pos

            # Update inventory
            current_inventory = await self.bridge.get_inventory()
            if not isinstance(current_inventory, dict) or 'error' not in current_inventory:
                inventory_summary = {}
                for item in current_inventory:
                    name = item["name"]
                    inventory_summary[name] = inventory_summary.get(name, 0) + item["count"]
                self.session.state["current_inventory"] = inventory_summary

        except Exception as e:
            logger.warning(f"Failed to update session context: {e}")

    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of conversation history and performance"""
        return {
            "conversation_length": len(self.session.state.get("conversation_history", [])),
            "performance_metrics": self.session.state.get("performance_metrics", {}),
            "session_state_keys": list(self.session.state.keys())
        }


async def demonstrate_simple_enhanced_patterns(bridge_manager, config: AgentConfig = None):
    """Demonstrate simple enhanced ADK patterns"""
    logger.info("Starting simple enhanced ADK pattern demonstrations")

    agent = SimpleEnhancedAgent(bridge_manager, config)
    await agent.initialize()

    # Demonstrate conversation history
    logger.info("=== Conversation History Demo ===")
    response1 = await agent.process_enhanced_command(
        "I want to build a small house. Can you help me plan this?"
    )

    response2 = await agent.process_enhanced_command(
        "What materials do I need for the house?"
    )

    response3 = await agent.process_enhanced_command(
        "Where should I place the house?"
    )

    # Get conversation summary
    summary = agent.get_conversation_summary()
    logger.info(f"Conversation summary: {summary}")

    logger.info("=== Output Key Demo ===")
    # Demonstrate output key usage
    output_key_data = agent.session.state.get("agent_response")
    logger.info(f"Output key contains: {type(output_key_data)}")

    return agent
