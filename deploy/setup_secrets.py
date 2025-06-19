"""Set up secrets in Google Secret Manager"""

from pathlib import Path

from google.api_core import exceptions
from google.cloud import secretmanager

from .config import API_KEY_SECRET_NAME, PROJECT_ID


def create_secret(project_id: str, secret_id: str) -> None:
    """Create a secret in Secret Manager"""

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"

    # Check if secret already exists
    secret_name = f"{parent}/secrets/{secret_id}"
    try:
        client.get_secret(request={"name": secret_name})
        print(f"✓ Secret '{secret_id}' already exists")
        return
    except exceptions.NotFound:
        pass

    # Create the secret
    try:
        secret = secretmanager.Secret(
            replication=secretmanager.Replication(
                automatic=secretmanager.Replication.Automatic(),
            ),
        )

        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": secret,
            }
        )
        print(f"✓ Secret '{secret_id}' created")
    except Exception as e:
        print(f"✗ Error creating secret: {e}")
        raise


def add_secret_version(project_id: str, secret_id: str, secret_value: str) -> None:
    """Add a version to an existing secret"""

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}/secrets/{secret_id}"

    try:
        # Add the secret version
        client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": secret_value.encode("UTF-8")},
            }
        )
        print(f"✓ Secret version added to '{secret_id}'")
    except Exception as e:
        print(f"✗ Error adding secret version: {e}")
        raise


def main():
    """Main setup function"""
    print(f"Setting up secrets for project: {PROJECT_ID}")
    print("=" * 50)

    # Check for .env file
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print("\n⚠️  No .env file found!")
        print("Please create a .env file with your MINECRAFT_AGENT_GOOGLE_AI_API_KEY")
        print("You can copy from .env.example")
        return

    # Read API key from .env
    api_key = None
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("MINECRAFT_AGENT_GOOGLE_AI_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n⚠️  Valid API key not found in .env!")
        print("Please update your .env file with a real Google AI API key")
        return

    # Create secret
    create_secret(PROJECT_ID, API_KEY_SECRET_NAME)

    # Add secret version
    add_secret_version(PROJECT_ID, API_KEY_SECRET_NAME, api_key)

    print("\n" + "=" * 50)
    print("Secrets setup complete!")
    print(f"\nAPI key stored in Secret Manager as: {API_KEY_SECRET_NAME}")
    print("\nNext step:")
    print("Deploy bot to Agent Engine: python deploy/deploy_agent.py")


if __name__ == "__main__":
    main()
