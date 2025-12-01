# API Contract: ServiceMapping

**Version**: 1.0.0 | **Status**: Draft | **Last Updated**: 2025-11-26

## Overview

ServiceMapping provides a canonical categorization layer that maps provider-specific Terraform resource types to semantic service categories. This enables consistent diagram layout and cross-provider resource equivalence (e.g., AWS EC2, Azure VM, and GCP Compute Engine all map to `compute.vm`).

## Type Signature

```python
from enum import Enum
from typing import Dict, Set

class ServiceCategory(Enum):
    """Canonical service categories for cross-provider semantic grouping"""
    
    # Compute categories
    COMPUTE_VM = "compute.vm"
    COMPUTE_CONTAINER = "compute.container"
    COMPUTE_SERVERLESS = "compute.serverless"
    COMPUTE_BATCH = "compute.batch"
    
    # Network categories
    NETWORK_VPC = "network.vpc"
    NETWORK_SUBNET = "network.subnet"
    NETWORK_LB = "network.lb"
    NETWORK_GATEWAY = "network.gateway"
    NETWORK_CDN = "network.cdn"
    NETWORK_DNS = "network.dns"
    
    # Storage categories
    STORAGE_OBJECT = "storage.object"
    STORAGE_BLOCK = "storage.block"
    STORAGE_FILE = "storage.file"
    
    # Database categories
    DATABASE_RELATIONAL = "database.relational"
    DATABASE_NOSQL = "database.nosql"
    DATABASE_CACHE = "database.cache"
    DATABASE_DATAWAREHOUSE = "database.datawarehouse"
    
    # Security categories
    SECURITY_FIREWALL = "security.firewall"
    SECURITY_IAM = "security.iam"
    SECURITY_SECRETS = "security.secrets"
    SECURITY_KEYS = "security.keys"
    
    # Analytics categories
    ANALYTICS_STREAMING = "analytics.streaming"
    ANALYTICS_BATCH = "analytics.batch"
    ANALYTICS_BI = "analytics.bi"
    
    # ML/AI categories
    ML_TRAINING = "ml.training"
    ML_INFERENCE = "ml.inference"
    ML_NOTEBOOK = "ml.notebook"
    
    # Integration categories
    INTEGRATION_QUEUE = "integration.queue"
    INTEGRATION_EVENTBUS = "integration.eventbus"
    INTEGRATION_API = "integration.api"
    
    # Management categories
    MANAGEMENT_MONITORING = "management.monitoring"
    MANAGEMENT_LOGGING = "management.logging"
    MANAGEMENT_AUTOMATION = "management.automation"
    
    # Generic fallback
    GENERIC = "generic"

class ServiceMapping:
    """Maps provider resource types to canonical categories"""
    
    @classmethod
    def get_category(cls, resource_type: str) -> ServiceCategory:
        """Get canonical category for resource type"""
        ...
    
    @classmethod
    def get_resources_by_category(cls, category: ServiceCategory) -> Set[str]:
        """Get all resource types in a category"""
        ...
    
    @classmethod
    def register(cls, resource_type: str, category: ServiceCategory) -> None:
        """Register custom resource type mapping (plugin extensibility)"""
        ...
```

## ServiceCategory Enum

### Purpose

Defines semantic categories that transcend provider-specific naming conventions. Enables:
- **Consistent layout**: Resources in same category grouped together regardless of provider
- **Cross-provider equivalence**: Identify functionally similar resources across clouds
- **Icon fallback**: Generic category icons used when provider-specific icons missing

### Naming Convention

**Format**: `{domain}.{subdomain}`

**Examples**:
- `compute.vm` - Virtual machines
- `network.lb` - Load balancers
- `database.relational` - Relational databases

**Rationale**: Two-level hierarchy balances specificity with simplicity. Avoids over-categorization (e.g., `compute.vm.linux.x86` is too granular).

### Category Domains

