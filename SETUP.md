# Setup Guide - Minecraft Multi-Agent System

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- Docker and Docker Compose
- Git

## Quick Setup with UV

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Run the Setup Script

```bash
# Make setup script executable
chmod +x setup_env.sh

# Run setup
./setup_env.sh
```

This will:
- Create a virtual environment with `uv`
- Install all Python dependencies
- Install Node.js dependencies
- Create directories
- Copy .env template

### 3. Configure Environment

Edit the `.env` file:

```bash
# Edit with your preferred editor
nano .env
```

Key settings:
- `MC_SERVER_HOST`: Leave as `localhost` for local Docker
- `MC_BOT_USERNAME`: Choose a name for your bot
- `ADK_API_KEY`: Add when Google ADK is available

### 4. Start Services

```bash
# Start Minecraft server and Redis
docker-compose up -d

# Check services are running
docker-compose ps

# View Minecraft server logs (wait for "Done" message)
docker-compose logs -f minecraft
```

### 5. Activate Virtual Environment

```bash
source .venv/bin/activate
```

### 6. Test the Setup

```bash
# Run the test script
python test_setup.py
```

You should see:
- ✅ Core imports successful
- ✅ External dependencies imported successfully
- ✅ Minecraft server is reachable
- ⚠️ Redis (optional)

### 7. Run the Agent

```bash
# Test connection first
python scripts/run_agent.py test

# Run interactive agent (mock mode for now)
python scripts/run_agent.py agent --interactive
```

## Manual Setup (Alternative)

If the setup script doesn't work:

### 1. Create Virtual Environment

```bash
# Using uv
uv venv
source .venv/bin/activate

# Or using standard Python
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Python dependencies
uv pip install -e ".[dev]"

# Or with standard pip
pip install -e ".[dev]"

# Node.js dependencies
npm install
```

### 3. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Create directories
mkdir -p logs data monitoring/grafana/{dashboards,datasources}
```

## Troubleshooting

### "Module not found" errors

```bash
# Ensure you're in virtual environment
which python  # Should show .venv/bin/python

# Reinstall dependencies
uv pip install -e ".[dev]"
```

### Docker issues

```bash
# Reset Docker containers
docker-compose down -v
docker-compose up -d

# Check Docker daemon is running
docker ps
```

### Node.js/JavaScript errors

```bash
# Clear and reinstall Node modules
rm -rf node_modules package-lock.json
npm install
```

### Permission errors

```bash
# Fix script permissions
chmod +x setup_env.sh scripts/run_agent.py test_setup.py
```

## Requirements

This system requires Google ADK to be installed. Ensure you have:
- A valid Google ADK API key
- Access to the google-adk Python package
- LLM model access (e.g., Gemini 2.0 Flash)

## Next Steps

1. **Test Basic Commands**: Try the interactive mode with simple commands
2. **Explore the Code**: Check `src/agents/simple_agent_mock.py`
3. **Add Features**: Extend the mock agent with more commands
4. **Monitor Logs**: Use `docker-compose logs -f` to debug

## Development Tips

### Running Without Docker

If you can't use Docker, you'll need a Minecraft server:
1. Download Minecraft server from minecraft.net
2. Run with: `java -Xmx2G -jar server.jar nogui`
3. Set `online-mode=false` in server.properties

### Using VS Code

Add to `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.terminal.activateEnvironment": true
}
```

### Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python scripts/run_agent.py agent --interactive
```
