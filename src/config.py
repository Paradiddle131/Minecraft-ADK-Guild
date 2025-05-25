"""
Configuration management for Minecraft multi-agent system
"""
import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration using pydantic-settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Minecraft Server Configuration
    mc_server_host: str = "localhost"
    mc_server_port: int = 25565
    mc_bot_username: str = "MinecraftAgent"
    mc_bot_auth: str = "offline"
    
    # ADK Configuration
    adk_model: str = "gemini-2.0-flash"
    adk_api_key: Optional[str] = None
    google_api_key: Optional[str] = None  # Alternative env var name
    adk_session_timeout: int = 3600
    
    # Bridge Configuration
    jspy_command_timeout: int = 5000
    jspy_batch_size: int = 10
    bridge_port: int = 8765
    
    # Redis Configuration (optional)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_enabled: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Monitoring
    prometheus_port: int = 9090
    enable_monitoring: bool = True
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from either ADK_API_KEY or GOOGLE_API_KEY"""
        return self.adk_api_key or self.google_api_key or os.getenv("GOOGLE_API_KEY")
    
    def validate_api_key(self) -> bool:
        """Check if API key is configured"""
        return bool(self.api_key)


# Global config instance
config = Config()