# Transfer to Agent Pattern Updates

## Summary

Updated all references from the old "transfer_to_agent" pattern to the new AgentTool pattern throughout the codebase. The CoordinatorAgent now uses GathererAgent and CrafterAgent as AgentTools rather than sub-agents with direct transfer mechanisms.

## Files Updated

### 1. CLAUDE.md
- Updated "Multi-Agent Hierarchy" section to reflect AgentTool usage
- Updated "ADK Components We DON'T Use" to clarify we don't use transfer_to_agent pattern
- Changed from: "LLM-driven delegation via transfer_to_agent for dynamic task routing"
- Changed to: "LLM-driven tool selection for dynamic task routing"

### 2. tests/test_craft_stick_current_behavior.py
- Updated event detection logic to look for AgentTool usage patterns
- Updated assertions and observations to reference "uses CrafterAgent tool" instead of "transfers to CrafterAgent"
- Updated desired behavior description to use AgentTool terminology

### 3. tests/test_coordinator_craft_flow.py
- Updated mock coordinator fixture to use tools instead of sub_agents
- Updated comments to reflect AgentTool pattern throughout the test cases
- Changed expectations from "transfer to agent" to "use agent tool"

### 4. tests/test_craft_stick_demonstration.py
- Updated demonstration flow to show "Uses CrafterAgent tool" instead of "Transfers to CrafterAgent"
- Updated all coordinator action descriptions to use AgentTool terminology
- Updated key points to reference "tool calls" instead of "transfers"

### 5. src/agents/state_schema.py
- Renamed state key from AGENT_TRANSFER_REASON to AGENT_TOOL_REASON
- This better reflects the new AgentTool pattern where agents are invoked as tools

### 6. docs/interactive-agent-loop-architecture.dot
- Updated diagram labels from "transfer_to_agent" to "AgentTool call"
- Regenerated PNG diagram with updated terminology

## Impact

These changes ensure consistency throughout the codebase with the new AgentTool pattern. All documentation, tests, and diagrams now accurately reflect the current architecture where:

1. CoordinatorAgent uses GathererAgent and CrafterAgent as tools
2. There is no direct "transfer" between agents
3. Agent communication happens through tool invocations and shared state
4. The LLM decides which tool to use based on context and goals

## No Changes Required

The following file was checked but didn't require updates:
- docs/interactive-agent-loop-flow.dot - Already uses generic "delegates" terminology