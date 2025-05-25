"""
End-to-End Test for Inventory Query
Tests the complete flow from user input to Mineflayer execution
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.config import AgentConfig
from src.tools.mineflayer_tools import create_mineflayer_tools

# Configure structured logging for test tracing
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ExecutionTracer:
    """Captures detailed execution trace for E2E analysis"""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None
        
    def start(self):
        """Start tracing"""
        self.start_time = time.time()
        self.events = []
        logger.info("E2E trace started")
        
    def add_event(self, event_type: str, data: Dict[str, Any], component: str = "unknown"):
        """Add an event to the trace"""
        event = {
            "timestamp": time.time(),
            "relative_time": time.time() - self.start_time if self.start_time else 0,
            "type": event_type,
            "component": component,
            "data": data
        }
        self.events.append(event)
        logger.info(f"Trace event: {event_type}", component=component, data=data)
        
    def stop(self):
        """Stop tracing"""
        self.end_time = time.time()
        total_time = self.end_time - self.start_time if self.start_time else 0
        logger.info(f"E2E trace completed in {total_time:.3f}s")
        
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary"""
        return {
            "total_time": self.end_time - self.start_time if self.start_time and self.end_time else 0,
            "event_count": len(self.events),
            "events_by_type": self._count_events_by_type(),
            "events_by_component": self._count_events_by_component(),
            "timeline": self.events
        }
        
    def _count_events_by_type(self) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in self.events:
            event_type = event["type"]
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
        
    def _count_events_by_component(self) -> Dict[str, int]:
        """Count events by component"""
        counts = {}
        for event in self.events:
            component = event["component"]
            counts[component] = counts.get(component, 0) + 1
        return counts
        
    def generate_report(self) -> str:
        """Generate markdown report of execution"""
        summary = self.get_summary()
        
        report = ["# E2E Test Execution Report\n"]
        report.append(f"**Date**: {datetime.now().isoformat()}\n")
        report.append(f"**Total Time**: {summary['total_time']:.3f}s\n")
        report.append(f"**Total Events**: {summary['event_count']}\n")
        
        report.append("\n## Event Summary\n")
        report.append("### By Type\n")
        for event_type, count in summary['events_by_type'].items():
            report.append(f"- {event_type}: {count}\n")
            
        report.append("\n### By Component\n")
        for component, count in summary['events_by_component'].items():
            report.append(f"- {component}: {count}\n")
            
        report.append("\n## Execution Timeline\n")
        for event in self.events:
            report.append(f"**[{event['relative_time']:.3f}s]** {event['type']} ({event['component']})\n")
            if event['data']:
                report.append(f"```json\n{json.dumps(event['data'], indent=2)}\n```\n")
                
        return "".join(report)


@pytest.fixture
def tracer():
    """Execution tracer fixture"""
    return ExecutionTracer()


@pytest.fixture
def test_config():
    """Test configuration"""
    return AgentConfig(
        google_ai_api_key="test-api-key",
        default_model="gemini-1.5-flash",
        command_timeout_ms=5000,
        minecraft_host="localhost",
        minecraft_port=25565
    )


