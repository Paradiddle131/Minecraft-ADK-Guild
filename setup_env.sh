#!/bin/bash
# Setup script for Minecraft Multi-Agent System

set -e  # Exit on error

echo "🚀 Setting up Minecraft Multi-Agent System..."

# Check for required tools
echo "📋 Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo "❌ Python $PYTHON_VERSION is too old. Please install Python 3.11 or higher."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker is not installed. You'll need it to run the Minecraft server."
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create Python virtual environment with uv
echo "🐍 Creating Python virtual environment..."
uv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install Python dependencies
echo "📚 Installing Python dependencies..."
uv pip install -e ".[dev]"

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "🔐 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys and settings"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x scripts/run_agent.py

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run pre-commit install

echo "✅ Setup complete!"
echo ""
echo "📖 Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Start Docker services: docker-compose up -d"
echo "3. Test connection: python scripts/run_agent.py test"
echo "4. Run agent: python scripts/run_agent.py agent --interactive"
echo ""
echo "💡 Tip: Source the virtual environment before running:"
echo "   source .venv/bin/activate"
