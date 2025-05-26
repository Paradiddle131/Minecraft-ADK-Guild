# Cleanup Plan for Minecraft ADK Guild

## Overview

This plan details the systematic removal of overengineered components and redundant code from the codebase, preparing it for the new agent implementation. The cleanup prioritizes simplicity while retaining essential functionality for Minecraft bot operations.

## Analysis of Current Codebase

### Components to KEEP

1. **Core Bridge Infrastructure**
   - `src/bridge/bridge_manager.py` - Essential for Python→JS communication
   - `src/bridge/event_stream.py` - Simple WebSocket server for JS→Python events
   - `src/minecraft/bot.js` - Mineflayer bot implementation
   - `src/minecraft/event_client.js` - WebSocket client for events
   - `src/minecraft/MinecraftEventEmitter.js` - Standardized event emission

2. **Essential Tools**
   - `src/tools/mineflayer_tools.py` - Core Minecraft operations
   - Tool functions: move_to, dig_block, place_block, find_blocks, get_inventory, etc.

3. **Configuration**
   - `src/config.py` - Environment variable management
   - `.env.example` - Configuration template

4. **Project Structure**
   - `pyproject.toml` - Python dependencies
   - `package.json` - JavaScript dependencies
   - Essential documentation: `README.md`, `SETUP.md`, `QUICKSTART.md`

### Components to REMOVE

1. **Entire Event Bridge Module** (`src/bridge/event_bridge/`)
   - `bridge_connector.py` - Unused orchestrator
   - `event_registry.py` - Overengineered event registration
   - `adk_adapter.py` - Unnecessary abstraction
   - `event_queue.py` - Complex priority queuing
   - `event_handlers.py` - Decorator-based complexity
   - `event_logger.py` - Excessive logging
   - `payload_schemas.py` - Over-specified validation
   - `event_filters.py` - Unnecessary filtering
   - `state_sync.py` - Complex state synchronization
   - `compression.py` - Premature optimization
   - `circuit_breaker.py` - Overengineered resilience
   - `connection_recovery.py` - Complex recovery logic
   - `metrics.py` - Unnecessary metrics collection
   - `tracing.py` - Excessive tracing
   - `profiling.py` - Premature performance profiling

2. **Current Agent Implementations**
   - `src/agents/simple_agent.py` - To be replaced
   - `src/agents/enhanced_agent.py` - To be replaced
   - `src/agents/workflow_agents.py` - If exists

3. **All Test Files**
   - `tests/` directory - Entire directory
   - `test_*.py` files in root - All test files
   - `run_*_e2e_test.py` - E2E test runners
   - `src/tests/` - Test infrastructure

4. **Redundant Documentation**
   - Planning documents (already removed from git)
   - Test-related documentation
   - Implementation status files

5. **Unused Scripts**
   - `benchmark_performance.py` - Performance testing
   - `debug_*.py` - Debug scripts
   - `verify_implementation.py` - Validation scripts
   - `validate_implementations.py` - Test validation

## Cleanup Phases

## Phase 1: Remove Test Infrastructure

### Goals
- Remove all testing code and infrastructure
- Clean up test-related documentation

### Section 1.1: Test File Removal

#### Chunk 1.1.1: Remove Test Directories
```bash
rm -rf tests/
rm -rf src/tests/
```

#### Chunk 1.1.2: Remove Root Test Files
```bash
rm test_*.py
rm run_*_e2e_test.py
rm pytest.ini
```

#### Chunk 1.1.3: Remove Test Scripts
```bash
rm benchmark_performance.py
rm debug_*.py
rm verify_implementation.py
rm validate_implementations.py
rm run_tests.py
rm test_setup.py
```

## Phase 2: Remove Event Bridge Complexity

### Goals
- Remove the entire overengineered event bridge module
- Retain simple WebSocket communication

### Section 2.1: Event Bridge Removal

#### Chunk 2.1.1: Remove Event Bridge Module
```bash
rm -rf src/bridge/event_bridge/
```

#### Chunk 2.1.2: Update Bridge Imports

**File:** `src/bridge/__init__.py`
**Updates:** Remove event_bridge imports, keep only bridge_manager and event_stream

## Phase 3: Remove Current Agent Implementations

