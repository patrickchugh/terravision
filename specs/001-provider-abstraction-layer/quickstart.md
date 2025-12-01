# Quickstart: Adding Provider Support to TerraVision

**Audience**: Contributors adding new cloud provider support  
**Time**: 2-3 hours for minimal viable provider  
**Prerequisites**: Python 3.9-3.11, familiarity with Terraform and Diagrams library

## Overview

This guide walks you through adding a new cloud provider to TerraVision using the Provider Abstraction Layer. We'll use **Oracle Cloud Infrastructure (OCI)** as an example, but the steps apply to any provider.

**What You'll Build**:
- Provider descriptor registration
- Provider configuration module (constants)
- 10-20 resource class mappings
- 10-20 service category mappings
- Basic icon set (5-10 icons)
- Unit tests

**End Result**: Generate diagrams from OCI Terraform configurations

---

## Step 1: Set Up Development Environment

### Install Dependencies

```bash
# Clone repository
git clone https://github.com/your-org/terravision.git
cd terravision

# Install dependencies with Poetry
poetry install

# Verify installation
poetry run python terravision.py --help
```

### Run Existing Tests

```bash
# Fast tests only (pre-commit hook)
poetry run pytest -m "not slow"

# All tests
poetry run pytest
```

**Expected**: All tests pass ✅

---

## Step 2: Research Provider Terraform Resources

### Identify Core Resources

**Goal**: Find 10-20 most common resources to support in Phase 1

**Sources**:
- Terraform Registry: https://registry.terraform.io/providers/oracle/oci/latest/docs
- Official documentation: https://docs.oracle.com/en-us/iaas/
- Example Terraform configs: GitHub search for `provider "oci"`

**OCI Example** (10 core resources):

| Resource Type | Service | Category | Priority |
|---------------|---------|----------|----------|
| `oci_core_instance` | Compute VM | compute.vm | P0 |
| `oci_core_vcn` | Virtual Cloud Network | network.vpc | P0 |
| `oci_core_subnet` | Subnet | network.subnet | P0 |
| `oci_core_internet_gateway` | Internet Gateway | network.gateway | P1 |
| `oci_load_balancer` | Load Balancer | network.lb | P1 |
| `oci_objectstorage_bucket` | Object Storage | storage.object | P0 |
| `oci_core_volume` | Block Volume | storage.block | P1 |
| `oci_database_db_system` | Database | database.relational | P1 |
| `oci_core_security_list` | Firewall | security.firewall | P0 |
| `oci_identity_policy` | IAM Policy | security.iam | P1 |

**Tip**: Focus on compute, network, storage, database, and security for Phase 1

---

## Step 3: Create Provider Descriptor

### File: `modules/cloud_config/__init__.py`

Add your provider descriptor to the existing file:

```python
# modules/cloud_config/__init__.py
from modules.provider_runtime import ProviderRegistry, ProviderDescriptor

# ... existing AWS, Azure, GCP descriptors ...

# New: OCI descriptor
OCI_DESCRIPTOR = ProviderDescriptor(
    name='oci',
    display_name='Oracle Cloud Infrastructure',
    resource_prefix='oci_',
    terraform_provider_name='hashicorp/oci',
    config_module='modules.cloud_config.oci',
    handler_module=None,  # Optional, can add later
    resource_class_prefix='resource_classes.oci',
    icon_directory='resource_images/oci',
    supports_annotations=True,
    supports_gitlibs=True,
    version='1.0.0',
    aliases=['oracle', 'oraclecloud']
)

# Register OCI provider
ProviderRegistry.register(OCI_DESCRIPTOR)
```

**Key Fields**:
- `name`: Lowercase canonical name (used in `--provider oci` CLI flag)
- `resource_prefix`: Terraform prefix (`oci_`)
- `terraform_provider_name`: From Terraform registry (`hashicorp/oci`)
- `config_module`: Python module path (create in Step 4)
- `resource_class_prefix`: Resource classes directory (create in Step 5)
- `icon_directory`: Icons directory (create in Step 6)

---

## Step 4: Create Provider Configuration Module

### File: `modules/cloud_config/oci.py`

Create configuration constants for OCI:

