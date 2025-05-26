# Minecraft ADK Guild

A multi-agent AI system for Minecraft using Google ADK patterns. The project demonstrates specialized agents that coordinate to accomplish tasks like resource gathering and item crafting.

## 🏗️ Architecture

```
User → main.py → CoordinatorAgent → [GathererAgent, CrafterAgent]
                      ↓                     ↓              ↓
                 session.state         Mineflayer      Mineflayer
                                         tools           tools
```

### Core Components

1. **Agent Layer (Python)**
   - **CoordinatorAgent**: Handles user interaction and task delegation
   - **GathererAgent**: Specialized in resource collection
   - **CrafterAgent**: Specialized in item crafting
   - Uses Google ADK for multi-agent orchestration

2. **Bridge Layer**
   - **BridgeManager**: Python → JavaScript command execution
   - **EventStream**: JavaScript → Python event streaming
   - WebSocket communication on port 8765

3. **Minecraft Layer (JavaScript)**
   - **Mineflayer Bot**: Direct Minecraft server interaction
   - **Pathfinding**: Navigation and movement
   - **Event System**: Real-time world updates

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Minecraft Java Edition server
- Google AI API key (for Gemini)

### Installation

```bash
# Clone repository
git clone https://github.com/your-repo/minecraft-adk-guild.git
cd minecraft-adk-guild

# Install dependencies
npm install
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your API key and server details
```

### Usage

```bash
# Start Minecraft bot
node src/minecraft/bot.js

# In another terminal, run agent commands
python main.py "check inventory"
python main.py "gather 3 oak logs"
python main.py "craft a wooden pickaxe"
```

## 📁 Project Structure

```
src/
├── agents/          # Multi-agent implementations
├── bridge/          # Python-JavaScript communication
├── minecraft/       # Mineflayer bot and events
└── tools/           # ADK tool wrappers for Minecraft
```

## 🔧 Configuration

Environment variables (`.env`):
```bash
MINECRAFT_AGENT_GOOGLE_AI_API_KEY=your_key_here
MINECRAFT_AGENT_MINECRAFT_HOST=localhost
MINECRAFT_AGENT_MINECRAFT_PORT=25565
MINECRAFT_AGENT_BOT_USERNAME=MinecraftAgent
```

## 📖 Documentation

- [CLAUDE.md](CLAUDE.md) - AI assistant guidelines
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [QUICKSTART.md](QUICKSTART.md) - Getting started guide

## 🤝 Contributing

This project prioritizes simplicity and clean architecture. Please ensure any contributions maintain these principles.