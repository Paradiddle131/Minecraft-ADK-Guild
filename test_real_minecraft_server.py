#!/usr/bin/env python3
"""
Simple test for real Minecraft server - just check inventory
This connects to your Docker Minecraft server and asks for inventory
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Mock Google ADK before importing
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.adk'] = MagicMock()

import structlog
from dotenv import load_dotenv

from src.agents.simple_agent import SimpleMinecraftAgent
from src.config import get_config

# Load environment variables
load_dotenv()

# Simple logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class SimpleMinecraftTest:
    """Simple test that connects to your Docker Minecraft server"""
    
    def __init__(self):
        self.config = get_config()
        self.agent = None
        
    async def test_inventory_query(self):
        """Test inventory query with real Minecraft server"""
        logger.info("🎮 Testing Minecraft Inventory Query")
        logger.info("=" * 50)
        
        # Show config
        logger.info(f"Minecraft Server: {self.config.minecraft_host}:{self.config.minecraft_port}")
        logger.info(f"Bot name: {self.config.bot_username}")
        logger.info(f"API Key configured: {bool(self.config.google_ai_api_key)}")
        
        try:
            # Create agent
            logger.info("\n1️⃣ Creating agent...")
            self.agent = SimpleMinecraftAgent(
                name="InventoryTestBot",
                config=self.config
            )
            
            # Initialize (this connects to Minecraft)
            logger.info("\n2️⃣ Connecting to Minecraft server...")
            await self.agent.initialize()
            
            # Wait for connection
            logger.info("\n3️⃣ Waiting for bot to spawn...")
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if self.agent.bridge and self.agent.bridge.is_connected:
                    if hasattr(self.agent.bridge, 'is_spawned') and self.agent.bridge.is_spawned:
                        logger.info("✅ Bot spawned successfully!")
                        break
                    elif hasattr(self.agent.bridge, 'bot_spawned') and self.agent.bridge.bot_spawned:
                        logger.info("✅ Bot spawned successfully!")
                        break
                await asyncio.sleep(1)
            else:
                logger.warning("⚠️  Bot may not have spawned, continuing anyway...")
            
            # Give it a moment to settle
            await asyncio.sleep(2)
            
            # Test inventory query
            logger.info("\n4️⃣ Testing inventory query...")
            query = "what items do you have in your inventory?"
            logger.info(f"Query: '{query}'")
            
            start_time = time.time()
            response = await self.agent.process_command(query, player="TestPlayer")
            execution_time = time.time() - start_time
            
            logger.info("\n5️⃣ Results:")
            logger.info(f"Response time: {execution_time:.2f} seconds")
            logger.info(f"Response length: {len(response) if response else 0} characters")
            logger.info("Response:")
            logger.info("-" * 30)
            logger.info(response or "No response received")
            logger.info("-" * 30)
            
            # Basic validation
            success = bool(response and len(response) > 10)
            logger.info(f"\n✅ Test result: {'SUCCESS' if success else 'FAILED'}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            if self.agent and self.agent.bridge:
                try:
                    await self.agent.bridge.close()
                except:
                    pass


async def main():
    """Run the test"""
    print("🚀 Simple Minecraft Server Test")
    print("This will connect to your Docker Minecraft server and test inventory query")
    print()
    
    # Check if bot.js should be running
    config = get_config()
    print(f"📍 Will connect to: {config.minecraft_host}:{config.minecraft_port}")
    print(f"🤖 Bot username: {config.bot_username}")
    print()
    
    print("⚠️  Make sure:")
    print("1. Your Minecraft server is running in Docker")
    print("2. Bot.js is running: node src/minecraft/bot.js")
    print("3. The bot can connect to your server")
    print()
    
    input("Press Enter to continue (or Ctrl+C to cancel)...")
    
    # Run test
    test = SimpleMinecraftTest()
    success = await test.test_inventory_query()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("Your inventory query system is working!")
    else:
        print("\n❌ Test failed!")
        print("Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test cancelled by user")
        sys.exit(0)