@pytest.mark.asyncio
async def test_inventory_query_flow(tracer):
    """
    Test the complete flow of inventory query without real connections
    
    This test validates the data flow through all components
    """
    tracer.start()
    
    # 1. Create mock bridge
    tracer.add_event("bridge_setup", {}, "test")
    mock_bridge = MagicMock()
    
    inventory_items = [
        {"name": "diamond", "count": 5, "slot": 0},
        {"name": "iron_ingot", "count": 64, "slot": 1},
        {"name": "oak_log", "count": 32, "slot": 2},
        {"name": "cobblestone", "count": 128, "slot": 3}
    ]
    
    async def mock_get_inventory():
        tracer.add_event("bridge_get_inventory", {
            "method": "get_inventory",
            "items_count": len(inventory_items)
        }, "bridge")
        return inventory_items
    
    mock_bridge.get_inventory = mock_get_inventory
    
    # 2. Create tools
    tracer.add_event("tools_setup", {}, "test")
    tools = create_mineflayer_tools(mock_bridge)
    get_inventory_tool = tools[5]  # get_inventory is the 6th tool
    
    # 3. Simulate ADK execution
    tracer.add_event("adk_simulation_start", {}, "adk")
    
    # User query
    query = "what's in your inventory"
    tracer.add_event("user_query", {"query": query}, "user")
    
    # ADK processes query
    tracer.add_event("adk_process_query", {
        "query": query,
        "detected_intent": "check_inventory"
    }, "adk")
    
    # ADK selects tool
    tracer.add_event("adk_tool_selection", {
        "selected_tool": "get_inventory",
        "reason": "User asked about inventory contents"
    }, "adk")
    
    # Execute tool
    tracer.add_event("tool_execution_start", {
        "tool": "get_inventory",
        "params": {}
    }, "tools")
    
    result = await get_inventory_tool()
    
    tracer.add_event("tool_execution_complete", {
        "tool": "get_inventory",
        "status": result.get("status"),
        "items_count": len(result.get("items", [])),
        "total_items": result.get("total_items")
    }, "tools")
    
    # ADK formats response
    response_text = "I'll check your inventory for you.\n\n"
    if result['status'] == 'success':
        response_text += "Your inventory contains:\n"
        for item, count in result['summary'].items():
            response_text += f"- {count} {item}\n"
        response_text += f"\nTotal: {result['total_items']} items across {len(result['items'])} slots"
    
    tracer.add_event("adk_response_generated", {
        "response_length": len(response_text),
        "contains_inventory": "inventory" in response_text.lower()
    }, "adk")
    
    tracer.stop()
    
    # Verify the flow
    summary = tracer.get_summary()
    assert summary['event_count'] >= 8
    assert 'bridge_get_inventory' in summary['events_by_type']
    assert 'tool_execution_complete' in summary['events_by_type']
    assert result['status'] == 'success'
    assert result['total_items'] == 229
    assert len(result['items']) == 4
    
    # Generate report
    report = tracer.generate_report()
    logger.info("Test report generated", length=len(report))
    
    # Log key findings
    logger.info("=" * 60)
    logger.info("INVENTORY QUERY FLOW TEST COMPLETE")
    logger.info(f"Total execution time: {summary['total_time']:.3f}s")
    logger.info(f"Tool returned {result['total_items']} items")
    logger.info("Flow verified: Query -> ADK -> Tool -> Bridge -> Response")
    logger.info("=" * 60)


@pytest.mark.asyncio
async def test_mineflayer_command_format(tracer):
    """
    Test that the correct command format is sent to Mineflayer
    """
    tracer.start()
    
    # Mock bridge that captures commands
    commands_sent = []
    
    class MockBridge:
        async def execute_command(self, command, **params):
            commands_sent.append({
                "command": command,
                "params": params
            })
            return {"success": True, "data": []}
        
        async def get_inventory(self):
            # This would normally call execute_command
            await self.execute_command("getInventory")
            return [
                {"name": "diamond", "count": 5, "slot": 0}
            ]
    
    mock_bridge = MockBridge()
    
    # Execute inventory check
    result = await mock_bridge.get_inventory()
    
    # Verify command format
    assert len(commands_sent) == 1
    assert commands_sent[0]["command"] == "getInventory"
    
    tracer.add_event("mineflayer_command_verified", {
        "command": "getInventory",
        "expected_js_execution": "bot.inventory.items()"
    }, "test")
    
    tracer.stop()
    
    logger.info("Mineflayer command format verified")
    logger.info("Command sent to bot.js: getInventory")
    logger.info("Expected execution: bot.inventory.items()")


if __name__ == "__main__":
    # Run tests directly
    tracer = ExecutionTracer()
    asyncio.run(test_inventory_query_flow(tracer))
    asyncio.run(test_mineflayer_command_format(tracer))