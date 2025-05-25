# Multi-Agent Minecraft System

A sophisticated multi-agent system for Minecraft automation using Google ADK, Mineflayer, and JSPyBridge. This project demonstrates how to build intelligent, collaborative agents that can gather resources, construct buildings, and coordinate complex tasks in Minecraft.

## 🎯 Current Status: Phase 1 Complete!

**Phase 1 (Google ADK Integration) has been successfully completed!** The system now features:
- ✅ Full Google ADK integration with Gemini API
- ✅ Real-time command execution with <500ms latency
- ✅ All core ADK patterns implemented (LlmAgent, Sequential, Parallel, Loop)
- ✅ Comprehensive test coverage and production-ready code

See [Phase 1 Completion Report](docs/PHASE1_COMPLETE.md) for detailed achievements.

## 🏗️ Architecture Overview

![Multi-Agent Architecture](docs/diagrams/minecraft_multiagent_architecture.png)

The system consists of three main layers connected through JSPyBridge:

### 1. **ADK Layer (Python)** - Intelligence & Coordination
- **Coordinator Agent**: Orchestrates tasks and monitors progress
- **Resource Gatherer**: Autonomously finds and collects materials
- **Builder Agent**: Constructs structures from blueprints
- Utilizes Google ADK's LLM agents, session management, and tool system

### 2. **Bridge Layer** - Seamless Communication
- **JSPyBridge**: Enables Python agents to control JavaScript bots
- **Command Queue**: Manages action sequencing and prioritization
- **State Synchronizer**: Maintains consistent world model across languages

### 3. **Mineflayer Layer (JavaScript)** - Game Interaction
- Direct Minecraft protocol implementation
- Pathfinding, physics, and inventory management
- Real-time event handling and world updates

## 🔄 Data Flow

![Data Flow Diagram](docs/diagrams/data_flow_diagram.png)

The diagram above illustrates how data flows through the system:
1. **User requests** are processed by the Coordinator Agent
2. **Commands flow** from Python agents through JSPyBridge to Mineflayer
3. **Game events** stream back through the bridge to update agent state
4. **State persistence** ensures continuity across sessions

## 🚀 Key Features

- **Multi-Agent Coordination**: Agents work together on complex tasks
- **Intelligent Decision Making**: LLM-powered agents adapt to situations
- **Fault Tolerance**: Automatic recovery from failures and disconnections
- **Scalable Architecture**: Easy to add new agents and capabilities
- **Real-time Monitoring**: Dashboard for agent status and performance

## 📋 Project Plan Summary

### Development Phases

#### Phase 1: Infrastructure Foundation (Week 1)
- Core bridge setup and communication protocol
- Single agent prototype with basic movements
- Development environment and monitoring

#### Phase 2: Multi-Agent Coordination (Week 2)
- Implement all three agent types
- Inter-agent communication and shared state
- World model and resource tracking

#### Phase 3: Complex Behaviors (Week 3)
- Advanced coordination patterns
- Error recovery and checkpointing
- Performance optimization

### POC Success Criteria

✅ **Resource Gathering**: Agent collects 64 wood blocks autonomously
✅ **Construction**: Builder creates 5x5x3 shelter from blueprint
✅ **Coordination**: Agents delegate tasks and share resources
✅ **Recovery**: System handles failures gracefully

## 🛠️ Technical Stack

- **Google ADK**: Agent orchestration and LLM integration
- **Mineflayer**: Minecraft bot framework (JavaScript)
- **JSPyBridge**: Python-JavaScript interoperability
- **Redis/SQLite**: Shared state and persistence
- **Docker**: Development environment

## 🔧 Risk Mitigation

### 1. Bridge Latency
- **Solution**: Command batching and predictive execution
- **Target**: <100ms p95 latency

### 2. State Synchronization
- **Solution**: Event sourcing and optimistic locking
- **Target**: Zero state conflicts

### 3. Session Management
- **Solution**: External state storage and rotation
- **Target**: 24+ hour continuous operation

## 🚦 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Minecraft Java Edition server
- Google Gemini API key (get one at [Google AI Studio](https://aistudio.google.com/app/apikey))

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/minecraft-adk-guild.git
   cd minecraft-adk-guild
   ```

2. **Install dependencies**
   ```bash
   # Python dependencies
   pip install -e .
   
   # JavaScript dependencies
   npm install
   ```

3. **Configure Google ADK**
   ```bash
   cp .env.example .env
   # Edit .env and add your MINECRAFT_AGENT_GOOGLE_AI_API_KEY
   ```

4. **Start Minecraft server**
   - Launch Minecraft Java Edition server on `localhost:25565`
   - Ensure server is in offline mode for bot connections

5. **Run the agent**
   ```bash
   # Interactive mode
   python scripts/run_agent.py agent --interactive
   
   # Demo mode
   python scripts/run_agent.py agent --demo
   ```

### Testing

Run the comprehensive test suite:
```bash
# All tests
pytest tests/

# ADK integration tests only
pytest tests/test_adk_integration.py -v

# With coverage
pytest --cov=src tests/
```

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/minecraft-multiagent

# Install Python dependencies
pip install google-adk javascript

# Install Node.js dependencies
npm install mineflayer pythonia mineflayer-pathfinder

# Start Minecraft server
docker-compose up minecraft-server
```

### Quick Start
```python
# Example: Simple resource gathering
from minecraft_agents import ResourceGatherer

gatherer = ResourceGatherer()
await gatherer.collect_wood(amount=64)
```

### Running Tests

```bash
# All tests
pytest tests/

# E2E tests for inventory query
python test_inventory_flow_demo.py      # Demo without server
python run_inventory_e2e_test.py        # Full E2E with server
pytest tests/test_check_inventory_e2e.py -v  # Unit test version
```

## 📊 Monitoring

The system includes a real-time dashboard showing:
- Agent status and current tasks
- Resource inventory
- Performance metrics
- Command history

## 🔮 Future Enhancements

- **Combat Agent**: Defend against threats
- **Farming Agent**: Automated food production
- **Trading Agent**: Economic interactions
- **Voice Control**: Natural language commands
- **Multi-server**: Coordinate across servers

## 📚 Documentation

- [Detailed Project Plan](PROJECT_PLAN.md)
- [API Reference](docs/api.md)
- [Agent Development Guide](docs/agents.md)
- [Troubleshooting](docs/troubleshooting.md)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Google ADK team for the agent framework
- PrismarineJS for Mineflayer
- extremeheat for JSPyBridge

---

Built with ❤️ for the Minecraft automation community
