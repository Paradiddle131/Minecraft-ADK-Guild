"""Deploy bot to Google Agent Engine"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

import vertexai
from google.cloud import compute_v1, secretmanager
from vertexai import agent_engines

from src.agents.coordinator_agent.agent import create_coordinator_agent

from .config import (
    AGENT_ENGINE_NAME,
    API_KEY_SECRET_NAME,
    INSTANCE_NAME,
    MODEL_NAME,
    PROJECT_ID,
    REGION,
    STAGING_BUCKET,
    ZONE,
)


def get_minecraft_server_ip() -> str:
    """Get the internal IP of the Minecraft server"""

    instances_client = compute_v1.InstancesClient()

    try:
        instance = instances_client.get(project=PROJECT_ID, zone=ZONE, instance=INSTANCE_NAME)
        internal_ip = instance.network_interfaces[0].network_i_p
        print(f"✓ Found Minecraft server internal IP: {internal_ip}")
        return internal_ip
    except Exception as e:
        print(f"✗ Error getting Minecraft server IP: {e}")
        print("  Make sure the Minecraft server is deployed first!")
        sys.exit(1)


def get_api_key_from_secret() -> str:
    """Retrieve API key from Secret Manager"""

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{API_KEY_SECRET_NAME}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": name})
        api_key = response.payload.data.decode("UTF-8")
        print("✓ Retrieved API key from Secret Manager")
        return api_key
    except Exception as e:
        print(f"✗ Error retrieving API key: {e}")
        print("  Make sure you've run setup_secrets.py first!")
        sys.exit(1)


def deploy_to_agent_engine():
    """Deploy the coordinator agent to Agent Engine"""

    print("Deploying bot to Agent Engine")
    print(f"Project: {PROJECT_ID}")
    print(f"Region: {REGION}")
    print("=" * 50)

    # Initialize Vertex AI
    vertexai.init(
        project=PROJECT_ID,
        location=REGION,
        staging_bucket=STAGING_BUCKET,
    )

    # Get Minecraft server IP
    minecraft_ip = get_minecraft_server_ip()

    # Get API key
    api_key = get_api_key_from_secret()

    # Set environment variables for the agent
    os.environ["MINECRAFT_AGENT_GOOGLE_AI_API_KEY"] = api_key
    os.environ["MINECRAFT_AGENT_MINECRAFT_HOST"] = minecraft_ip
    os.environ["MINECRAFT_AGENT_MINECRAFT_PORT"] = "25565"
    os.environ["MINECRAFT_AGENT_DEFAULT_MODEL"] = MODEL_NAME

    print("\nCreating coordinator agent...")

    # Create the coordinator agent
    coordinator = create_coordinator_agent()

    print("✓ Coordinator agent created")
    print("\nDeploying to Agent Engine...")
    print("This may take 5-10 minutes...")

    try:
        # Deploy to Agent Engine
        remote_app = agent_engines.create(
            agent_engine=coordinator,
            requirements=[
                "google-cloud-aiplatform[adk,agent_engines]",
                "google-genai",
                "google-cloud-secret-manager",
                "websockets",
                "asyncio",
                "python-dotenv",
                "pydantic",
                "tenacity",
            ],
            display_name=AGENT_ENGINE_NAME,
            description="Minecraft ADK Guild bot system",
        )

        print("\n✓ Agent deployed successfully!")
        print(f"  Resource name: {remote_app.resource_name}")
        print(f"  Agent Engine ID: {remote_app.agent_id}")

        # Test the deployment
        print("\nTesting deployment...")
        test_session = remote_app.create_session(user_id="test_user")
        print(f"✓ Test session created: {test_session['id']}")

        print("\n" + "=" * 50)
        print("Deployment complete!")
        print("\nYour bot is now running on Agent Engine and will connect to")
        print(f"the Minecraft server at {minecraft_ip}:25565")
        print("\nNext step:")
        print("Add monitoring: python deploy/setup_monitoring.py")

    except Exception as e:
        print(f"\n✗ Error deploying to Agent Engine: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have the necessary permissions")
        print("2. Check that all APIs are enabled")
        print("3. Verify the staging bucket exists or will be created")
        raise


def main():
    """Main deployment function"""
    deploy_to_agent_engine()


if __name__ == "__main__":
    main()
