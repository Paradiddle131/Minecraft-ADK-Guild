# Deployment Scripts Changelog

## 2024-06-19 - Library Updates

### Updated Libraries
- **google-cloud-compute**: 1.14.0 → 1.30.0
- **google-cloud-service-usage**: NEW (replaces google-cloud-resource-manager)
- **google-cloud-secret-manager**: 2.16.0 → 2.24.0
- **google-cloud-monitoring**: 2.15.0 → 2.22.0
- **google-cloud-aiplatform**: 1.43.0 → 1.70.0
- **google-auth**: Added 2.29.0 (explicit dependency)

### API Changes

#### Service Enablement (setup_project.py)
- **OLD**: `resourcemanager_v3.ServicesClient()` (deprecated/removed)
- **NEW**: `service_usage_v1.ServiceUsageClient()` (current standard)
- **Method**: Now uses `EnableServiceRequest` and `GetServiceRequest` patterns
- **Benefit**: More reliable service enablement with proper request objects

#### Secret Manager (setup_secrets.py)
- **Already up-to-date**: Using latest `secretmanager.SecretManagerServiceClient()`
- **Patterns**: Follows 2024 best practices with request objects
- **Features**: Support for TTL, checksums, and modern replication patterns

#### Compute Engine (deploy_minecraft.py, setup_monitoring.py)
- **Already up-to-date**: Using `compute_v1` clients
- **Clients**: `FirewallsClient`, `InstancesClient`, `GlobalAddressesClient`
- **Patterns**: Modern request-response patterns

### Compatibility
- All scripts now use the latest 2024 GCP Python SDK patterns
- Request objects used consistently for better type safety
- Improved error handling and status reporting
- Backward compatible with existing GCP projects

### Testing
- Verified against latest Google Cloud Python SDK documentation
- Updated requirements files reflect latest stable versions
- All deprecated imports removed and replaced with current APIs