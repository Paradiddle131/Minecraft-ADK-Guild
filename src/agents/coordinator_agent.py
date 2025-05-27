"""
CoordinatorAgent - Main interface for user communication and task delegation
Implements ADK multi-agent patterns for orchestrating GathererAgent and CrafterAgent
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager
from .coordinator_agent.prompt import COORDINATOR_INSTRUCTIONS

logger = structlog.get_logger(__name__)


class CoordinatorAgent(BaseMinecraftAgent):
    """Main coordinator agent that handles user interaction and delegates to sub-agents"""
    
    def __init__(
        self,
        name: str = "CoordinatorAgent",
        model: str = "gemini-2.0-flash",
        sub_agents: Optional[List[Any]] = None,
        session_service: Optional[InMemorySessionService] = None,
        bridge_manager: Optional[BridgeManager] = None,
        ai_credentials: Optional[Dict[str, Any]] = None,
        config=None
    ):
        """Initialize the coordinator agent
        
        Args:
            name: Agent name for identification
            model: LLM model to use
            sub_agents: List of sub-agents (GathererAgent, CrafterAgent)
            session_service: ADK session service for state management
            bridge_manager: Shared BridgeManager instance
            ai_credentials: Google AI credentials
            config: Agent configuration
        """
        # Initialize base class
        super().__init__(name, bridge_manager, config)
        
        self.model = model
        self.sub_agents = sub_agents or []
        self.session_service = session_service
        if ai_credentials:
            self.ai_credentials = ai_credentials
        self.agent = None
        
        logger.info(f"Initializing {self.name} with {len(self.sub_agents)} sub-agents")
        
    def _create_instruction(self) -> str:
        """Create the coordinator's instruction prompt
        
        Returns:
            Instruction string for the LLM
        """
        return COORDINATOR_INSTRUCTIONS
    
    def create_agent(self) -> LlmAgent:
        """Create the ADK LlmAgent instance
        
        Returns:
            Configured LlmAgent for coordination
        """
        # Get sub-agent names for the instruction
        sub_agent_names = [agent.name for agent in self.sub_agents]
        instruction = self._create_instruction().format(
            sub_agent_names=", ".join(sub_agent_names)
        )
        
        # Configure the coordinator agent with transfer settings
        agent_config = {
            "name": self.name,
            "model": self.model,
            "instruction": instruction,
            "description": "Main coordinator for Minecraft multi-agent system",
            "sub_agents": self.sub_agents,
            "output_key": "coordinator_response"
        }
           
        self.agent = LlmAgent(**agent_config)
        logger.info(f"{self.name} created with sub-agents: {sub_agent_names}")
        
        return self.agent
    
    def _analyze_user_request(self, request: str) -> dict:
        """Analyze user request to determine task type and delegation
        
        Args:
            request: User's request string
            
        Returns:
            Dictionary with task analysis
        """
        request_lower = request.lower()
        
        # Define task patterns
        gather_keywords = [
            "gather", "collect", "mine", "find", "get", "obtain",
            "harvest", "dig", "chop", "break", "acquire"
        ]
        
        craft_keywords = [
            "craft", "make", "create", "build", "construct",
            "forge", "assemble", "produce", "manufacture"
        ]
        
        inventory_keywords = [
            "inventory", "have", "items", "what do i",
            "check", "show", "list", "count"
        ]
        
        # Analyze task type
        task_type = None
        confidence = 0
        
        # Check for gathering task
        gather_score = sum(1 for keyword in gather_keywords if keyword in request_lower)
        if gather_score > 0:
            task_type = "gather"
            confidence = min(gather_score / len(gather_keywords), 1.0)
            
        # Check for crafting task
        craft_score = sum(1 for keyword in craft_keywords if keyword in request_lower)
        if craft_score > gather_score:
            task_type = "craft"
            confidence = min(craft_score / len(craft_keywords), 1.0)
            
        # Check for inventory query
        inventory_score = sum(1 for keyword in inventory_keywords if keyword in request_lower)
        if inventory_score > max(gather_score, craft_score):
            task_type = "inventory"
            confidence = min(inventory_score / len(inventory_keywords), 1.0)
            
        # Extract target item/resource
        target = self._extract_target(request, task_type)
        
        # Determine complexity
        complexity = self._assess_complexity(request, task_type)
        
        return {
            "task_type": task_type,
            "confidence": confidence,
            "target": target,
            "complexity": complexity,
            "original_request": request,
            "requires_delegation": task_type in ["gather", "craft"],
            "suggested_agent": self._get_suggested_agent(task_type)
        }
        
    def _extract_target(self, request: str, task_type: str) -> str:
        """Extract target item or resource from request
        
        Args:
            request: User request
            task_type: Identified task type
            
        Returns:
            Target item/resource name
        """
        import re
        
        # Remove common action words
        action_words = [
            "please", "can you", "i need", "i want", "help me",
            "gather", "collect", "craft", "make", "create",
            "get", "find", "build", "some", "a few"
        ]
        
        cleaned = request.lower()
        for word in action_words:
            cleaned = cleaned.replace(word, "")
            
        # Extract quantity and item
        quantity_pattern = r'(\d+)\s+(\w+(?:\s+\w+)*)'
        match = re.search(quantity_pattern, cleaned)
        
        if match:
            return match.group(2).strip()
        else:
            # Get remaining words as target
            words = cleaned.split()
            return ' '.join(words).strip()
            
    def _assess_complexity(self, request: str, task_type: str) -> str:
        """Assess task complexity
        
        Args:
            request: User request
            task_type: Task type
            
        Returns:
            Complexity level (simple/moderate/complex)
        """
        # Complex items that require multiple steps
        complex_items = [
            "pickaxe", "axe", "sword", "shovel", "hoe",
            "furnace", "chest", "door", "fence", "stairs"
        ]
        
        # Check for quantity
        import re
        quantity_match = re.search(r'(\d+)', request)
        quantity = int(quantity_match.group(1)) if quantity_match else 1
        
        # Check for complex items
        request_lower = request.lower()
        has_complex_item = any(item in request_lower for item in complex_items)
        
        # Determine complexity
        if task_type == "inventory":
            return "simple"
        elif has_complex_item or quantity > 10:
            return "complex"
        elif quantity > 5:
            return "moderate"
        else:
            return "simple"
            
    def _get_suggested_agent(self, task_type: str) -> str:
        """Get suggested agent for task type
        
        Args:
            task_type: Identified task type
            
        Returns:
            Agent name or None
        """
        agent_mapping = {
            "gather": "GathererAgent",
            "craft": "CrafterAgent",
            "inventory": None  # Handle directly
        }
        
        return agent_mapping.get(task_type)
    
    def _synthesize_response(self, session_state: dict, task_analysis: dict) -> str:
        """Synthesize user-friendly response from sub-agent results
        
        Args:
            session_state: Current session state with results
            task_analysis: Original task analysis
            
        Returns:
            User-friendly response string
        """
        from .state_schema import StateKeys
        
        task_type = task_analysis.get("task_type")
        target = task_analysis.get("target", "items")
        
        # Check for gathering results
        if task_type == "gather":
            gather_result = session_state.get(StateKeys.GATHER_RESULT, {})
            
            if gather_result.get("status") == "success":
                gathered = gather_result.get("gathered", 0)
                item_type = gather_result.get("item_type", target)
                
                # Get current position for context
                position = session_state.get(StateKeys.MINECRAFT_POSITION, {})
                pos_str = f" at position ({position.get('x', 0):.0f}, {position.get('y', 0):.0f}, {position.get('z', 0):.0f})" if position else ""
                
                return (f"✅ Successfully gathered {gathered} {item_type}{pos_str}! "
                       f"The items have been added to your inventory.")
                       
            elif gather_result.get("status") == "error":
                error = gather_result.get("error", "Unknown error")
                return (f"❌ Failed to gather {target}: {error}. "
                       f"Try moving to a different area or checking if the resource exists nearby.")
                       
            elif gather_result.get("status") == "not_found":
                return (f"🔍 Could not find any {target} within search range. "
                       f"You may need to explore further or try a different biome.")
                       
        # Check for crafting results
        elif task_type == "craft":
            craft_result = session_state.get(StateKeys.CRAFT_RESULT, {})
            
            if craft_result.get("status") == "success":
                crafted = craft_result.get("crafted", 0)
                item_type = craft_result.get("item_type", target)
                
                return (f"🔨 Successfully crafted {crafted} {item_type}! "
                       f"The crafted items are now in your inventory.")
                       
            elif craft_result.get("status") == "insufficient_resources":
                missing = craft_result.get("missing_materials", {})
                missing_str = ", ".join([f"{count} {item}" for item, count in missing.items()])
                
                return (f"📦 Cannot craft {target} - missing materials: {missing_str}. "
                       f"You'll need to gather these resources first.")
                       
            elif craft_result.get("status") == "error":
                error = craft_result.get("error", "Unknown error")
                return f"❌ Failed to craft {target}: {error}"
                
        # Check for inventory query
        elif task_type == "inventory":
            inventory = session_state.get(StateKeys.MINECRAFT_INVENTORY, {})
            
            if not inventory:
                return "🎒 Your inventory is empty."
            else:
                # Format inventory nicely
                items = []
                for item, count in sorted(inventory.items()):
                    items.append(f"• {item}: {count}")
                    
                inventory_list = "\n".join(items[:10])  # Show first 10 items
                total_types = len(inventory)
                
                response = f"🎒 Current inventory ({total_types} item types):\n{inventory_list}"
                
                if total_types > 10:
                    response += f"\n... and {total_types - 10} more item types"
                    
                return response
                
        # Default response if no results found
        return self._create_status_response(session_state, task_analysis)
        
    def _create_status_response(self, session_state: dict, task_analysis: dict) -> str:
        """Create a status response when no specific results are available
        
        Args:
            session_state: Current session state
            task_analysis: Task analysis
            
        Returns:
            Status response string
        """
        from .state_schema import StateKeys
        
        # Get current world state
        position = session_state.get(StateKeys.MINECRAFT_POSITION, {})
        health = session_state.get(StateKeys.MINECRAFT_HEALTH, 20)
        food = session_state.get(StateKeys.MINECRAFT_FOOD, 20)
        
        status_parts = []
        
        if position:
            status_parts.append(f"Position: ({position.get('x', 0):.0f}, {position.get('y', 0):.0f}, {position.get('z', 0):.0f})")
            
        if health < 20:
            status_parts.append(f"Health: {health}/20")
            
        if food < 20:
            status_parts.append(f"Food: {food}/20")
            
        status_str = " | ".join(status_parts) if status_parts else "Status unknown"
        
        task_type = task_analysis.get("task_type", "unknown")
        if task_type == "gather":
            return f"🔄 Gathering task in progress... {status_str}"
        elif task_type == "craft":
            return f"🔄 Crafting task in progress... {status_str}"
        else:
            return f"📊 Current status: {status_str}"