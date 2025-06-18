"""Deploy Minecraft server to Google Compute Engine"""

import time
from pathlib import Path

from google.api_core import exceptions
from google.cloud import compute_v1

from config import (
    INSTANCE_NAME,
    MACHINE_TYPE,
    PROJECT_ID,
    STATIC_IP_NAME,
    ZONE,
)


def create_instance(project_id: str, zone: str, instance_name: str, static_ip: str) -> None:
    """Create a Compute Engine instance for Minecraft server"""

    instances_client = compute_v1.InstancesClient()

    # Check if instance already exists
    try:
        existing = instances_client.get(project=project_id, zone=zone, instance=instance_name)
        print(f"✓ Instance '{instance_name}' already exists")
        print(f"  External IP: {existing.network_interfaces[0].access_configs[0].nat_i_p}")
        return
    except exceptions.NotFound:
        pass

    print(f"Creating Compute Engine instance '{instance_name}'...")

    # Read startup script
    startup_script_path = Path(__file__).parent / "startup-script.sh"
    with open(startup_script_path, "r") as f:
        startup_script = f.read()

    # Define instance configuration
    instance = compute_v1.Instance(
        name=instance_name,
        machine_type=f"zones/{zone}/machineTypes/{MACHINE_TYPE}",
        disks=[
            compute_v1.AttachedDisk(
                auto_delete=True,
                boot=True,
                initialize_params=compute_v1.AttachedDiskInitializeParams(
                    disk_size_gb=50,
                    source_image="projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts",
                ),
            ),
        ],
        network_interfaces=[
            compute_v1.NetworkInterface(
                access_configs=[
                    compute_v1.AccessConfig(
                        name="External NAT",
                        nat_i_p=static_ip if static_ip else None,
                        type_="ONE_TO_ONE_NAT",
                    ),
                ],
            ),
        ],
        metadata=compute_v1.Metadata(
            items=[
                compute_v1.Items(
                    key="startup-script",
                    value=startup_script,
                ),
            ],
        ),
        tags=compute_v1.Tags(items=["minecraft-server"]),
        description="Minecraft server for ADK bot testing",
    )

    # Create the instance
    try:
        instances_client.insert(
            project=project_id,
            zone=zone,
            instance_resource=instance,
        )
        print("✓ Instance creation initiated")
        print("  This may take a few minutes...")

        # Wait for operation to complete (simplified wait)
        time.sleep(30)

        # Get instance details
        created_instance = instances_client.get(project=project_id, zone=zone, instance=instance_name)
        external_ip = created_instance.network_interfaces[0].access_configs[0].nat_i_p
        internal_ip = created_instance.network_interfaces[0].network_i_p

        print(f"\n✓ Instance '{instance_name}' created successfully!")
        print(f"  External IP: {external_ip}")
        print(f"  Internal IP: {internal_ip}")
        print(f"\nMinecraft server will be available at: {external_ip}:25565")
        print("Note: It may take 2-3 minutes for the server to fully start")

    except Exception as e:
        print(f"✗ Error creating instance: {e}")
        raise


def assign_static_ip(project_id: str, zone: str, instance_name: str) -> str:
    """Get the static IP address for assignment"""

    addresses_client = compute_v1.GlobalAddressesClient()

    try:
        address = addresses_client.get(project=project_id, address=STATIC_IP_NAME)
        if address.address:
            print(f"Using static IP: {address.address}")
            return address.address
        else:
            print("Static IP reserved but not yet assigned, using ephemeral IP")
            return ""
    except exceptions.NotFound:
        print("No static IP found, using ephemeral IP")
        return ""


def main():
    """Main deployment function"""
    print("Deploying Minecraft server to GCP")
    print(f"Project: {PROJECT_ID}")
    print(f"Zone: {ZONE}")
    print("=" * 50)

    # Get static IP if available
    static_ip = assign_static_ip(PROJECT_ID, ZONE, INSTANCE_NAME)

    # Create the instance
    create_instance(PROJECT_ID, ZONE, INSTANCE_NAME, static_ip)

    print("\n" + "=" * 50)
    print("Deployment complete!")
    print("\nNext steps:")
    print("1. Wait 2-3 minutes for server to start")
    print("2. Connect with your Minecraft client to the external IP")
    print("3. Set up secrets: python deploy/setup_secrets.py")


if __name__ == "__main__":
    main()
