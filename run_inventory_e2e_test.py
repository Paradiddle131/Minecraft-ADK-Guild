#!/usr/bin/env python3
"""
E2E Test Runner for Inventory Query with Real Minecraft Server
Connect to your Docker Minecraft server and test inventory functionality

This test validates structured output from the ADK agent:
- Checks session.state['minecraft_inventory'] for structured data
- Falls back to text parsing for backwards compatibility
- Ensures deterministic testing of inventory queries
"""

import asyncio
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
# MagicMock no longer needed since we're not mocking Google imports

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Note: Google ADK is now properly installed and doesn't need mocking
# The old mocking was preventing the actual imports from working

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
            logger.info("Creating SimpleMinecraftAgent...")
            self.agent = SimpleMinecraftAgent(
                name="E2ETestAgent", 
                config=self.config
            )
            logger.info("Agent created, now initializing...")
            
            # Initialize (connects to Minecraft)
            await self.agent.initialize()
            logger.info("Agent initialization completed")
            self.log_result("Agent Setup", True, "Agent created and initialized")
            
            return True
            
        except Exception as e:
            self.log_result("Agent Setup", False, f"Failed: {e}")
            logger.error(f"Setup failed: {e}")
            return False
            
    async def wait_for_connection(self, timeout: float = 60):
        """Wait for Minecraft connection and spawn"""
        logger.info("🔌 Waiting for Minecraft connection...")
        start = time.time()
        
        while time.time() - start < timeout:
            if self.agent and self.agent.bridge:
                # Check connection
                bridge_connected = hasattr(self.agent.bridge, 'is_connected') and self.agent.bridge.is_connected
                logger.debug(f"Bridge connected: {bridge_connected}")
                
                if bridge_connected:
                    # Check if spawned
                    spawned = False
                    if hasattr(self.agent.bridge, 'is_spawned'):
                        spawned = self.agent.bridge.is_spawned
                        logger.debug(f"Bridge is_spawned: {spawned}")
                    elif hasattr(self.agent.bridge, 'bot_spawned'):
                        spawned = self.agent.bridge.bot_spawned
                        logger.debug(f"Bridge bot_spawned: {spawned}")
                    
                    if spawned:
                        wait_time = time.time() - start
                        self.log_result("Connection", True, f"Connected and spawned in {wait_time:.1f}s")
                        return True
                    else:
                        # Only log occasionally to avoid spam
                        if int(time.time() - start) % 5 == 0:
                            logger.info(f"Connected but waiting for spawn... (bridge connected: {bridge_connected}, spawned: {spawned})")
                else:
                    # Log connection status occasionally
                    if int(time.time() - start) % 5 == 0:
                        logger.info(f"Waiting for bridge connection... (time elapsed: {time.time() - start:.1f}s)")
                        
            await asyncio.sleep(1)
        
        # Connection/spawn failed - this is a critical failure
        self.log_result("Connection", False, f"Bot failed to spawn after {timeout}s")
        return False
        
    async def run_birch_planks_validation(self):
        """Run specific validation for Birch Planks in inventory"""
        query = "what items do you have in your inventory?"
        logger.info(f"🌳 Testing Birch Planks validation: '{query}'")
        
        start_time = time.time()
        
        try:
            # Execute the query
            logger.info(f"Executing command: {query}")
            try:
                response = await self.agent.process_command(query, player="TestPlayer")
                execution_time = time.time() - start_time
                logger.info(f"Got response in {execution_time:.2f}s: {response[:100] if response else 'None'}...")
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                self.log_result("Birch Planks Validation", False, f"Command execution failed: {e}")
                return None
            
            # Specific check for Birch Planks mention
            if response and len(response) > 5:
                has_birch_mention = 'birch' in response.lower() and 'plank' in response.lower()
                
                if has_birch_mention:
                    self.log_result("Birch Planks Validation", True, 
                                  f"✅ Agent correctly mentioned Birch Planks in {execution_time:.2f}s")
                    
                    # Show agent response prominently in console
                    print("\n🌳 ✅ BIRCH PLANKS VALIDATION SUCCESS!")
                    print("=" * 60)
                    print(f"🤖 AGENT RESPONSE: {response.strip()}")
                    print("=" * 60)
                    print("✅ Confirmed: Agent correctly mentioned Birch Planks!")
                    
                    return response
                else:
                    self.log_result("Birch Planks Validation", False, 
                                  f"❌ Agent did not mention Birch Planks: {response[:100]}...")
                    logger.error("Agent response does not mention Birch Planks")
                    return None
            else:
                self.log_result("Birch Planks Validation", False, 
                              f"No valid response (got: {response})")
                return None
                
        except Exception as e:
            self.log_result("Birch Planks Validation", False, f"Error: {e}")
            logger.error(f"Birch Planks validation failed: {e}")
            return None

    async def run_inventory_query(self):
        """Run the inventory query test"""
        query = "what items do you have in your inventory?"
        logger.info(f"📦 Testing inventory query: '{query}'")
        
        start_time = time.time()
        
        try:
            # Execute the query
            logger.info(f"Executing command: {query}")
            try:
                response = await self.agent.process_command(query, player="TestPlayer")
                execution_time = time.time() - start_time
                logger.info(f"Got response in {execution_time:.2f}s: {response[:100] if response else 'None'}...")
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                self.log_result("Inventory Query", False, f"Command execution failed: {e}")
                return None
            
            # Check session state for structured inventory data
            inventory_data = None
            if self.agent.session and hasattr(self.agent.session, 'state'):
                # First try the tool's minecraft_inventory key
                inventory_data = self.agent.session.state.get('minecraft_inventory')
                logger.info(f"Session state minecraft_inventory: {inventory_data}")
                
                # If not found, try the agent's current_inventory key as fallback
                if inventory_data is None:
                    inventory_data = self.agent.session.state.get('current_inventory')
                    logger.info(f"Session state current_inventory: {inventory_data}")
                    if inventory_data is not None:
                        # Convert to expected format
                        inventory_data = {
                            'items': [],
                            'summary': inventory_data,
                            'total_items': len(inventory_data)
                        }
            
            
            # First check structured data in session state
            if inventory_data:
                if 'error' in inventory_data:
                    self.log_result("Inventory Query", False, 
                                  f"Session state contains error: {inventory_data['error']}")
                    logger.error("Inventory query failed with error in session state")
                    return None
                elif 'items' in inventory_data:
                    # Success - we have structured inventory data
                    self.log_result("Inventory Query", True, 
                                  f"Got structured inventory data in {execution_time:.2f}s")
                    
                    logger.info("📋 Structured Inventory Data:")
                    logger.info("-" * 50)
                    logger.info(f"Total items: {inventory_data.get('total_items', 0)}")
                    if inventory_data.get('summary'):
                        for item, count in inventory_data['summary'].items():
                            logger.info(f"  - {item}: {count}")
                    logger.info("-" * 50)
                    
                    # Also show agent's text response
                    if response:
                        print("\n📋 INVENTORY QUERY RESPONSE:")
                        print("-" * 50)
                        print(f"🤖 {response.strip()}")
                        print("-" * 50)
                    
                    return inventory_data
            
            # Fallback to text parsing if no structured data (for backwards compatibility)
            # Check if we got a valid response
            # A valid response should mention inventory items or explain why it can't access them
            if response and len(response) > 10:
                # Check for error indicators in the response
                error_phrases = [
                    "cannot access my inventory",
                    "not connected to a Minecraft server",
                    "encountered an error",
                    "ADK integration may need configuration",
                    "having trouble getting the inventory",
                    "sorry, i am having trouble",
                    "please try again"
                ]
                
                is_error_response = any(phrase in response.lower() for phrase in error_phrases)
                
                if is_error_response:
                    self.log_result("Inventory Query", False, 
                                  f"Got error response: {response[:100]}...")
                    logger.error("Agent returned an error response")
                    return None
                else:
                    # For non-error responses, check if it contains actual inventory information
                    # A valid inventory response should describe items or say the inventory is empty
                    # Just mentioning "inventory" is not enough (could be "I can't access inventory")
                    
                    # Look for patterns that indicate actual inventory content
                    success_patterns = [
                        r"inventory contains:?\s*(.*)",  # "inventory contains: ..."
                        r"i have:?\s*(.*)",              # "i have: ..."
                        r"my current inventory:?\s*(.*)", # "my current inventory: ..."
                        r"items?:?\s*(.*)",              # "items: ..."
                        r"empty inventory",              # explicit empty inventory
                        r"no items",                     # explicit no items
                        r"nothing in my inventory",      # "I currently have nothing in my inventory"
                        r"inventory is empty",           # "my inventory is empty"
                        r"\d+\s+\w+",                    # item counts like "64 cobblestone"
                    ]
                    
                    import re
                    has_inventory_info = any(re.search(pattern, response.lower()) for pattern in success_patterns)
                    
                    if has_inventory_info:
                        self.log_result("Inventory Query", True, 
                                      f"Got valid inventory response in {execution_time:.2f}s ({len(response)} chars) [text parsing fallback]")
                        
                        # Show the response
                        logger.info("📋 Agent Response (no structured data):")
                        logger.info("-" * 50)
                        logger.info(response)
                        logger.info("-" * 50)
                        logger.warning("⚠️  Using text parsing fallback - structured data not available")
                        
                        return response
                    else:
                        self.log_result("Inventory Query", False, 
                                      f"Response doesn't contain inventory data: {response[:100]}...")
                        logger.warning("Response appears to be generic, not actual inventory data")
                        return None
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
            logger.info("Step 1: Setting up agent...")
            if not await self.setup():
                logger.error("Setup failed - aborting test")
                return False
            
            # Step 2: Connect and spawn
            logger.info("Step 2: Waiting for connection and spawn...")
            if not await self.wait_for_connection():
                self.log_result("Overall Test", False, "Failed to connect to Minecraft")
                logger.error("Connection failed - aborting test")
                return False
                
            # Step 3: Test inventory
            logger.info("Step 3: Running inventory query...")
            result = await self.run_inventory_query()
            
            # Step 4: Birch Planks validation
            logger.info("Step 4: Running Birch Planks validation...")
            birch_result = await self.run_birch_planks_validation()
            
            # Step 5: Final result
            logger.info("Step 5: Evaluating results...")
            
            # Check both general inventory and specific Birch Planks validation
            inventory_success = result is not None
            birch_success = birch_result is not None
            
            if inventory_success and birch_success:
                self.log_result("Overall Test", True, "✅ ALL TESTS PASSED: Inventory query AND Birch Planks validation successful!")
                logger.info("🎉 Complete success: Both general inventory and Birch Planks validation passed")
                success = True
            elif inventory_success and not birch_success:
                self.log_result("Overall Test", False, "❌ PARTIAL FAILURE: Inventory query passed but Birch Planks validation failed")
                logger.error("Inventory works but agent did not mention Birch Planks")
                success = False
            elif not inventory_success and birch_success:
                self.log_result("Overall Test", False, "❌ UNEXPECTED: Birch Planks validation passed but general inventory failed")
                logger.error("Unexpected state - this should not happen")
                success = False
            else:
                self.log_result("Overall Test", False, "❌ COMPLETE FAILURE: Both inventory query and Birch Planks validation failed")
                logger.error("Both tests failed")
                success = False
            
            # Generate report
            logger.info("Generating test report...")
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
            logger.info("Starting cleanup...")
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
    print("3. Check session state for structured inventory data")
    print("4. Validate that agent mentions 'Birch Planks' specifically")
    print("5. Show the agent's response and structured data")
    print("6. Generate a test report")
    
    print("\n⚠️  Make sure:")
    print("• Your Minecraft server is running in Docker")
    print("• Run: node src/minecraft/bot.js")
    print("• The bot can connect to your server")
    
    # Run test
    runner = E2ETestRunner()
    await runner.run()
    
    # Results are now handled within the test runner itself
    # Check the generated report for detailed results


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)