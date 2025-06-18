"""Set up basic monitoring for the Minecraft server"""

from google.api_core import exceptions
from google.cloud import monitoring_v3

from config import MINECRAFT_PORT, PROJECT_ID, STATIC_IP_NAME


def create_uptime_check(project_id: str) -> None:
    """Create an uptime check for the Minecraft server"""

    client = monitoring_v3.UptimeCheckServiceClient()
    project_path = f"projects/{project_id}"

    # Get the static IP address
    from google.cloud import compute_v1

    addresses_client = compute_v1.GlobalAddressesClient()

    try:
        address = addresses_client.get(project=project_id, address=STATIC_IP_NAME)
        if not address.address:
            print("⚠️  Static IP not yet assigned, skipping uptime check")
            return

        server_ip = address.address
        print(f"Creating uptime check for {server_ip}:{MINECRAFT_PORT}")

    except exceptions.NotFound:
        print("⚠️  No static IP found, skipping uptime check")
        return

    # Define the uptime check configuration
    uptime_check_config = monitoring_v3.UptimeCheckConfig(
        display_name=f"Minecraft Server Port {MINECRAFT_PORT}",
        monitored_resource=monitoring_v3.MonitoredResource(
            type="uptime_url",
            labels={
                "project_id": project_id,
                "host": server_ip,
            },
        ),
        tcp_check=monitoring_v3.UptimeCheckConfig.TcpCheck(
            port=MINECRAFT_PORT,
        ),
        timeout=monitoring_v3.Duration(seconds=10),
        period=monitoring_v3.Duration(seconds=300),  # Check every 5 minutes
    )

    # Check if uptime check already exists
    existing_checks = client.list_uptime_check_configs(parent=project_path)
    for check in existing_checks:
        if check.display_name == uptime_check_config.display_name:
            print(f"✓ Uptime check already exists: {check.name}")
            return

    # Create the uptime check
    try:
        uptime_check = client.create_uptime_check_config(
            parent=project_path,
            uptime_check_config=uptime_check_config,
        )
        print(f"✓ Uptime check created: {uptime_check.name}")
        print(f"  Monitoring {server_ip}:{MINECRAFT_PORT} every 5 minutes")

    except Exception as e:
        print(f"✗ Error creating uptime check: {e}")


def main():
    """Main monitoring setup function"""
    print(f"Setting up monitoring for project: {PROJECT_ID}")
    print("=" * 50)

    # Create uptime check
    create_uptime_check(PROJECT_ID)

    print("\n" + "=" * 50)
    print("Monitoring setup complete!")
    print("\nYou can view monitoring data in the Google Cloud Console:")
    print(f"https://console.cloud.google.com/monitoring/uptime?project={PROJECT_ID}")
    print("\nLogs are automatically collected and can be viewed at:")
    print(f"https://console.cloud.google.com/logs?project={PROJECT_ID}")
    print("\nNext step:")
    print("Set up CI/CD: Create cloudbuild.yaml and push to trigger builds")


if __name__ == "__main__":
    main()
