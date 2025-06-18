"""Validate deployment setup before running deployment scripts"""

import os
import sys
from pathlib import Path

try:
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError

    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False


def check_prerequisites():
    """Check if all prerequisites are met"""

    print("Checking deployment prerequisites...")
    print("=" * 50)

    errors = []
    warnings = []

    # Check Python version
    if sys.version_info < (3, 11):
        errors.append(f"Python 3.11+ required, found {sys.version}")
    else:
        print("✓ Python version: " + sys.version.split()[0])

    # Check for .env file
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        errors.append("No .env file found. Copy .env.example and add your API key.")
    else:
        print("✓ .env file found")

        # Check for API key
        has_api_key = False
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("MINECRAFT_AGENT_GOOGLE_AI_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value and value != "your_gemini_api_key_here":
                        has_api_key = True
                    break

        if not has_api_key:
            errors.append("MINECRAFT_AGENT_GOOGLE_AI_API_KEY not set in .env file")
        else:
            print("✓ API key configured in .env")

    # Check Google Cloud authentication
    if HAS_GOOGLE_AUTH:
        try:
            credentials, project = default()
            if project:
                print(f"✓ Google Cloud authenticated (project: {project})")
                os.environ["GOOGLE_CLOUD_PROJECT"] = project
            else:
                warnings.append("Google Cloud project not set. Run: gcloud config set project YOUR_PROJECT_ID")
        except DefaultCredentialsError:
            errors.append("Not authenticated with Google Cloud. Run: gcloud auth application-default login")
    else:
        warnings.append("google-auth not installed. Install with: pip install google-auth")

    # Check for required environment variables
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        warnings.append("GOOGLE_CLOUD_PROJECT not set. Using default from config.py")

    # Check if Docker is installed
    docker_installed = os.system("docker --version > /dev/null 2>&1") == 0
    if docker_installed:
        print("✓ Docker installed")
    else:
        warnings.append("Docker not found. Install Docker to build container images.")

    # Summary
    print("\n" + "=" * 50)

    if errors:
        print("\n❌ ERRORS found (must fix before deploying):")
        for error in errors:
            print(f"   - {error}")

    if warnings:
        print("\n⚠️  WARNINGS (deployment may still work):")
        for warning in warnings:
            print(f"   - {warning}")

    if not errors:
        print("\n✅ All prerequisites met! You can proceed with deployment.")
        print("\nNext steps:")
        print("1. Install deployment dependencies: pip install -r deploy/requirements.txt")
        print("2. Run deployment scripts as documented in deploy/README.md")
    else:
        print("\n❌ Fix the errors above before proceeding with deployment.")
        sys.exit(1)


if __name__ == "__main__":
    check_prerequisites()