#### Compute Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `compute.vm` | Virtual machines | `aws_instance` | `azurerm_virtual_machine` | `google_compute_instance` |
| `compute.container` | Container orchestration | `aws_ecs_service`, `aws_eks_cluster` | `azurerm_kubernetes_cluster` | `google_kubernetes_cluster` |
| `compute.serverless` | Function-as-a-Service | `aws_lambda_function` | `azurerm_function_app` | `google_cloudfunctions_function` |
| `compute.batch` | Batch job processing | `aws_batch_job_definition` | `azurerm_batch_pool` | `google_dataproc_cluster` |

#### Network Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `network.vpc` | Virtual private networks | `aws_vpc` | `azurerm_virtual_network` | `google_compute_network` |
| `network.subnet` | Network subnets | `aws_subnet` | `azurerm_subnet` | `google_compute_subnetwork` |
| `network.lb` | Load balancers | `aws_lb`, `aws_elb` | `azurerm_load_balancer` | `google_compute_backend_service` |
| `network.gateway` | Network gateways | `aws_internet_gateway`, `aws_nat_gateway` | `azurerm_virtual_network_gateway` | `google_compute_router` |
| `network.cdn` | Content delivery networks | `aws_cloudfront_distribution` | `azurerm_cdn_profile` | `google_compute_backend_bucket` |
| `network.dns` | DNS services | `aws_route53_zone` | `azurerm_dns_zone` | `google_dns_managed_zone` |

#### Storage Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `storage.object` | Object/blob storage | `aws_s3_bucket` | `azurerm_storage_account` | `google_storage_bucket` |
| `storage.block` | Block storage volumes | `aws_ebs_volume` | `azurerm_managed_disk` | `google_compute_disk` |
| `storage.file` | File storage systems | `aws_efs_file_system` | `azurerm_storage_share` | `google_filestore_instance` |

#### Database Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `database.relational` | SQL databases | `aws_db_instance`, `aws_rds_cluster` | `azurerm_mysql_server` | `google_sql_database_instance` |
| `database.nosql` | NoSQL databases | `aws_dynamodb_table` | `azurerm_cosmosdb_account` | `google_firestore_database` |
| `database.cache` | In-memory caches | `aws_elasticache_cluster` | `azurerm_redis_cache` | `google_redis_instance` |
| `database.datawarehouse` | Data warehouses | `aws_redshift_cluster` | `azurerm_synapse_workspace` | `google_bigquery_dataset` |

#### Security Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `security.firewall` | Network firewalls | `aws_security_group` | `azurerm_network_security_group` | `google_compute_firewall` |
| `security.iam` | Identity and access mgmt | `aws_iam_role`, `aws_iam_policy` | `azurerm_role_assignment` | `google_project_iam_binding` |
| `security.secrets` | Secret management | `aws_secretsmanager_secret` | `azurerm_key_vault` | `google_secret_manager_secret` |
| `security.keys` | Encryption keys | `aws_kms_key` | `azurerm_key_vault_key` | `google_kms_crypto_key` |

#### Analytics Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `analytics.streaming` | Stream processing | `aws_kinesis_stream` | `azurerm_stream_analytics_job` | `google_dataflow_job` |
| `analytics.batch` | Batch analytics | `aws_emr_cluster` | `azurerm_hdinsight_cluster` | `google_dataproc_cluster` |
| `analytics.bi` | Business intelligence | `aws_quicksight_dashboard` | `azurerm_powerbi_embedded` | `google_data_studio_report` |

#### ML/AI Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `ml.training` | Model training | `aws_sagemaker_training_job` | `azurerm_machine_learning_compute` | `google_ai_platform_training_job` |
| `ml.inference` | Model inference/serving | `aws_sagemaker_endpoint` | `azurerm_machine_learning_webservice` | `google_ai_platform_model` |
| `ml.notebook` | Interactive notebooks | `aws_sagemaker_notebook_instance` | `azurerm_databricks_workspace` | `google_notebooks_instance` |

