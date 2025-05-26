# Agent Implementation Plan for Minecraft ADK Guild

## Project Overview

This plan details the implementation of a specialized multi-agent system for Minecraft using Google ADK patterns. The system consists of three agents:

1. **CoordinatorAgent** - Main interface for user communication and task delegation
2. **GathererAgent** - Specialized in resource collection tasks
3. **CrafterAgent** - Specialized in item crafting tasks

The agents will leverage the existing JSPyBridge infrastructure for Minecraft interaction while adhering to ADK's multi-agent patterns for coordination and communication.

## Non-Functional Requirements

### Scalability
- Agents should handle multiple concurrent requests through proper state isolation
- Session state management must support multiple users interacting with the same bot

### Reliability & Error Handling
- Graceful degradation when Minecraft server is unavailable
- Proper error propagation from sub-agents to coordinator
- Timeout handling for long-running Minecraft operations

### Security
- Input validation for user commands
- Sanitization of Minecraft chat messages
- API key protection through environment variables

### Maintainability
- Clear separation between agent logic and Minecraft bridge
- Modular tool design for easy extension
- Comprehensive logging for debugging

## Phase 1: Core Agent Architecture

### Goals
- Establish the three-agent hierarchy following ADK patterns
- Implement basic inter-agent communication via shared state
- Create main.py entry point for user interaction

### Section 1.1: Agent Base Structure

#### Chunk 1.1.1: Create CoordinatorAgent

**File:** `src/agents/coordinator_agent.py`
**Classes:** CoordinatorAgent
**Methods:** CoordinatorAgent.__init__, CoordinatorAgent._create_instruction
**Key Variables:** CoordinatorAgent.name, CoordinatorAgent.model, CoordinatorAgent.sub_agents

**File:** `src/agents/__init__.py`
**Exports:** CoordinatorAgent, GathererAgent, CrafterAgent

#### Chunk 1.1.2: Create GathererAgent

**File:** `src/agents/gatherer_agent.py`
**Classes:** GathererAgent
**Methods:** GathererAgent.__init__, GathererAgent._create_instruction
**Key Variables:** GathererAgent.name, GathererAgent.model, GathererAgent.tools

#### Chunk 1.1.3: Create CrafterAgent

**File:** `src/agents/crafter_agent.py`
**Classes:** CrafterAgent  
**Methods:** CrafterAgent.__init__, CrafterAgent._create_instruction
**Key Variables:** CrafterAgent.name, CrafterAgent.model, CrafterAgent.tools

### Section 1.2: Main Entry Point

#### Chunk 1.2.1: Create main.py

**File:** `main.py`
**Functions:** main, setup_agents, run_agent_system, parse_args
**Key Variables:** runner, session_service, coordinator

#### Chunk 1.2.2: Environment Configuration

**File:** `.env.example`
**Variables:** MINECRAFT_AGENT_GOOGLE_AI_API_KEY, MINECRAFT_AGENT_MINECRAFT_HOST, MINECRAFT_AGENT_MINECRAFT_PORT, MINECRAFT_AGENT_BOT_USERNAME

## Phase 2: Agent Communication & Tool Integration

### Goals
- Implement LLM-driven delegation between agents
- Integrate existing Mineflayer tools with sub-agents
- Establish shared state patterns for agent communication

### Section 2.1: Inter-Agent Communication

#### Chunk 2.1.1: Configure Agent Hierarchy

Update CoordinatorAgent to properly establish sub-agent relationships and enable transfer capabilities.

**File:** `src/agents/coordinator_agent.py`
**Updates:** Add sub_agents parameter, configure transfer settings

#### Chunk 2.1.2: Shared State Schema

Define standardized state keys for agent communication.

**File:** `src/agents/state_schema.py`
**Classes:** StateKeys
**Constants:** MINECRAFT_INVENTORY, GATHER_TASK, CRAFT_TASK, TASK_RESULT

### Section 2.2: Tool Integration

#### Chunk 2.2.1: Enhance Mineflayer Tools for Agents

Update existing tools to work seamlessly with agent state management.

**File:** `src/tools/agent_tools.py`
**Functions:** create_gatherer_tools, create_crafter_tools
**Updates:** Wrap existing mineflayer_tools with state management

#### Chunk 2.2.2: Bridge Integration

Ensure BridgeManager is properly initialized and accessible to agents.

**File:** `src/agents/base_minecraft_agent.py`
**Classes:** BaseMinecraftAgent
**Methods:** BaseMinecraftAgent.__init__, BaseMinecraftAgent.initialize_bridge

## Phase 3: Specialized Agent Capabilities

### Goals
- Implement gathering logic with resource finding and collection
- Implement crafting logic with recipe management
- Add coordinator's decision-making capabilities

### Section 3.1: Gatherer Specialization

