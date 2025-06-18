"""GCP deployment configuration constants"""

import os

# GCP Project Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "minecraft-adk-guild")
REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
ZONE = os.environ.get("GOOGLE_CLOUD_ZONE", "us-central1-a")

# Resource Names
INSTANCE_NAME = "minecraft-server"
AGENT_ENGINE_NAME = "minecraft-bot-agent"
STATIC_IP_NAME = "minecraft-server-ip"
FIREWALL_RULE_NAME = "allow-minecraft"

# Minecraft Configuration
MINECRAFT_PORT = 25565
MACHINE_TYPE = "e2-medium"

# Agent Engine Configuration
STAGING_BUCKET = f"gs://{PROJECT_ID}-agent-staging"
MODEL_NAME = "gemini-2.0-flash"

# Secret Names
API_KEY_SECRET_NAME = "google-ai-api-key"