#### Integration Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `integration.queue` | Message queues | `aws_sqs_queue` | `azurerm_servicebus_queue` | `google_pubsub_subscription` |
| `integration.eventbus` | Event buses | `aws_eventbridge_bus` | `azurerm_eventgrid_topic` | `google_pubsub_topic` |
| `integration.api` | API gateways | `aws_api_gateway_rest_api` | `azurerm_api_management` | `google_api_gateway_api` |

#### Management Domain

| Category | Description | AWS Examples | Azure Examples | GCP Examples |
|----------|-------------|--------------|----------------|--------------|
| `management.monitoring` | Monitoring/metrics | `aws_cloudwatch_dashboard` | `azurerm_monitor_action_group` | `google_monitoring_dashboard` |
| `management.logging` | Centralized logging | `aws_cloudwatch_log_group` | `azurerm_log_analytics_workspace` | `google_logging_project_sink` |
| `management.automation` | Automation/orchestration | `aws_ssm_document` | `azurerm_automation_account` | `google_deployment_manager_deployment` |

#### Generic Fallback

| Category | Description | Usage |
|----------|-------------|-------|
| `generic` | Unmapped resources | Default when resource type not in mappings dict |

### Extensibility

**Phase 1**: 40+ categories covering core services

**Future Expansion**:
- IoT domain: `iot.device`, `iot.gateway`, `iot.analytics`
- Blockchain domain: `blockchain.node`, `blockchain.ledger`
- Quantum domain: `quantum.simulator`, `quantum.hardware`
- Media domain: `media.transcoding`, `media.streaming`

**Adding Categories** (example):
```python
# Future: IoT support
class ServiceCategory(Enum):
    # ... existing categories
    IOT_DEVICE = "iot.device"
    IOT_GATEWAY = "iot.gateway"
    IOT_ANALYTICS = "iot.analytics"
```

## ServiceMapping Class Methods

### `get_category(resource_type: str) -> ServiceCategory`

**Purpose**: Get canonical category for a Terraform resource type

**Parameters**:
- `resource_type`: Terraform resource type string (e.g., `'aws_instance'`, `'azurerm_virtual_machine'`)

**Returns**: ServiceCategory enum value (defaults to `ServiceCategory.GENERIC` if unmapped)

**Complexity**: O(1) dictionary lookup

**Example**:
```python
# AWS EC2
category = ServiceMapping.get_category('aws_instance')
assert category == ServiceCategory.COMPUTE_VM
assert category.value == 'compute.vm'

# Azure VM (semantically equivalent to AWS EC2)
category = ServiceMapping.get_category('azurerm_virtual_machine')
assert category == ServiceCategory.COMPUTE_VM

# Cross-provider equivalence
aws_cat = ServiceMapping.get_category('aws_instance')
azure_cat = ServiceMapping.get_category('azurerm_virtual_machine')
gcp_cat = ServiceMapping.get_category('google_compute_instance')
assert aws_cat == azure_cat == gcp_cat  # All compute.vm

# Unknown resource type
category = ServiceMapping.get_category('custom_unknown_type')
assert category == ServiceCategory.GENERIC
```

**Thread Safety**: Safe (read-only dict access)

### `get_resources_by_category(category: ServiceCategory) -> Set[str]`

**Purpose**: Get all resource types mapped to a category (reverse lookup)

**Parameters**:
- `category`: ServiceCategory enum value

**Returns**: Set of resource type strings

**Complexity**: O(n) where n = total mappings (cached if needed)

**Example**:
```python
# Get all VM-type resources across providers
vm_resources = ServiceMapping.get_resources_by_category(ServiceCategory.COMPUTE_VM)
assert 'aws_instance' in vm_resources
assert 'azurerm_virtual_machine' in vm_resources
assert 'google_compute_instance' in vm_resources

# Get all load balancers
lb_resources = ServiceMapping.get_resources_by_category(ServiceCategory.NETWORK_LB)
assert 'aws_lb' in lb_resources
assert 'aws_elb' in lb_resources
assert 'azurerm_load_balancer' in lb_resources
```