#### Chunk 3.1.1: Resource Finding Logic

**File:** `src/agents/gatherer_agent.py`
**Updates:** Add specific instructions for resource identification and pathfinding

#### Chunk 3.1.2: Collection State Management

Implement state updates for tracking gathered resources.

**File:** `src/agents/gatherer_agent.py`
**Methods:** GathererAgent._update_gather_state

### Section 3.2: Crafter Specialization

#### Chunk 3.2.1: Recipe Knowledge

**File:** `src/agents/crafter_agent.py`
**Updates:** Add crafting recipe instructions and prerequisite checking

#### Chunk 3.2.2: Multi-Step Crafting

Handle complex crafting that requires intermediate steps.

**File:** `src/agents/crafter_agent.py`
**Methods:** CrafterAgent._plan_crafting_steps

### Section 3.3: Coordinator Intelligence

#### Chunk 3.3.1: Task Analysis

**File:** `src/agents/coordinator_agent.py`
**Methods:** CoordinatorAgent._analyze_user_request

#### Chunk 3.3.2: Response Synthesis

Implement user-friendly response generation from sub-agent results.

**File:** `src/agents/coordinator_agent.py`
**Methods:** CoordinatorAgent._synthesize_response

## Interface Definitions

### Agent Communication Protocol

1. **CoordinatorAgent → Sub-agents**: Via LLM-driven delegation (transfer_to_agent)
   - Input: User request context in session.state['user_request']
   - Output: Task completion status in session.state['task_result']

2. **Sub-agents → CoordinatorAgent**: Via shared session state
   - GathererAgent: Updates session.state['gathered_resources']
   - CrafterAgent: Updates session.state['crafted_items']

3. **All Agents → Minecraft**: Via existing BridgeManager and Mineflayer tools
   - Commands sent through WebSocket connection
   - Events received through EventStream

### State Schema

```
session.state = {
    # User context
    "user_request": str,
    "user_id": str,
    
    # Minecraft state
    "minecraft_inventory": dict,
    "minecraft_position": dict,
    "minecraft_nearby_blocks": list,
    
    # Task state
    "current_task": str,
    "task_status": str,
    "task_result": dict,
    
    # Agent-specific
    "gathered_resources": dict,
    "crafted_items": dict,
    "crafting_plan": list
}
```

## Data Management

### Session Persistence
- Use InMemorySessionService for development
- State keys follow ADK conventions (no prefix for session-specific data)
- Minecraft world state cached with appropriate TTL

### Event History
- All agent actions recorded as Events with proper EventActions
- State updates via state_delta for auditability
- Agent responses saved with output_key

## Communication Layer

### Python ↔ JavaScript Bridge
- Existing WebSocket connection on port 8765
- EventStream for Minecraft events → Python
- BridgeManager for Python commands → Minecraft

### Agent ↔ Agent Communication
- Shared session.state for data passing
- LLM-driven transfer_to_agent for control flow
- No direct agent-to-agent messaging

## Testing Strategy

### Manual Testing via main.py
- Test basic commands: "check inventory", "gather 3 oak logs", "craft wooden pickaxe"
- Verify agent delegation works correctly
- Ensure state updates propagate properly

### Integration Points
- Verify BridgeManager connection
- Test Mineflayer tool execution
- Validate state persistence across agent transfers

## Step-by-Step Execution Plan

### Week 1: Foundation
1. Create directory structure and base files
2. Implement BaseMinecraftAgent with bridge initialization
3. Create three agent classes with basic structure
4. Implement main.py with ADK runner setup
5. Test basic agent instantiation and hierarchy

### Week 2: Communication
1. Add LLM-driven delegation to CoordinatorAgent
2. Implement shared state patterns
3. Integrate existing Mineflayer tools
4. Test inter-agent communication flow
5. Verify state updates work correctly

### Week 3: Specialization
1. Add gathering-specific logic to GathererAgent
2. Implement crafting capabilities in CrafterAgent
3. Enhance coordinator's decision-making
4. Test end-to-end scenarios
5. Polish user interaction and responses

### Week 4: Refinement
1. Add comprehensive error handling
2. Implement timeout management
3. Enhance logging and debugging
4. Optimize agent instructions
5. Final testing and documentation

## Success Criteria

1. **Functional Requirements**
   - User can interact solely with CoordinatorAgent
   - Gathering tasks delegated to GathererAgent successfully
   - Crafting tasks delegated to CrafterAgent successfully
   - State properly shared between agents
   - Minecraft actions execute correctly

2. **Technical Requirements**
   - Follows ADK multi-agent patterns
   - No direct user interaction with sub-agents
   - Clean separation of concerns
   - Proper error propagation
   - Maintainable code structure

3. **User Experience**
   - Natural language understanding of requests
   - Clear feedback on task progress
   - Helpful error messages
   - Responsive interaction