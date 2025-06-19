"""Set up GCP project with required APIs and basic resources"""

from typing import List

from google.api_core import exceptions
from google.cloud import compute_v1, service_usage_v1

from .config import (
    FIREWALL_RULE_NAME,
    MINECRAFT_PORT,
    PROJECT_ID,
    STATIC_IP_NAME,
)


class GCPSetup:
    """Handle GCP project setup and resource creation"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.compute_client = compute_v1.FirewallsClient()
        self.addresses_client = compute_v1.GlobalAddressesClient()
        self.service_usage_client = service_usage_v1.ServiceUsageClient()

    def enable_apis(self, apis: List[str]) -> None:
        """Enable required GCP APIs using Service Usage API"""
        print("Enabling required APIs...")

        for api in apis:
            service_name = f"projects/{self.project_id}/services/{api}"

            try:
                # Check if already enabled
                request = service_usage_v1.GetServiceRequest(name=service_name)
                service = self.service_usage_client.get_service(request=request)
                if service.state == service_usage_v1.State.ENABLED:
                    print(f"✓ {api} already enabled")
                    continue
            except exceptions.NotFound:
                pass

            try:
                # Enable the service
                request = service_usage_v1.EnableServiceRequest(name=service_name)
                self.service_usage_client.enable_service(request=request)
                print(f"  Enabling {api}...")
                # Note: In production, you'd want to wait for the operation to complete
                print(f"✓ {api} enablement initiated")
            except Exception as e:
                print(f"✗ Error enabling {api}: {e}")

    def create_firewall_rule(self) -> None:
        """Create firewall rule for Minecraft server"""
        print(f"\nCreating firewall rule for port {MINECRAFT_PORT}...")

        firewall_rule = compute_v1.Firewall(
            name=FIREWALL_RULE_NAME,
            allowed=[compute_v1.Allowed(I_p_protocol="tcp", ports=[str(MINECRAFT_PORT)])],
            source_ranges=["0.0.0.0/0"],
            direction="INGRESS",
            priority=1000,
            target_tags=["minecraft-server"],
            description="Allow Minecraft server traffic",
        )

        try:
            # Check if rule already exists
            self.compute_client.get(project=self.project_id, firewall=FIREWALL_RULE_NAME)
            print(f"✓ Firewall rule '{FIREWALL_RULE_NAME}' already exists")
        except exceptions.NotFound:
            # Create the rule
            try:
                self.compute_client.insert(project=self.project_id, firewall_resource=firewall_rule)
                print(f"✓ Firewall rule '{FIREWALL_RULE_NAME}' created")
            except Exception as e:
                print(f"✗ Error creating firewall rule: {e}")

    def create_static_ip(self) -> str:
        """Reserve a static external IP address"""
        print("\nReserving static IP address...")

        address = compute_v1.Address(name=STATIC_IP_NAME, description="Static IP for Minecraft server")

        try:
            # Check if already exists
            existing = self.addresses_client.get(project=self.project_id, address=STATIC_IP_NAME)
            print(f"✓ Static IP '{STATIC_IP_NAME}' already reserved: {existing.address}")
            return existing.address
        except exceptions.NotFound:
            # Create new static IP
            try:
                self.addresses_client.insert(project=self.project_id, address_resource=address)
                # In production, wait for operation to complete
                print(f"✓ Static IP '{STATIC_IP_NAME}' reservation initiated")
                print("  Run this script again in a minute to see the assigned IP")
                return ""
            except Exception as e:
                print(f"✗ Error creating static IP: {e}")
                return ""


def main():
    """Main setup function"""
    print(f"Setting up GCP project: {PROJECT_ID}")
    print("=" * 50)

    setup = GCPSetup(PROJECT_ID)

    # Define required APIs
    required_apis = [
        "compute.googleapis.com",  # Compute Engine
        "aiplatform.googleapis.com",  # Vertex AI / Agent Engine
        "secretmanager.googleapis.com",  # Secret Manager
        "cloudbuild.googleapis.com",  # Cloud Build for CI/CD
        "monitoring.googleapis.com",  # Cloud Monitoring
        "logging.googleapis.com",  # Cloud Logging
    ]

    # Enable APIs
    setup.enable_apis(required_apis)

    # Create firewall rule
    setup.create_firewall_rule()

    # Reserve static IP
    static_ip = setup.create_static_ip()

    print("\n" + "=" * 50)
    print("Setup complete!")

    if static_ip:
        print(f"\nMinecraft server will be accessible at: {static_ip}:{MINECRAFT_PORT}")
        print("Update your local Minecraft client to connect to this IP")

    print("\nNext steps:")
    print("1. Create Docker container: python deploy/setup_docker.py")
    print("2. Deploy Minecraft server: python deploy/deploy_minecraft.py")


if __name__ == "__main__":
    main()