**Usage**: Diagram layout algorithms group resources by category

### `register(resource_type: str, category: ServiceCategory) -> None`

**Purpose**: Register custom resource type mapping (enables plugin extensibility)

**Parameters**:
- `resource_type`: Terraform resource type string
- `category`: ServiceCategory enum value

**Returns**: None

**Side Effects**: Modifies internal `_mappings` dict

**Example**:
```python
# Plugin adds custom provider support
ServiceMapping.register('oci_core_instance', ServiceCategory.COMPUTE_VM)
ServiceMapping.register('oci_objectstorage_bucket', ServiceCategory.STORAGE_OBJECT)

# Now OCI resources mapped correctly
category = ServiceMapping.get_category('oci_core_instance')
assert category == ServiceCategory.COMPUTE_VM
```

**Thread Safety**: Not thread-safe (modifies class-level dict)

**Validation**: None (trusts caller to provide valid inputs)

## Internal Data Structure

### `_mappings: Dict[str, ServiceCategory]`

**Purpose**: Internal dictionary storing resource type → category mappings

**Visibility**: Class-level private variable (convention: single underscore)

**Structure**:
```python
_mappings = {
    # AWS
    'aws_instance': ServiceCategory.COMPUTE_VM,
    'aws_lambda_function': ServiceCategory.COMPUTE_SERVERLESS,
    'aws_s3_bucket': ServiceCategory.STORAGE_OBJECT,
    # ... 200+ AWS mappings
    
    # Azure
    'azurerm_virtual_machine': ServiceCategory.COMPUTE_VM,
    'azurerm_function_app': ServiceCategory.COMPUTE_SERVERLESS,
    'azurerm_storage_account': ServiceCategory.STORAGE_OBJECT,
    # ... 100+ Azure mappings
    
    # GCP
    'google_compute_instance': ServiceCategory.COMPUTE_VM,
    'google_cloudfunctions_function': ServiceCategory.COMPUTE_SERVERLESS,
    'google_storage_bucket': ServiceCategory.STORAGE_OBJECT,
    # ... 100+ GCP mappings
}
```

**Phase 1 Size**: ~150 mappings (50 AWS core + 50 Azure core + 50 GCP core)

**Future Size**: 400+ mappings (200+ AWS + 100+ Azure + 100+ GCP)

## Cross-Provider Equivalence Examples

### Virtual Machines
```python
assert ServiceMapping.get_category('aws_instance') == \
       ServiceMapping.get_category('azurerm_virtual_machine') == \
       ServiceMapping.get_category('azurerm_linux_virtual_machine') == \
       ServiceMapping.get_category('google_compute_instance') == \
       ServiceCategory.COMPUTE_VM
```

### Object Storage
```python
assert ServiceMapping.get_category('aws_s3_bucket') == \
       ServiceMapping.get_category('azurerm_storage_account') == \
       ServiceMapping.get_category('google_storage_bucket') == \
       ServiceCategory.STORAGE_OBJECT
```

### Kubernetes
```python
assert ServiceMapping.get_category('aws_eks_cluster') == \
       ServiceMapping.get_category('azurerm_kubernetes_cluster') == \
       ServiceMapping.get_category('google_kubernetes_cluster') == \
       ServiceCategory.COMPUTE_CONTAINER
```

### Relational Databases
```python
assert ServiceMapping.get_category('aws_db_instance') == \
       ServiceMapping.get_category('azurerm_mysql_server') == \
       ServiceMapping.get_category('google_sql_database_instance') == \
       ServiceCategory.DATABASE_RELATIONAL
```

## Usage Patterns

