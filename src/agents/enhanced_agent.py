"""
Enhanced Agent with Advanced ADK Patterns
Demonstrates structured output, conversation history, and output key usage
"""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pydantic import BaseModel, Field

from ..config import AgentConfig, get_config, setup_google_ai_credentials
from ..tools.mineflayer_tools import create_mineflayer_tools

logger = structlog.get_logger(__name__)


class EnhancedMinecraftAgent:
    """Enhanced Minecraft agent demonstrating advanced ADK patterns"""
    
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
            logger.info("Enhanced agent: Google AI credentials configured")
        except ValueError as e:
            logger.warning(f"Google AI credentials not configured: {e}")
            self.ai_credentials = None
    
    async def initialize(self):
        """Initialize the enhanced agent with advanced features"""
        logger.info("Initializing enhanced Minecraft agent")
        
        # Create tools
        tools = create_mineflayer_tools(self.bridge)
        
        # Agent configuration with structured output (no tools when using output_schema)
        agent_config = {
            "name": "EnhancedMinecraftAgent",
            "model": self.config.default_model,
            "instruction": self._get_enhanced_instruction(),
            "description": "Advanced Minecraft bot with structured output and conversation history",
            "output_schema": self.StructuredResponse,
            "output_key": "structured_response"
        }
        
        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)
        
        self.agent = LlmAgent(**agent_config)
        
        # Create runner
        self.runner = Runner(
            agent=self.agent,
            app_name="enhanced_minecraft_agent",
            session_service=self.session_manager
        )
        
        # Create session
        self.session = await self.session_manager.create_session(
            app_name="enhanced_minecraft_agent",
            user_id="enhanced_player"
        )
        
        # Initialize conversation history
        self.session.state["conversation_history"] = []
        self.session.state["task_context"] = {}
        self.session.state["performance_metrics"] = {
            "commands_executed": 0,
            "successful_actions": 0,
            "failed_actions": 0
        }
        
        logger.info(f"Enhanced agent initialized with session {self.session.id}")
    
    def _get_enhanced_instruction(self) -> str:
        """Get enhanced instruction with conversation context"""
        return """You are an advanced Minecraft bot with sophisticated planning capabilities.

CURRENT STATE:
- Position: {current_position?}
- Inventory: {current_inventory?} 
- Recent conversation: {conversation_history?}
- Current task context: {task_context?}
- Performance: {performance_metrics?}

RESPONSE FORMAT:
You must respond with a JSON structure containing:
{
  "analysis": "Your analysis of the request and current situation",
  "plan": ["step 1", "step 2", "step 3"],
  "actions": [{"tool": "tool_name", "params": {}, "reason": "why"}],
  "communication": "Message to send to the player",
  "confidence": 0.85,
  "estimated_time": "2 minutes"
}

CAPABILITIES:
- move_to(x, y, z): Navigate using pathfinding
- dig_block(x, y, z): Mine blocks
- place_block(x, y, z, block_type, face): Build structures
- find_blocks(block_name, max_distance, count): Locate resources
- get_inventory(): Check current items
- send_chat(message): Communicate with players
- craft_item(recipe, count): Create items

GUIDELINES:
1. Always analyze the situation before acting
2. Break complex tasks into clear steps
3. Provide confidence estimates for your actions
4. Communicate your plans clearly to players
5. Learn from past conversation history
6. Track and improve your performance metrics

Be proactive, efficient, and maintain clear communication throughout all tasks.

Note: You cannot use tools directly. Instead, plan the actions and specify which tools should be used in your actions array."""