```python
# modules/cloud_config/oci.py
"""
Oracle Cloud Infrastructure provider configuration.

Defines OCI-specific constants for diagram generation.
"""

from typing import Dict, List, Any

# Node Consolidation Rules
# Group related resources together in diagrams
CONSOLIDATED_NODES: Dict[str, List[str]] = {
    # Example: Consolidate security lists with their rules
    'oci_core_security_list': ['oci_core_security_list_rule'],
    
    # Add more consolidation rules as needed
}

# Drawing Order
# Resources drawn in this order (background to foreground)
DRAW_ORDER: List[str] = [
    # Network layer (background)
    'oci_core_vcn',
    'oci_core_subnet',
    'oci_core_internet_gateway',
    'oci_core_nat_gateway',
    'oci_core_service_gateway',
    
    # Compute layer
    'oci_core_instance',
    'oci_containerengine_cluster',
    
    # Load balancing
    'oci_load_balancer',
    
    # Storage layer
    'oci_objectstorage_bucket',
    'oci_core_volume',
    'oci_file_storage_file_system',
    
    # Database layer
    'oci_database_db_system',
    'oci_database_autonomous_database',
    
    # Security layer (foreground)
    'oci_core_security_list',
    'oci_core_network_security_group',
    'oci_identity_policy',
]

# Icon Variant Mappings
# Map resource types to icon file names (if different)
NODE_VARIANTS: Dict[str, str] = {
    'oci_core_instance': 'compute',
    'oci_objectstorage_bucket': 'object-storage',
    'oci_core_vcn': 'vcn',
    # Add abbreviations/variants as needed
}

# Auto-Annotation Defaults
# Provider-specific annotation defaults
AUTO_ANNOTATIONS: Dict[str, Any] = {
    'consolidate_security_lists': True,
    'group_by_compartment': False,  # OCI-specific: compartments
    # Add OCI-specific defaults
}
```

**Customization Tips**:
- **CONSOLIDATED_NODES**: Group resources that are always used together
- **DRAW_ORDER**: Order by dependency (VPC before subnets before instances)
- **NODE_VARIANTS**: Use when icon filename differs from resource type
- **AUTO_ANNOTATIONS**: Provider-specific diagram defaults

---

## Step 5: Create Resource Classes

### Directory Structure

```bash
mkdir -p resource_classes/oci/compute
mkdir -p resource_classes/oci/network
mkdir -p resource_classes/oci/storage
mkdir -p resource_classes/oci/database
mkdir -p resource_classes/oci/security
```

### File: `resource_classes/oci/__init__.py`

```python
# resource_classes/oci/__init__.py
"""Oracle Cloud Infrastructure resource classes for Diagrams library."""

# Import modules to make them available
from . import compute, network, storage, database, security
```

### File: `resource_classes/oci/compute.py`

```python
# resource_classes/oci/compute.py
"""OCI Compute resource classes."""

from diagrams import Node

class Instance(Node):
    """OCI Compute Instance (VM)"""
    _provider = "oci"
    _type = "compute"
    
    def __init__(self, label: str = "Instance", **kwargs):
        super().__init__(label, **kwargs)

class ContainerEngine(Node):
    """OCI Container Engine for Kubernetes (OKE)"""
    _provider = "oci"
    _type = "compute"
    
    def __init__(self, label: str = "Container Engine", **kwargs):
        super().__init__(label, **kwargs)
```

### File: `resource_classes/oci/network.py`

```python
# resource_classes/oci/network.py
"""OCI Network resource classes."""

from diagrams import Node

class VCN(Node):
    """OCI Virtual Cloud Network"""
    _provider = "oci"
    _type = "network"
    
    def __init__(self, label: str = "VCN", **kwargs):
        super().__init__(label, **kwargs)

class Subnet(Node):
    """OCI Subnet"""
    _provider = "oci"
    _type = "network"
    
    def __init__(self, label: str = "Subnet", **kwargs):
        super().__init__(label, **kwargs)

class LoadBalancer(Node):
    """OCI Load Balancer"""
    _provider = "oci"
    _type = "network"
    
    def __init__(self, label: str = "Load Balancer", **kwargs):
        super().__init__(label, **kwargs)
```

**Repeat for**:
- `storage.py`: ObjectStorage, BlockVolume, FileStorage
- `database.py`: DBSystem, AutonomousDatabase
- `security.py`: SecurityList, NetworkSecurityGroup, IdentityPolicy

**Pattern**: Each class inherits from `diagrams.Node` and sets `_provider` and `_type` attributes

---

## Step 6: Add Service Mappings

### File: `modules/service_mapping.py`

Add OCI resources to the existing `ServiceMapping._mappings` dict:

