"""
Base Minecraft Agent class with bridge integration
Provides common functionality for all Minecraft agents
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from ..bridge.bridge_manager import BridgeManager
from ..config import AgentConfig, get_config, setup_google_ai_credentials
from ..logging_config import get_logger
from ..minecraft_data_service import MinecraftDataService
from ..minecraft_bot_controller import BotController

logger = get_logger(__name__)


class BaseMinecraftAgent(ABC):
    """Base class for all Minecraft agents with bridge access"""
    
    def __init__(
        self,
        name: str,
        bridge_manager: Optional[BridgeManager] = None,
        config: Optional[AgentConfig] = None
    ):
        """Initialize base agent with bridge access
        
        Args:
            name: Agent name for identification
            bridge_manager: Shared BridgeManager instance
            config: Agent configuration
        """
        self.name = name
        self.bridge = bridge_manager
        self.config = config or get_config()
        self.ai_credentials = None
        
        # Initialize MinecraftDataService
        minecraft_version = getattr(self.config, 'minecraft_version', '1.21.1')
        self.mc_data = MinecraftDataService(minecraft_version)
        logger.info(f"{self.name}: Initialized MinecraftDataService for version {minecraft_version}")
        
        # Initialize BotController if bridge is available
        self.bot_controller = BotController(bridge_manager) if bridge_manager else None
        if self.bot_controller:
            logger.info(f"{self.name}: Initialized BotController")
        
        # Setup Google AI credentials if not already configured
        try:
            self.ai_credentials = setup_google_ai_credentials(self.config)
            logger.info(f"{self.name}: Google AI credentials configured")
        except ValueError as e:
            logger.warning(f"{self.name}: Google AI credentials not configured: {e}")
            
    async def initialize_bridge(self) -> bool:
        """Initialize bridge connection if not already connected
        
        Returns:
            True if bridge is initialized and connected
        """
        if not self.bridge:
            logger.error(f"{self.name}: No bridge manager provided")
            return False
            
        if not self.bridge.is_connected:
            logger.info(f"{self.name}: Initializing bridge connection")
            try:
                await self.bridge.initialize()
                logger.info(f"{self.name}: Bridge initialized successfully")
                return True
            except Exception as e:
                logger.error(f"{self.name}: Failed to initialize bridge: {e}")
                return False
        else:
            logger.info(f"{self.name}: Bridge already connected")
            return True
            
    async def check_minecraft_state(self) -> Dict[str, Any]:
        """Check current Minecraft world state
        
        Returns:
            Dictionary with position, inventory, and health info
        """
        state = {}
        
        if not self.bridge or not self.bridge.is_connected:
            logger.warning(f"{self.name}: Bridge not connected for state check")
            return {"error": "Bridge not connected"}
            
        try:
            # Get position
            position = await self.bridge.get_position()
            if isinstance(position, dict) and "error" not in position:
                state["position"] = position
                
            # Get inventory
            inventory = await self.bridge.get_inventory()
            if isinstance(inventory, list):
                # Summarize inventory
                summary = {}
                for item in inventory:
                    name = item.get("name", "unknown")
                    count = item.get("count", 0)
                    summary[name] = summary.get(name, 0) + count
                state["inventory"] = summary
                
            # Get health and food
            health = await self.bridge.execute_command("return bot.health")
            if isinstance(health, (int, float)):
                state["health"] = health
                
            food = await self.bridge.execute_command("return bot.food")
            if isinstance(food, (int, float)):
                state["food"] = food
                
            logger.info(f"{self.name}: Minecraft state check complete")
            return state
            
        except Exception as e:
            logger.error(f"{self.name}: Error checking Minecraft state: {e}")
            return {"error": str(e)}
            
    @abstractmethod
    def create_agent(self):
        """Create the ADK agent instance - must be implemented by subclasses"""
        pass
        
    def get_bridge_status(self) -> Dict[str, bool]:
        """Get current bridge connection status
        
        Returns:
            Dictionary with connection status flags
        """
        if not self.bridge:
            return {
                "has_bridge": False,
                "is_connected": False,
                "is_spawned": False
            }
            
        return {
            "has_bridge": True,
            "is_connected": self.bridge.is_connected,
            "is_spawned": self.bridge.is_spawned
        }