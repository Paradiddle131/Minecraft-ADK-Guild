"""
CoordinatorAgent - Main interface for user communication and task delegation
Implements ADK multi-agent patterns for orchestrating GathererAgent and CrafterAgent
"""

import structlog
from typing import List, Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.sessions import SessionService

from .base_minecraft_agent import BaseMinecraftAgent
from ..bridge.bridge_manager import BridgeManager

logger = structlog.get_logger(__name__)


class CoordinatorAgent(BaseMinecraftAgent):
    """Main coordinator agent that handles user interaction and delegates to sub-agents"""
    
    def __init__(
        self,
        name: str = "CoordinatorAgent",
        model: str = "gemini-2.0-flash",
        sub_agents: Optional[List[Any]] = None,
        session_service: Optional[SessionService] = None,
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
        return """You are the Coordinator Agent for a Minecraft bot system. Your role is to:

1. Analyze user requests and understand the intent
2. Delegate tasks to the appropriate sub-agent:
   - GathererAgent: For resource collection tasks (finding and mining blocks, collecting items)
   - CrafterAgent: For item crafting tasks (creating tools, blocks, or other items)
3. Monitor task progress through shared session state
4. Synthesize results and respond to the user

DELEGATION PROCESS:
- When you identify a gathering task, use transfer_to_agent('GathererAgent')
- When you identify a crafting task, use transfer_to_agent('CrafterAgent')
- The sub-agent will update session.state with results
- After delegation, check the task results in state and provide a user-friendly response

SESSION STATE KEYS:
- user_request: The original user request
- minecraft.inventory: Current inventory state
- minecraft.position: Current bot position
- task.gather.result: Results from GathererAgent
- task.craft.result: Results from CrafterAgent
- current_task: Active task being processed
- task_status: Status of current task

TASK ANALYSIS:
- "gather", "collect", "mine", "find" keywords → GathererAgent
- "craft", "make", "create", "build" keywords → CrafterAgent
- "check inventory", "what do I have" → Direct inventory check (no delegation)
- Complex requests may require multiple delegations

RESPONSE GUIDELINES:
- Always acknowledge the user's request
- Explain what you're delegating and why
- Report results clearly after delegation
- If a task fails, explain why and suggest alternatives
- Provide helpful context about the Minecraft world state

IMPORTANT:
- You are the ONLY agent that communicates with the user
- Sub-agents work silently and communicate only through state
- Always read task results from state after delegation
- Maintain a helpful, informative tone

Current sub-agents available: {sub_agent_names}
"""
    
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
            "output_key": "coordinator_response",
            # Enable agent transfer capabilities
            "enable_transfers": True,
            "transfer_mode": "SINGLE"  # Only one transfer per turn
        }
        
        # Add credentials if available
        if self.ai_credentials:
            agent_config.update(self.ai_credentials)
            
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