```python
# modules/service_mapping.py
class ServiceMapping:
    _mappings: Dict[str, ServiceCategory] = {
        # ... existing AWS, Azure, GCP mappings ...
        
        # OCI Compute
        'oci_core_instance': ServiceCategory.COMPUTE_VM,
        'oci_containerengine_cluster': ServiceCategory.COMPUTE_CONTAINER,
        'oci_functions_function': ServiceCategory.COMPUTE_SERVERLESS,
        
        # OCI Network
        'oci_core_vcn': ServiceCategory.NETWORK_VPC,
        'oci_core_subnet': ServiceCategory.NETWORK_SUBNET,
        'oci_load_balancer': ServiceCategory.NETWORK_LB,
        'oci_core_internet_gateway': ServiceCategory.NETWORK_GATEWAY,
        
        # OCI Storage
        'oci_objectstorage_bucket': ServiceCategory.STORAGE_OBJECT,
        'oci_core_volume': ServiceCategory.STORAGE_BLOCK,
        'oci_file_storage_file_system': ServiceCategory.STORAGE_FILE,
        
        # OCI Database
        'oci_database_db_system': ServiceCategory.DATABASE_RELATIONAL,
        'oci_nosql_table': ServiceCategory.DATABASE_NOSQL,
        
        # OCI Security
        'oci_core_security_list': ServiceCategory.SECURITY_FIREWALL,
        'oci_identity_policy': ServiceCategory.SECURITY_IAM,
        'oci_vault_secret': ServiceCategory.SECURITY_SECRETS,
    }
```

**Tip**: Use existing categories when possible for cross-provider consistency

---

## Step 7: Add Icons (Optional but Recommended)

### Create Icon Directories

```bash
mkdir -p resource_images/oci/compute
mkdir -p resource_images/oci/network
mkdir -p resource_images/oci/storage
mkdir -p resource_images/oci/database
mkdir -p resource_images/oci/security
```

### Add Icon Files

**Sources**:
- Oracle official icons: https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm
- Cloud provider icon packs: https://github.com/mingrammer/diagrams/tree/master/resources

**File naming**: `{resource_type}.png` (e.g., `oci_core_instance.png`)

**Example**:
```bash
# Download OCI compute icon
cp ~/Downloads/oci-compute-icon.png resource_images/oci/compute/oci_core_instance.png

# Download OCI VCN icon
cp ~/Downloads/oci-vcn-icon.png resource_images/oci/network/oci_core_vcn.png
```

**Fallback**: If icons missing, TerraVision uses generic category icons automatically

---

## Step 8: Write Unit Tests

### File: `tests/unit/test_oci_provider.py`

```python
# tests/unit/test_oci_provider.py
"""Unit tests for OCI provider support."""

import pytest
from modules.provider_runtime import ProviderRegistry, ProviderContext
from modules.service_mapping import ServiceMapping, ServiceCategory

class TestOCIProvider:
    """Test OCI provider registration and configuration"""
    
    def test_oci_descriptor_registered(self):
        """OCI provider is registered"""
        descriptor = ProviderRegistry.get_descriptor('oci')
        assert descriptor is not None
        assert descriptor.name == 'oci'
        assert descriptor.display_name == 'Oracle Cloud Infrastructure'
    
    def test_oci_aliases(self):
        """OCI aliases work"""
        oci_desc = ProviderRegistry.get_descriptor('oci')
        oracle_desc = ProviderRegistry.get_descriptor('oracle')
        assert oci_desc == oracle_desc
    
    def test_oci_context_loading(self):
        """OCI context loads config correctly"""
        ctx = ProviderRegistry.get_context('oci')
        assert ctx.name == 'oci'
        
        # Config loaded
        assert isinstance(ctx.draw_order, list)
        assert 'oci_core_vcn' in ctx.draw_order
        assert isinstance(ctx.consolidated_nodes, dict)
    
    def test_oci_service_mappings(self):
        """OCI resources map to correct categories"""
        assert ServiceMapping.get_category('oci_core_instance') == ServiceCategory.COMPUTE_VM
        assert ServiceMapping.get_category('oci_core_vcn') == ServiceCategory.NETWORK_VPC
        assert ServiceMapping.get_category('oci_objectstorage_bucket') == ServiceCategory.STORAGE_OBJECT
    
    def test_oci_resource_class_resolution(self):
        """OCI resource classes resolve correctly"""
        ctx = ProviderRegistry.get_context('oci')
        
        # Should resolve to OCI-specific class
        instance_class = ctx.resolve_resource_class('oci_core_instance')
        assert instance_class is not None
        assert instance_class._provider == 'oci'
```

### Run Tests

```bash
poetry run pytest tests/unit/test_oci_provider.py -v
```

**Expected**: All tests pass ✅

---

## Step 9: Create Integration Test

### File: `tests/fixtures/oci/simple-vm/main.tf`

Create a minimal Terraform config for testing:

```hcl
# tests/fixtures/oci/simple-vm/main.tf
provider "oci" {
  region = "us-ashburn-1"
}

resource "oci_core_vcn" "test_vcn" {
  cidr_block     = "10.0.0.0/16"
  compartment_id = "ocid1.compartment.oc1..test"
  display_name   = "Test VCN"
}

resource "oci_core_subnet" "test_subnet" {
  cidr_block     = "10.0.1.0/24"
  vcn_id         = oci_core_vcn.test_vcn.id
  compartment_id = "ocid1.compartment.oc1..test"
  display_name   = "Test Subnet"
}

resource "oci_core_instance" "test_instance" {
  availability_domain = "AD-1"
  compartment_id      = "ocid1.compartment.oc1..test"
  shape               = "VM.Standard2.1"
  display_name        = "Test Instance"
  
  source_details {
    source_type = "image"
    source_id   = "ocid1.image.oc1..test"
  }
  
  create_vnic_details {
    subnet_id = oci_core_subnet.test_subnet.id
  }
}
```

### Generate Terraform Plan

```bash
cd tests/fixtures/oci/simple-vm
terraform init
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan > plan.json
```

### File: `tests/integration/test_oci_diagrams.py`

```python
# tests/integration/test_oci_diagrams.py
"""Integration tests for OCI diagram generation."""

import pytest
from modules.tfwrapper import parse_terraform
from modules.graphmaker import build_graph
from modules.provider_runtime import ProviderRegistry

@pytest.mark.slow
class TestOCIDiagrams:
    """Test end-to-end OCI diagram generation"""
    
    def test_simple_vm_diagram(self):
        """Generate diagram from simple OCI VM config"""
        tfdata = parse_terraform('tests/fixtures/oci/simple-vm/')
        
        # Detect OCI provider
        providers = ProviderRegistry.detect_providers(tfdata)
        assert 'oci' in providers
        
        # Build graph
        graphdict = build_graph(tfdata, provider='oci')
        
        # Verify resources present
        resource_types = [node['type'] for node in graphdict['nodes']]
        assert 'oci_core_vcn' in resource_types
        assert 'oci_core_subnet' in resource_types
        assert 'oci_core_instance' in resource_types
        
        # Verify connections (subnet → VCN, instance → subnet)
        assert len(graphdict['edges']) >= 2
```

### Run Integration Test

```bash
poetry run pytest tests/integration/test_oci_diagrams.py -v
```

**Expected**: Diagram generates successfully ✅

---

## Step 10: Test End-to-End CLI

### Generate Diagram with CLI

```bash
cd tests/fixtures/oci/simple-vm

# Method 1: Auto-detect provider
poetry run python terravision.py --tfplan plan.json --output oci-diagram.png

# Method 2: Explicit provider flag
poetry run python terravision.py --tfplan plan.json --provider oci --output oci-diagram.png
```

**Expected**: PNG diagram generated with OCI resources ✅

### Verify Diagram

Open `oci-diagram.png` and verify:
- VCN (Virtual Cloud Network) displayed
- Subnet nested inside VCN
- Compute instance connected to subnet
- Icons loaded correctly (or generic icons if missing)

---

## Step 11: Document Your Provider

### File: `docs/providers/oci.md`

Create provider-specific documentation:

```markdown
# Oracle Cloud Infrastructure (OCI) Provider

## Supported Resources (Phase 1)

### Compute
- `oci_core_instance` - Compute VM instances

### Network
- `oci_core_vcn` - Virtual Cloud Network
- `oci_core_subnet` - Subnet
- `oci_load_balancer` - Load Balancer

### Storage
- `oci_objectstorage_bucket` - Object Storage
- `oci_core_volume` - Block Volume

### Database
- `oci_database_db_system` - Database System

### Security
- `oci_core_security_list` - Security List (firewall rules)
- `oci_identity_policy` - IAM Policy

## Usage

```bash
# Auto-detect OCI provider from Terraform plan
terravision --tfplan plan.json