### Diagram Layout
```python
# Group resources by category for consistent layout
from collections import defaultdict

resources_by_category = defaultdict(list)
for resource_type in tfdata['all_resource'].keys():
    category = ServiceMapping.get_category(resource_type)
    resources_by_category[category].append(resource_type)

# Render all VMs together, all load balancers together, etc.
for category, resources in resources_by_category.items():
    render_category_group(category, resources)
```

### Icon Fallback
```python
# Use category for generic icon when provider-specific icon missing
resource_type = 'azurerm_new_service'  # New Azure service, no icon yet
category = ServiceMapping.get_category(resource_type)

icon_path = f"resource_images/azure/compute/{resource_type}.png"
if not os.path.exists(icon_path):
    # Fallback to generic category icon
    category_name = category.value.split('.')[0]  # 'compute.vm' -> 'compute'
    icon_path = f"resource_images/generic/{category_name}/{category_name}.png"
```

### Cross-Provider Comparison
```python
# Find all resources in a multi-cloud diagram that are VMs
vm_category = ServiceCategory.COMPUTE_VM
all_vms = [
    (resource_type, provider)
    for resource_type, resource_data in tfdata['all_resource'].items()
    if ServiceMapping.get_category(resource_type) == vm_category
    for provider in [resource_data['provider_name'].split('/')[-1]]
]

# Result: [('aws_instance', 'aws'), ('azurerm_virtual_machine', 'azure'), ...]
```

## Validation and Quality

### Completeness Check
```python
def validate_core_resources_mapped():
    """Ensure common resources are mapped (not GENERIC)"""
    core_resources = [
        'aws_instance', 'aws_s3_bucket', 'aws_vpc', 'aws_lambda_function',
        'azurerm_virtual_machine', 'azurerm_storage_account', 'azurerm_virtual_network',
        'google_compute_instance', 'google_storage_bucket', 'google_compute_network',
    ]
    
    for resource_type in core_resources:
        category = ServiceMapping.get_category(resource_type)
        assert category != ServiceCategory.GENERIC, \
            f"Core resource {resource_type} unmapped!"
```

### Category Distribution Check
```python
def analyze_category_distribution():
    """Report how many resources per category"""
    from collections import Counter
    
    categories = [
        ServiceMapping.get_category(rt)
        for rt in ServiceMapping._mappings.keys()
    ]
    
    distribution = Counter(categories)
    for category, count in distribution.most_common():
        print(f"{category.value}: {count} resources")
    
    # Example output:
    # compute.vm: 12 resources
    # network.lb: 8 resources
    # storage.object: 6 resources
    # ...
```

## Performance Characteristics

| Operation | Complexity | Expected Latency | Notes |
|-----------|------------|------------------|-------|
| `get_category()` | O(1) | <1μs | Dict lookup |
| `get_resources_by_category()` | O(n) | ~100μs | Iterates all mappings (~400) |
| `register()` | O(1) | <1μs | Dict insert |

**Memory Usage**: ~50KB (400 mappings × ~125 bytes each)

**Caching**: Not needed (O(1) lookups already fast)

## Testing Contract

### Unit Tests

