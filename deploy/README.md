# GCP Deployment Guide

This directory contains scripts to deploy the Minecraft ADK Guild bot system to Google Cloud Platform using the latest 2024 Google Cloud Python SDK libraries.

## Prerequisites

1. Google Cloud SDK installed and configured
2. A GCP project with billing enabled
3. Appropriate permissions (Owner or Editor role recommended for initial setup)
4. Python 3.11+ installed
5. A valid Google AI API key (get one from https://aistudio.google.com/app/apikey)

## Quick Start

1. **Install deployment dependencies:**
   ```bash
   # Install latest GCP SDK libraries (2024)
   pip install -e ".[deploy]"
   # OR alternatively:
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
   python -m deploy.setup_project
   
   # Deploy Minecraft server
   python -m deploy.deploy_minecraft
   
   # Set up secrets
   python -m deploy.setup_secrets
   
   # Deploy bot to Agent Engine
   python -m deploy.deploy_agent
   
   # Set up monitoring
   python -m deploy.setup_monitoring
   ```

   > **Note**: Scripts must be run as Python modules (using `-m`) to support proper relative imports and IDE navigation. Running them directly (e.g., `python deploy/setup_project.py`) will result in import errors.

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

## Troubleshooting

### Import Errors
If you encounter `ImportError: attempted relative import with no known parent package`:
- Make sure you're running scripts as modules: `python -m deploy.script_name`
- Ensure you're in the project root directory when running commands
- Do not run scripts directly (e.g., `python deploy/setup_project.py`)

### Authentication Issues
```bash
# Re-authenticate if needed
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Cleanup

To avoid charges, delete resources when done:
```bash
# Delete Compute Engine instance
gcloud compute instances delete minecraft-server --zone=us-central1-a

# Release static IP
gcloud compute addresses delete minecraft-server-ip --global

# Delete Agent Engine deployment (manual process in Cloud Console)
```