# Explicit provider flag
terravision --tfplan plan.json --provider oci
```

## Limitations

- Phase 1 supports ~10 core resources (expand in future)
- OCI-specific features (compartments, tags) not yet visualized
- Requires Terraform provider hashicorp/oci >= 4.0

## Contributing

To add more OCI resources, edit:
- `modules/cloud_config/oci.py` - Add to DRAW_ORDER
- `modules/service_mapping.py` - Add category mapping
- `resource_classes/oci/*.py` - Create resource class
```

---

## Step 12: Submit Pull Request

### Commit Changes

```bash
git checkout -b feature/add-oci-provider

git add modules/cloud_config/__init__.py
git add modules/cloud_config/oci.py
git add modules/service_mapping.py
git add resource_classes/oci/
git add resource_images/oci/
git add tests/unit/test_oci_provider.py
git add tests/integration/test_oci_diagrams.py
git add tests/fixtures/oci/
git add docs/providers/oci.md

git commit -m "feat: add Oracle Cloud Infrastructure (OCI) provider support

- Register OCI provider descriptor with aliases (oracle, oraclecloud)
- Add config module with 10 core resources
- Map OCI resources to service categories (compute, network, storage, etc.)
- Create resource classes for Diagrams integration
- Add unit and integration tests
- Include minimal icon set (5 icons)

Closes #123"
```

### Run Pre-Commit Hooks

```bash
poetry run pre-commit run --all-files
```

**Expected**: All hooks pass ✅

### Push and Create PR

```bash
git push origin feature/add-oci-provider

# Create PR on GitHub with description:
# - What: Add OCI provider support
# - Why: Enable TerraVision to generate diagrams from OCI Terraform configs
# - Testing: Unit tests + integration test with simple VM config
# - Docs: Added docs/providers/oci.md
```

---

## Troubleshooting

### "Provider not found" Error

**Symptom**: `ProviderRegistry.get_descriptor('oci')` returns None

**Fix**: Ensure you registered the descriptor in `modules/cloud_config/__init__.py`:
```python
ProviderRegistry.register(OCI_DESCRIPTOR)
```

### "Config module not found" Error

**Symptom**: `ImportError: No module named 'modules.cloud_config.oci'`

**Fix**: Create `modules/cloud_config/oci.py` and define all required constants:
- CONSOLIDATED_NODES
- DRAW_ORDER
- NODE_VARIANTS
- AUTO_ANNOTATIONS

### "Resource class not found" Error

**Symptom**: Diagram uses generic Blank icons for all resources

**Fix**: 
1. Create resource classes in `resource_classes/oci/compute.py`, etc.
2. Ensure class names match NodeFactory naming convention (PascalCase)
3. Check `__init__.py` imports modules correctly

### Icon Not Displaying

**Symptom**: Generic blank icons shown instead of provider icons

**Fix**: This is expected if icons not added yet. To add icons:
1. Download PNG icons (256×256 recommended)
2. Save to `resource_images/oci/{category}/{resource_type}.png`
3. Verify path matches `NODE_VARIANTS` if using abbreviations

### Tests Fail

**Symptom**: `pytest` shows failures

**Fix**:
1. Check test fixture Terraform is valid: `terraform validate`
2. Ensure Terraform plan JSON generated: `terraform show -json plan.tfplan > plan.json`
3. Verify service mappings include all resources in test fixtures

---

## Next Steps

### Phase 1 Complete ✅

You've successfully added a new provider! Your contribution includes:
- ✅ Provider descriptor registered
- ✅ Configuration module created
- ✅ 10+ resource classes defined
- ✅ Service mappings added
- ✅ Unit tests passing
- ✅ Integration test passing
- ✅ Documentation written

### Phase 2: Expand Coverage

**Add more resources**:
- Identify next 20-30 resources (serverless, analytics, ML services)
- Add to DRAW_ORDER, service mappings, and resource classes
- Update tests and documentation

**Add advanced features**:
- Custom consolidation rules (e.g., group OCI compartments)
- Provider-specific annotations (e.g., tag-based filtering)
- Custom icon variants for resource states

**Optimize performance**:
- Profile diagram generation for large OCI configs (500+ resources)
- Add LRU cache optimizations if needed
- Benchmark against AWS performance baseline

---

## Getting Help

**Questions?**
- GitHub Discussions: https://github.com/your-org/terravision/discussions
- Slack: #terravision-dev

**Found a bug?**
- GitHub Issues: https://github.com/your-org/terravision/issues

**Want to contribute more?**
- See ROADMAP.md for upcoming features
- Check "good first issue" labels

---

## Appendix: Provider Checklist

Use this checklist to track your progress:

- [ ] Step 1: Dev environment set up, tests passing
- [ ] Step 2: Researched 10-20 core resources
- [ ] Step 3: Created ProviderDescriptor
- [ ] Step 4: Created config module (oci.py)
- [ ] Step 5: Created resource classes
- [ ] Step 6: Added service mappings
- [ ] Step 7: Added icons (optional)
- [ ] Step 8: Wrote unit tests
- [ ] Step 9: Created integration test
- [ ] Step 10: Tested CLI end-to-end
- [ ] Step 11: Wrote provider documentation
- [ ] Step 12: Submitted pull request

**Time Estimate**: 2-3 hours for Phase 1 (10 resources, no icons)

**Maintenance**: ~30 min per quarter to add new resources as provider adds features
