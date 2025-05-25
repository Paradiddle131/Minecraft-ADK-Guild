#!/usr/bin/env python3
"""
Standalone E2E Test Runner for Inventory Query
Run this script to test the complete flow with a real Minecraft server
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import structlog
from dotenv import load_dotenv

from src.agents.simple_agent import SimpleMinecraftAgent
from src.bridge.bridge_manager import BridgeManager
from src.bridge.event_stream import EventStreamProcessor
from src.config import get_config
from src.minecraft.bot import run_bot

# Load environment variables
load_dotenv()

# Configure logging with detailed formatting
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


class E2ETestRunner:
    """Runs end-to-end test with real components"""
    
    def __init__(self):
        self.config = get_config()
        self.bridge = None
        self.event_processor = None
        self.agent = None
        self.trace_events = []
        self.start_time = None
        
    def log_trace(self, event_type: str, data: dict, component: str = "test"):
        """Log a trace event"""
        event = {
            "timestamp": time.time(),
            "relative_time": time.time() - self.start_time if self.start_time else 0,
            "type": event_type,
            "component": component,
            "data": data
        }
        self.trace_events.append(event)
        logger.info(f"[TRACE] {event_type}", **data, component=component)
        
    async def setup(self):
        """Setup all components"""
        logger.info("Setting up E2E test components")
        self.start_time = time.time()
        
        # Initialize bridge
        self.log_trace("bridge_init", {"timeout": self.config.command_timeout_ms}, "bridge")
        self.bridge = BridgeManager(timeout_ms=self.config.command_timeout_ms)
        await self.bridge.initialize()
        
        # Initialize event processor
        self.log_trace("event_processor_init", {}, "events")
        self.event_processor = EventStreamProcessor(self.bridge.event_queue)
        await self.event_processor.initialize()
        
        # Initialize agent
        self.log_trace("agent_init", {
            "model": self.config.default_model,
            "has_api_key": bool(self.config.google_ai_api_key)
        }, "agent")
        
        self.agent = SimpleMinecraftAgent(
            bridge_manager=self.bridge,
            event_processor=self.event_processor,
            config=self.config
        )
        
        try:
            await self.agent.initialize()
            self.log_trace("agent_initialized", {
                "session_id": self.agent.session.id if self.agent.session else None
            }, "agent")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
            
    async def wait_for_connection(self, timeout: float = 30):
        """Wait for Minecraft connection"""
        logger.info("Waiting for Minecraft server connection...")
        start = time.time()
        
        while time.time() - start < timeout:
            if self.bridge.is_connected():
                self.log_trace("minecraft_connected", {
                    "wait_time": time.time() - start
                }, "connection")
                logger.info("✓ Connected to Minecraft server")
                return True
            await asyncio.sleep(0.5)
            
        logger.error("✗ Failed to connect to Minecraft server")
        return False
        
    async def run_inventory_query(self):
        """Run the actual inventory query test"""
        query = "what's in your inventory"
        logger.info(f"Executing query: '{query}'")
        
        self.log_trace("query_start", {
            "query": query,
            "player": "TestPlayer"
        }, "test")
        
        # Capture detailed execution metrics
        start_time = time.time()
        
        try:
            # Execute the command
            response = await self.agent.process_command(query, player="TestPlayer")
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            self.log_trace("query_complete", {
                "response": response,
                "execution_time": execution_time,
                "response_length": len(response) if response else 0
            }, "test")
            
            # Log the response
            logger.info("=" * 60)
            logger.info("AGENT RESPONSE:")
            logger.info(response)
            logger.info("=" * 60)
            
            # Analyze response
            self.analyze_response(response, execution_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            self.log_trace("query_error", {
                "error": str(e),
                "error_type": type(e).__name__
            }, "test")
            raise
            
    def analyze_response(self, response: str, execution_time: float):
        """Analyze the response and execution"""
        analysis = {
            "execution_time": execution_time,
            "response_contains_inventory": "inventory" in response.lower() if response else False,
            "response_length": len(response) if response else 0,
            "latency_ok": execution_time < 0.5,  # Target <500ms
        }
        
        # Check for expected inventory items
        expected_keywords = ["item", "empty", "contains", "slot"]
        found_keywords = [kw for kw in expected_keywords if kw in response.lower()] if response else []
        analysis["found_keywords"] = found_keywords
        
        self.log_trace("response_analysis", analysis, "analysis")
        
        # Log analysis
        logger.info("Response Analysis:")
        logger.info(f"  - Execution time: {execution_time:.3f}s")
        logger.info(f"  - Response length: {analysis['response_length']} chars")
        logger.info(f"  - Contains inventory info: {analysis['response_contains_inventory']}")
        logger.info(f"  - Latency target met: {analysis['latency_ok']}")
        
    def generate_report(self):
        """Generate execution report"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        # Count events by type
        event_counts = {}
        for event in self.trace_events:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
        report = [
            "# E2E Inventory Query Test Report\n",
            f"**Date**: {datetime.now().isoformat()}\n",
            f"**Total Time**: {total_time:.3f}s\n",
            f"**Total Events**: {len(self.trace_events)}\n",
            f"**Config**: Model={self.config.default_model}, Timeout={self.config.command_timeout_ms}ms\n",
            "\n## Event Summary\n"
        ]
        
        for event_type, count in sorted(event_counts.items()):
            report.append(f"- {event_type}: {count}\n")
            
        report.append("\n## Execution Timeline\n")
        for event in self.trace_events:
            report.append(f"\n### [{event['relative_time']:.3f}s] {event['type']} ({event['component']})\n")
            if event['data']:
                report.append("```json\n")
                report.append(json.dumps(event['data'], indent=2))
                report.append("\n```\n")
                
        return "".join(report)
        
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up test resources")
        
        if self.event_processor:
            await self.event_processor.cleanup()
            
        if self.bridge:
            await self.bridge.cleanup()
            
    async def run(self):
        """Run the complete E2E test"""
        logger.info("Starting E2E Inventory Query Test")
        logger.info(f"Minecraft Server: {self.config.minecraft_host}:{self.config.minecraft_port}")
        
        try:
            # Setup components
            await self.setup()
            
            # Wait for connection
            if not await self.wait_for_connection():
                logger.error("Cannot proceed without Minecraft connection")
                logger.error("Make sure:")
                logger.error("1. Minecraft server is running")
                logger.error("2. Run: node src/minecraft/bot.js")
                return False
                
            # Give bot time to fully spawn
            logger.info("Waiting for bot to fully spawn...")
            await asyncio.sleep(2)
            
            # Run the test
            await self.run_inventory_query()
            
            # Generate report
            report = self.generate_report()
            report_path = "e2e_inventory_test_report.md"
            with open(report_path, "w") as f:
                f.write(report)
            logger.info(f"Report written to {report_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"E2E test failed: {e}", exc_info=True)
            return False
            
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    # Check for API key
    config = get_config()
    if not config.google_ai_api_key:
        logger.warning("=" * 60)
        logger.warning("No Google AI API key found!")
        logger.warning("Set MINECRAFT_AGENT_GOOGLE_AI_API_KEY in .env file")
        logger.warning("Get your key from: https://aistudio.google.com/app/apikey")
        logger.warning("=" * 60)
        
    logger.info("=" * 60)
    logger.info("E2E Test: Inventory Query")
    logger.info("This test will:")
    logger.info("1. Connect to Minecraft server")
    logger.info("2. Send 'what's in your inventory' query")
    logger.info("3. Trace the complete execution flow")
    logger.info("4. Generate a detailed report")
    logger.info("=" * 60)
    
    # Ensure bot.js is running
    logger.info("\nMake sure bot.js is running:")
    logger.info("  node src/minecraft/bot.js")
    logger.info("\nPress Ctrl+C to cancel, or wait to continue...\n")
    
    await asyncio.sleep(3)
    
    # Run test
    runner = E2ETestRunner()
    success = await runner.run()
    
    if success:
        logger.info("✓ E2E test completed successfully")
    else:
        logger.error("✗ E2E test failed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)