### Goals
- Remove existing agent code to make way for new implementation
- Clean up agent-related imports

### Section 3.1: Agent Removal

#### Chunk 3.1.1: Remove Agent Files
```bash
rm src/agents/simple_agent.py
rm src/agents/enhanced_agent.py
rm src/agents/workflow_agents.py
```

#### Chunk 3.1.2: Clean Agent Directory

**File:** `src/agents/__init__.py`
**Updates:** Clear all exports, prepare for new agents

## Phase 4: Simplify Dependencies

### Goals
- Remove unnecessary dependencies from project files
- Clean up imports in remaining code

### Section 4.1: Dependency Cleanup

#### Chunk 4.1.1: Update Python Dependencies

**File:** `pyproject.toml`
**Updates:** Remove testing dependencies (pytest, pytest-asyncio, etc.)

#### Chunk 4.1.2: Clean Unused Imports

Review and clean imports in:
- `src/config.py`
- `src/bridge/bridge_manager.py`
- `src/bridge/event_stream.py`
- `src/tools/mineflayer_tools.py`

## Phase 5: Documentation Cleanup

### Goals
- Remove redundant documentation
- Update remaining docs to reflect simplified architecture

### Section 5.1: Documentation Updates

#### Chunk 5.1.1: Update README

**File:** `README.md`
**Updates:** Remove references to removed components, focus on core functionality

#### Chunk 5.1.2: Update CLAUDE.md

**File:** `CLAUDE.md`
**Updates:** Reflect new agent architecture, remove old patterns

## Phase 6: Final Cleanup

### Goals
- Remove temporary files and caches
- Ensure clean directory structure

### Section 6.1: Directory Cleanup

#### Chunk 6.1.1: Remove Build Artifacts
```bash
rm -rf __pycache__/
rm -rf *.egg-info/
rm -rf .pytest_cache/
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete
```

#### Chunk 6.1.2: Remove Temporary Files
```bash
rm -f *.md.bak
rm -f .coverage
rm -rf htmlcov/
rm -rf test_results/
```

## Verification Steps

### After Each Phase
1. Ensure core functionality still works:
   - Bridge connection establishes
   - Bot can connect to Minecraft
   - Basic commands execute

2. Check for broken imports:
   ```bash
   python -m py_compile src/**/*.py
   ```

3. Verify minimal dependencies:
   - No test frameworks
   - No monitoring/metrics libraries
   - Only essential ADK and bridge dependencies

## Expected Result

### Final Structure
```
src/
├── agents/           # New agents (to be added)
│   └── __init__.py
├── bridge/
│   ├── __init__.py
│   ├── bridge_manager.py
│   └── event_stream.py
├── minecraft/
│   ├── bot.js
│   ├── event_client.js
│   ├── index.js
│   └── MinecraftEventEmitter.js
├── tools/
│   ├── __init__.py
│   └── mineflayer_tools.py
├── utils/            # If needed
│   └── state_manager.py
├── __init__.py
└── config.py
```

### Removed Components Summary
- **Lines of Code Removed**: ~3000+ (event bridge module alone)
- **Files Removed**: ~40+
- **Dependencies Removed**: All testing frameworks, monitoring tools
- **Complexity Reduction**: 80% reduction in bridge layer complexity

## Risk Mitigation

1. **Backup Current State**: Ensure git commit before starting
2. **Incremental Removal**: Test after each phase
3. **Core Functionality Tests**: Manual verification of bot operations
4. **Import Verification**: Check all remaining imports work

## Execution Timeline

### Day 1: Test Removal (Phase 1)
- Remove all test infrastructure
- Verify core functionality remains

### Day 2: Event Bridge Removal (Phase 2)
- Remove event_bridge module
- Test WebSocket communication still works

### Day 3: Agent Cleanup (Phase 3)
- Remove old agent implementations
- Prepare for new agents

### Day 4: Final Cleanup (Phases 4-6)
- Clean dependencies
- Update documentation
- Final verification

## Success Metrics

1. **Code Reduction**: 60%+ reduction in codebase size
2. **Dependency Reduction**: Remove 10+ unnecessary packages
3. **Complexity**: Single-responsibility modules only
4. **Maintainability**: Clear, simple architecture
5. **Functionality**: All core Minecraft operations still work