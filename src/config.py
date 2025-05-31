"""
Configuration management for Minecraft Multi-Agent system
"""

import os
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Configuration for Google ADK agents"""

    # Google AI API configuration
    google_ai_api_key: Optional[SecretStr] = Field(default=None, description="Google AI API key for Gemini models")

    # Google Cloud configuration (alternative to API key)
    google_cloud_project: Optional[str] = Field(default=None, description="Google Cloud project ID for Vertex AI")
    google_cloud_location: Optional[str] = Field(
        default="us-central1", description="Google Cloud location for Vertex AI"
    )

    # Agent configuration
    default_model: str = Field(default="gemini-2.0-flash", description="Default LLM model to use")
    agent_temperature: float = Field(default=0.2, description="Temperature for LLM responses (0.0-1.0)")
    max_output_tokens: int = Field(default=500, description="Maximum tokens in agent responses")

    # Minecraft server configuration
    minecraft_host: str = Field(default="localhost", description="Minecraft server host")
    minecraft_port: int = Field(default=25565, description="Minecraft server port")
    bot_username: str = Field(default="MinecraftAgent", description="Bot username in Minecraft")
    minecraft_version: str = Field(default="1.21.1", description="Minecraft version for bot compatibility")

    # Bridge configuration
    command_timeout_ms: int = Field(default=10000, description="Command timeout in milliseconds")
    event_queue_size: int = Field(default=1000, description="Maximum size of event queue")

    # Timeout configuration
    pathfinder_timeout_ms: int = Field(default=30000, description="Timeout for pathfinder movement in milliseconds")
    js_command_timeout_ms: int = Field(default=15000, description="Timeout for JS command execution in milliseconds")

    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    log_file: Optional[str] = Field(default=None, description="Log file path (None for no file logging)")
    log_json_format: bool = Field(default=False, description="Use JSON format for logs")
    google_log_level: str = Field(
        default="WARNING", description="Logging level for Google ADK and other Google libraries"
    )

    class Config:
        env_file = ".env"
        env_prefix = "MINECRAFT_AGENT_"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


def get_config() -> AgentConfig:
    """Get the configuration instance"""
    return AgentConfig()


def setup_google_ai_credentials(config: AgentConfig) -> dict:
    """Setup Google AI credentials based on configuration

    Returns:
        Dictionary with credential configuration for ADK
    """
    credentials = {}

    if config.google_ai_api_key:
        # Use Google AI API with API key
        os.environ["GOOGLE_API_KEY"] = config.google_ai_api_key.get_secret_value()
    elif config.google_cloud_project:
        # Use Google Cloud Vertex AI
        credentials["vertexai"] = True
        credentials["project"] = config.google_cloud_project
        credentials["location"] = config.google_cloud_location
        os.environ["GOOGLE_CLOUD_PROJECT"] = config.google_cloud_project
        os.environ["GOOGLE_CLOUD_LOCATION"] = config.google_cloud_location
    else:
        # Try to get from environment
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "No Google AI credentials found. Set MINECRAFT_AGENT_GOOGLE_AI_API_KEY "
                "or GOOGLE_API_KEY environment variable, or configure Google Cloud credentials."
            )

    return credentials
