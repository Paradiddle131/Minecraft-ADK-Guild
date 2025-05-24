"""
Tests for bridge functionality
"""
from unittest.mock import AsyncMock, patch

import pytest

from src.bridge import BridgeConfig, BridgeManager


@pytest.mark.asyncio
async def test_bridge_initialization():
    """Test bridge initialization"""
    config = BridgeConfig()
    bridge = BridgeManager(config)

    # Mock the JavaScript module loading
    with patch("src.bridge.bridge_manager.require") as mock_require:
        mock_bot_module = AsyncMock()
        mock_bot_instance = AsyncMock()
        mock_bot_instance.bot = AsyncMock()
        mock_bot_instance.eventClient = AsyncMock()
        mock_bot_module.startBot.return_value = mock_bot_instance
        mock_require.return_value = mock_bot_module

        await bridge.initialize()

        assert bridge.is_connected
        assert bridge.bot is not None


@pytest.mark.asyncio
async def test_bridge_command_execution():
    """Test command execution through bridge"""
    config = BridgeConfig()
    bridge = BridgeManager(config)

    # Mock the bot
    bridge.bot = AsyncMock()
    bridge.is_connected = True

    result = await bridge.execute_command("move_to", x=100, y=65, z=200)

    # Should queue command and return result
    assert result is not None


def test_bridge_config():
    """Test bridge configuration"""
    config = BridgeConfig(command_timeout=5000, batch_size=10, max_retries=3)

    assert config.command_timeout == 5000
    assert config.batch_size == 10
    assert config.max_retries == 3
