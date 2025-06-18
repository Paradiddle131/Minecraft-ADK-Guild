# GCP Deployment Guide

This directory contains scripts to deploy the Minecraft ADK Guild bot system to Google Cloud Platform.

## Prerequisites

1. Google Cloud SDK installed and configured
2. A GCP project with billing enabled
3. Appropriate permissions (Owner or Editor role recommended for initial setup)
4. Python 3.11+ installed
5. A valid Google AI API key (get one from https://aistudio.google.com/app/apikey)

## Quick Start

1. **Install deployment dependencies:**
   ```bash
   pip install -r deploy/requirements.txt
   ```

2. **Set up your environment:**
   ```bash
   # Set your GCP project ID
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   
   # Copy and update .env file with your API key
   cp .env.example .env
   # Edit .env and add your MINECRAFT_AGENT_GOOGLE_AI_API_KEY
   ```

3. **Run deployment scripts in order:**
   ```bash
   # Enable APIs and create basic resources
   python deploy/setup_project.py
   
   # Deploy Minecraft server
   python deploy/deploy_minecraft.py
   
   # Set up secrets
   python deploy/setup_secrets.py
   
   # Deploy bot to Agent Engine
   python deploy/deploy_agent.py
   
   # Set up monitoring
   python deploy/setup_monitoring.py
   ```

## What Gets Deployed

- **Minecraft Server**: Runs on Compute Engine (e2-medium instance)
  - Static IP for external access
  - Docker-based deployment
  - Automatic startup on VM boot

- **Bot System**: Runs on Agent Engine
  - Automatically scales based on usage
  - Connects to Minecraft server via internal IP
  - Managed by Google's AI infrastructure

- **Monitoring**: Basic uptime checks
  - Monitors Minecraft server availability
  - Logs automatically collected

## Connecting to the Server

After deployment, the script will show you the external IP address. Connect your Minecraft client to:
```
<EXTERNAL_IP>:25565
```

## CI/CD

Push to the main branch to trigger automatic builds:
```bash
git push origin main
```

The Cloud Build configuration will:
1. Build the Docker image
2. Push to Container Registry
3. Tag as latest

Note: Full automated deployment to Agent Engine requires additional setup.

## Costs

Estimated monthly costs for this MVP:
- Compute Engine (e2-medium): ~$30
- Static IP: ~$7
- Agent Engine: Pay-per-use (minimal for testing)
- Total: ~$40-50/month

## Cleanup

To avoid charges, delete resources when done:
```bash
# Delete Compute Engine instance
gcloud compute instances delete minecraft-server --zone=us-central1-a

# Release static IP
gcloud compute addresses delete minecraft-server-ip --global

# Delete Agent Engine deployment (manual process in Cloud Console)
```