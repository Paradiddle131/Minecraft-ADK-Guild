#!/usr/bin/env python3
"""
E2E Test Runner for Inventory Query with Real Minecraft Server
Connect to your Docker Minecraft server and test inventory functionality
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
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

# Configure simplified logging
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


class E2ETestRunner:
    """Simple end-to-end test with real Minecraft server"""
    
    def __init__(self):
        self.config = get_config()
        self.agent = None
        self.start_time = time.time()
        self.results = []
        
    def log_result(self, step: str, success: bool, details: str = ""):
        """Log a test result"""
        result = {
            "step": step,
            "success": success,
            "details": details,
            "timestamp": time.time() - self.start_time
        }
        self.results.append(result)
        status = "✅" if success else "❌"
        logger.info(f"{status} {step}: {details}")
        
    async def setup(self):
        """Setup the agent and connect to Minecraft"""
        try:
            logger.info("🔧 Setting up test agent...")
            
            # Create agent
            self.agent = SimpleMinecraftAgent(
                name="E2ETestAgent", 
                config=self.config
            )
            
            # Initialize (connects to Minecraft)
            await self.agent.initialize()
            self.log_result("Agent Setup", True, "Agent created and initialized")
            
            return True
            
        except Exception as e:
            self.log_result("Agent Setup", False, f"Failed: {e}")
            logger.error(f"Setup failed: {e}")
            return False
            
    async def wait_for_connection(self, timeout: float = 30):
        """Wait for Minecraft connection and spawn"""
        logger.info("🔌 Waiting for Minecraft connection...")
        start = time.time()
        
        while time.time() - start < timeout:
            if self.agent and self.agent.bridge:
                # Check connection
                if hasattr(self.agent.bridge, 'is_connected') and self.agent.bridge.is_connected:
                    # Check if spawned
                    spawned = False
                    if hasattr(self.agent.bridge, 'is_spawned'):
                        spawned = self.agent.bridge.is_spawned
                    elif hasattr(self.agent.bridge, 'bot_spawned'):
                        spawned = self.agent.bridge.bot_spawned
                    
                    if spawned:
                        wait_time = time.time() - start
                        self.log_result("Connection", True, f"Connected and spawned in {wait_time:.1f}s")
                        return True
                    else:
                        logger.info("Connected but waiting for spawn...")
                        
            await asyncio.sleep(1)
            
        self.log_result("Connection", False, f"Timeout after {timeout}s")
        return False
        
    async def run_inventory_query(self):
        """Run the inventory query test"""
        query = "what items do you have in your inventory?"
        logger.info(f"📦 Testing inventory query: '{query}'")
        
        start_time = time.time()
        
        try:
            # Execute the query
            response = await self.agent.process_command(query, player="TestPlayer")
            execution_time = time.time() - start_time
            
            # Check if we got a response
            if response and len(response) > 10:
                self.log_result("Inventory Query", True, 
                              f"Got response in {execution_time:.2f}s ({len(response)} chars)")
                
                # Show the response
                logger.info("📋 Agent Response:")
                logger.info("-" * 50)
                logger.info(response)
                logger.info("-" * 50)
                
                return response
            else:
                self.log_result("Inventory Query", False, 
                              f"No valid response (got: {response})")
                return None
                
        except Exception as e:
            self.log_result("Inventory Query", False, f"Error: {e}")
            logger.error(f"Query failed: {e}")
            return None
            
    def generate_report(self):
        """Generate simple test report"""
        total_time = time.time() - self.start_time
        passed_tests = sum(1 for r in self.results if r["success"])
        total_tests = len(self.results)
        
        report = [
            "# Simple Minecraft Inventory Test Report\n\n",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"**Total Time**: {total_time:.2f} seconds\n",
            f"**Tests Passed**: {passed_tests}/{total_tests}\n",
            f"**Server**: {self.config.minecraft_host}:{self.config.minecraft_port}\n\n",
            "## Test Results\n\n"
        ]
        
        for result in self.results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            report.append(f"- **{result['step']}**: {status}\n")
            if result["details"]:
                report.append(f"  - {result['details']}\n")
            report.append(f"  - Time: {result['timestamp']:.2f}s\n\n")
        
        return "".join(report)
        
    async def cleanup(self):
        """Clean up resources"""
        if self.agent and self.agent.bridge:
            try:
                await self.agent.bridge.close()
                self.log_result("Cleanup", True, "Resources cleaned up")
            except Exception as e:
                self.log_result("Cleanup", False, f"Cleanup error: {e}")
            
    async def run(self):
        """Run the simple E2E test"""
        logger.info("🚀 Starting Simple Minecraft Inventory Test")
        logger.info(f"🎯 Target: {self.config.minecraft_host}:{self.config.minecraft_port}")
        
        try:
            # Step 1: Setup
            if not await self.setup():
                return False
            
            # Step 2: Connect and spawn
            if not await self.wait_for_connection():
                self.log_result("Overall Test", False, "Failed to connect to Minecraft")
                return False
                
            # Step 3: Test inventory
            response = await self.run_inventory_query()
            
            # Step 4: Final result
            if response:
                self.log_result("Overall Test", True, "Inventory query successful!")
                success = True
            else:
                self.log_result("Overall Test", False, "Inventory query failed")
                success = False
            
            # Generate report
            report = self.generate_report()
            report_path = "minecraft_test_report.md"
            with open(report_path, "w") as f:
                f.write(report)
            logger.info(f"📄 Report saved to: {report_path}")
            
            return success
            
        except Exception as e:
            self.log_result("Overall Test", False, f"Exception: {e}")
            logger.error(f"Test failed with exception: {e}")
            return False
            
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    print("🎮 Minecraft Server Inventory Test")
    print("=" * 50)
    
    config = get_config()
    print(f"🎯 Server: {config.minecraft_host}:{config.minecraft_port}")
    print(f"🤖 Bot: {config.bot_username}")
    print(f"🔑 API Key: {'✅ Configured' if config.google_ai_api_key else '❌ Missing'}")
    
    if not config.google_ai_api_key:
        print("\n⚠️  No Google AI API key found!")
        print("Set MINECRAFT_AGENT_GOOGLE_AI_API_KEY in .env file")
        print("Get your key from: https://aistudio.google.com/app/apikey")
    
    print("\n📋 This test will:")
    print("1. Connect to your Docker Minecraft server")
    print("2. Ask the bot: 'what items do you have in your inventory?'")
    print("3. Show the agent's response")
    print("4. Generate a test report")
    
    print("\n⚠️  Make sure:")
    print("• Your Minecraft server is running in Docker")
    print("• Run: node src/minecraft/bot.js")
    print("• The bot can connect to your server")
    
    print("\nPress Enter to continue (or Ctrl+C to cancel)...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n👋 Test cancelled")
        return
    
    # Run test
    runner = E2ETestRunner()
    success = await runner.run()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("Your inventory query system is working with the real Minecraft server!")
    else:
        print("\n❌ Test failed!")
        print("Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)