```python
# tests/unit/test_service_mapping.py
import pytest
from modules.service_mapping import ServiceMapping, ServiceCategory

class TestServiceMapping:
    def test_get_category_aws(self):
        """AWS resources map to correct categories"""
        assert ServiceMapping.get_category('aws_instance') == ServiceCategory.COMPUTE_VM
        assert ServiceMapping.get_category('aws_s3_bucket') == ServiceCategory.STORAGE_OBJECT
        assert ServiceMapping.get_category('aws_vpc') == ServiceCategory.NETWORK_VPC
    
    def test_cross_provider_equivalence(self):
        """Equivalent resources map to same category"""
        vm_category = ServiceCategory.COMPUTE_VM
        
        assert ServiceMapping.get_category('aws_instance') == vm_category
        assert ServiceMapping.get_category('azurerm_virtual_machine') == vm_category
        assert ServiceMapping.get_category('google_compute_instance') == vm_category
    
    def test_unknown_resource_generic(self):
        """Unknown resources default to GENERIC"""
        category = ServiceMapping.get_category('totally_unknown_resource')
        assert category == ServiceCategory.GENERIC
    
    def test_get_resources_by_category(self):
        """Reverse lookup returns correct resources"""
        vm_resources = ServiceMapping.get_resources_by_category(ServiceCategory.COMPUTE_VM)
        
        assert 'aws_instance' in vm_resources
        assert 'azurerm_virtual_machine' in vm_resources
        assert 'google_compute_instance' in vm_resources
        assert 'aws_s3_bucket' not in vm_resources  # Wrong category
    
    def test_register_custom_mapping(self):
        """Custom mappings can be registered"""
        ServiceMapping.register('custom_vm_type', ServiceCategory.COMPUTE_VM)
        
        category = ServiceMapping.get_category('custom_vm_type')
        assert category == ServiceCategory.COMPUTE_VM
        
        # Cleanup
        del ServiceMapping._mappings['custom_vm_type']
    
    def test_category_enum_values(self):
        """Category enum values follow naming convention"""
        for category in ServiceCategory:
            if category != ServiceCategory.GENERIC:
                # Should be in format 'domain.subdomain'
                parts = category.value.split('.')
                assert len(parts) == 2, f"Category {category.value} not in 'domain.subdomain' format"
```

### Integration Tests

```python
# tests/integration/test_category_coverage.py
@pytest.mark.slow
class TestCategoryCoverage:
    def test_all_aws_resources_mapped(self):
        """All AWS resources in test fixtures are mapped"""
        tfdata = parse_terraform('tests/fixtures/aws/wordpress/')
        
        for resource_type in tfdata['all_resource'].keys():
            if resource_type.startswith('aws_'):
                category = ServiceMapping.get_category(resource_type)
                # Warn if generic, but don't fail (some resources intentionally unmapped)
                if category == ServiceCategory.GENERIC:
                    print(f"Warning: {resource_type} unmapped (using GENERIC)")
```

## Migration Strategy

### Phase 1: Initial Mappings
- Map 50 core AWS resources
- Map 30 core Azure resources (VMs, networking, storage, databases)
- Map 30 core GCP resources (VMs, networking, storage, databases)
- **Total**: ~110 mappings

### Phase 2: Expansion
- Add remaining AWS services from existing cloud_config.py
- Expand Azure/GCP coverage to 100 resources each
- **Total**: ~300 mappings

### Phase 3: Long Tail
- Add specialty services (IoT, blockchain, quantum)
- Plugin contributions for additional providers
- **Total**: 400+ mappings

## Related Contracts

- [ProviderContext](./provider_context.md) - Uses ServiceMapping in `get_service_category()` method
- [ProviderDescriptor](./provider_descriptor.md) - Independent of ServiceMapping (no direct relationship)

## Open Questions

1. **Should categories support hierarchy beyond 2 levels?**
   - Current: `domain.subdomain` (2 levels)
   - Future: `domain.subdomain.detail` (3 levels)?
   - Decision: Keep 2 levels for Phase 1; expand if needed

2. **Should we validate category enum values at module load?**
   - Current: Trust developers follow naming convention
   - Future: Add regex validation in `__init_subclass__`?
   - Decision: Add validation in Phase 2 if issues arise

3. **Should get_resources_by_category() be cached?**
   - Current: O(n) iteration every call
   - Future: Cache results with invalidation on register()?
   - Decision: Add caching if performance tests show bottleneck

## Changelog

### v1.0.0 (2025-11-26)
- Initial contract definition
- 40+ canonical categories defined
- ~110 initial mappings (AWS/Azure/GCP core services)
- Plugin extensibility via `register()` method