class ActionItem(BaseModel):
        """Single action item"""
        tool: str = Field(description="Tool name to use")
        params: Dict[str, Any] = Field(description="Parameters for the tool")
        reason: str = Field(description="Reason for this action")
    
    class StructuredResponse(BaseModel):
        """Structured response schema for enhanced agent"""
        analysis: str = Field(description="Analysis of the current situation and request")
        plan: List[str] = Field(description="Step-by-step plan to complete the task")
        actions: List[ActionItem] = Field(description="Specific actions to take with reasoning")
        communication: str = Field(description="Message to communicate to the player")
        confidence: float = Field(ge=0, le=1, description="Confidence level for task completion")
        estimated_time: str = Field(description="Estimated time to complete the task")
    
    async def process_enhanced_command(self, command: str, player: str = "Player") -> Dict[str, Any]:
        """Process command with enhanced features and structured output"""
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
            
            # Keep only last 10 conversation entries
            if len(self.session.state["conversation_history"]) > 10:
                self.session.state["conversation_history"] = \
                    self.session.state["conversation_history"][-10:]
            
            # Create user message
            user_content = types.Content(
                role='user',
                parts=[types.Part(text=command)]
            )
            
            # Execute with ADK runner
            logger.info("Executing enhanced command with structured output")
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
            
            # Parse structured response
            try:
                import json
                structured_response = json.loads(final_response)
                
                # Add to conversation history
                self.session.state["conversation_history"].append({
                    "type": "agent_response",
                    "response": structured_response,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                # Update performance metrics
                self.session.state["performance_metrics"]["commands_executed"] += 1
                
                logger.info(f"Structured response: {structured_response}")
                return structured_response
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse structured response: {final_response}")
                # Fallback to plain text response
                return {
                    "analysis": "Response parsing failed",
                    "plan": ["Review command and try again"],
                    "actions": [],
                    "communication": final_response or "I couldn't process that command properly.",
                    "confidence": 0.1,
                    "estimated_time": "unknown"
                }
                
        except Exception as e:
            logger.error(f"Error in enhanced command processing: {e}")
            self.session.state["performance_metrics"]["failed_actions"] += 1
            return {
                "analysis": f"Error occurred: {str(e)}",
                "plan": ["Address the error and retry"],
                "actions": [],
                "communication": f"Sorry, I encountered an error: {str(e)}",
                "confidence": 0.0,
                "estimated_time": "unknown"
            }
    
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
    
    async def demonstrate_output_keys(self) -> Dict[str, Any]:
        """Demonstrate output key usage for agent communication"""
        logger.info("Demonstrating output key patterns")
        
        # Example of how to use output keys for agent-to-agent communication
        demo_commands = [
            "Analyze my current inventory and suggest what to build",
            "Plan a resource gathering mission for building a house",
            "Evaluate the best location within 50 blocks for construction"
        ]
        
        results = []
        for command in demo_commands:
            logger.info(f"Demo command: {command}")
            result = await self.process_enhanced_command(command)
            results.append({
                "command": command,
                "structured_output": result
            })
        
        return {
            "demo_type": "output_key_usage",
            "results": results,
            "session_state_keys": list(self.session.state.keys())
        }


async def demonstrate_enhanced_patterns(bridge_manager, config: AgentConfig = None):
    """Demonstrate enhanced ADK patterns"""
    logger.info("Starting enhanced ADK pattern demonstrations")
    
    agent = EnhancedMinecraftAgent(bridge_manager, config)
    await agent.initialize()
    
    # Demonstrate structured output
    logger.info("=== Structured Output Demo ===")
    response = await agent.process_enhanced_command(
        "I want to build a small house. Help me plan this project."
    )
    logger.info(f"Structured response received: {response.get('analysis', 'N/A')}")
    
    # Demonstrate conversation history
    logger.info("=== Conversation History Demo ===") 
    await agent.process_enhanced_command("What materials do I need?")
    await agent.process_enhanced_command("Where should I place it?")
    
    history = agent.session.state.get("conversation_history", [])
    logger.info(f"Conversation history contains {len(history)} entries")
    
    # Demonstrate output keys
    logger.info("=== Output Key Demo ===")
    output_demo = await agent.demonstrate_output_keys()
    logger.info(f"Output key demonstration completed: {len(output_demo['results'])} examples")
    
    return agent