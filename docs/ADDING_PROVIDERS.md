# Developer Guide: Adding New Cloud Providers to TerraVision

This guide explains how to add support for a new cloud provider to TerraVision using the multi-cloud provider abstraction layer implemented in Phases 1-6.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Step-by-Step Guide](#step-by-step-guide)
- [Provider Configuration Reference](#provider-configuration-reference)
- [Testing Requirements](#testing-requirements)
- [Best Practices](#best-practices)

---

## Overview

TerraVision's provider abstraction layer (introduced in v0.8) enables adding new cloud providers by:
1. Creating a provider configuration module
2. Registering the provider with the runtime
3. Adding tests to validate the provider

**Time to Add Provider:** ~2-4 hours for basic support
**Code Required:** ~250-400 lines (configuration only, no handler functions required initially)

---

## Architecture

### Provider Abstraction Components

```
modules/
├── provider_runtime.py          # Provider detection & registry (272 lines)
├── cloud_config/
│   ├── common.py               # Base CloudConfig contract
│   ├── aws.py                  # AWS provider config (existing)
│   ├── azure.py                # Azure provider config (303 lines, Phase 5)
│   ├── gcp.py                  # GCP provider config (398 lines, Phase 5)
│   └── YOUR_PROVIDER.py        # Your new provider config
└── resource_handlers/
    ├── aws.py                  # AWS-specific handlers (existing)
    ├── azure.py                # Azure handlers (stub, Phase 8)
    ├── gcp.py                  # GCP handlers (stub, Phase 9)
    └── YOUR_PROVIDER.py        # Your provider handlers (optional)
```

### Data Flow

```
Terraform JSON → ProviderDetector → ProviderContext → ProviderConfig
                       ↓                  ↓                ↓
                  Identify provider   Load config    Apply rules
```

---

## Step-by-Step Guide

### Step 1: Create Provider Configuration Module

Create a new file at `modules/cloud_config/YOUR_PROVIDER.py`:

```python
"""
YOUR_PROVIDER Provider Configuration for TerraVision Multi-Cloud Architecture.

This module defines all YOUR_PROVIDER-specific constants and configuration
used throughout the graph building and rendering pipeline.

Provider Information:
- Provider ID: your_provider
- Terraform Provider: hashicorp/your_provider (or custom)
- Resource Prefix: your_provider_*

Status: Phase X (Initial Implementation)
TODO: Implement handler functions in resource_handlers/YOUR_PROVIDER.py
"""

# ============================================================================
# CONSOLIDATED_NODES: Multi-Resource Consolidation Definitions
# ============================================================================
# Resources with multiple sub-types that should be consolidated to a single
# diagram node (e.g., database + replicas + backups → single DB icon).
#
# Structure:
#   - Key: Base resource type pattern
#   - resource_name: Default name format for consolidated node
#   - import_location: Python path to icon class
#   - vpc: Boolean indicating if resource belongs inside VPC boundary
#   - edge_service: Boolean indicating if resource is at network edge
# ============================================================================
CONSOLIDATED_NODES = [
    # Example: DNS service consolidation
    {
        "your_provider_dns_zone": {
            "resource_name": "your_provider_dns_zone.dns",
            "import_location": "resource_classes.your_provider.network",
            "vpc": False,  # Global service, not VPC-scoped
            "edge_service": True,  # Receives external traffic
        }
    },
    # Add more consolidations here...
]

# ============================================================================
# GROUP_NODES: Container/Hierarchical Resources
# ============================================================================
# Resources that act as containers (drawn as subgraphs with nested resources).
# ============================================================================
GROUP_NODES = [
    "your_provider_vpc",         # Top-level network boundary
    "your_provider_subnet",      # Subnet within VPC
    "your_provider_project",     # Project/account boundary
]

# ============================================================================
# EDGE_NODES: Network Edge Services
# ============================================================================
# Services at the network edge (outside VPC, inside cloud perimeter).
# ============================================================================
EDGE_NODES = [
    "your_provider_dns_zone",
    "your_provider_cdn",
    "your_provider_load_balancer",
]

# ============================================================================
# OUTER_NODES: External Entities
# ============================================================================
# Virtual nodes representing external traffic sources/destinations.
# Prefixed with 'tv_' to distinguish from Terraform resources.
# ============================================================================
OUTER_NODES = [
    "tv_your_provider_users",      # End users
    "tv_your_provider_internet"    # Internet connectivity
]

# ============================================================================
# DRAW_ORDER: Rendering Layer Order
# ============================================================================
# Controls diagram layering (earlier = outermost, later = innermost).
# ============================================================================
DRAW_ORDER = [
    OUTER_NODES,           # Layer 1: External entities
    EDGE_NODES,            # Layer 2: Edge services
    GROUP_NODES,           # Layer 3: Container resources
    CONSOLIDATED_NODES,    # Layer 4: Consolidated nodes
    [""],                  # Layer 5: All other resources
]

# ============================================================================
# AUTO_ANNOTATIONS: Automatic Edge Creation Rules
# ============================================================================
# Defines automatic connections for common patterns.
#
# Structure:
#   - Key: Terraform resource type
#   - link: List of target node patterns (supports wildcards)
#   - arrow: "forward" (source→dest) or "reverse" (dest→source)
# ============================================================================
AUTO_ANNOTATIONS = [
    # DNS receives queries from users (users → DNS)
    {
        "your_provider_dns_zone": {
            "link": ["tv_your_provider_users.users"],
            "arrow": "reverse",
        }
    },
    # Public IPs connect to internet (resource → internet)
    {
        "your_provider_public_ip": {
            "link": ["tv_your_provider_internet.internet"],
            "arrow": "forward",
        }
    },
    # Add more auto-annotation rules here...
]

# ============================================================================
# NODE_VARIANTS: Resource Type Variation Mapping
# ============================================================================
# Maps base resource types to variant-specific icons based on metadata
# (SKU, tier, size, etc.) for visual differentiation.
#
# Matching: Case-sensitive substring match against resource metadata
# Example: "Standard" in tier → use "standard" variant icon
# ============================================================================
NODE_VARIANTS = {
    # Virtual Machine variants by size
    "your_provider_vm": {
        "small": "your_provider_vm_small",
        "medium": "your_provider_vm_medium",
        "large": "your_provider_vm_large",
    },
    # Storage variants by tier
    "your_provider_storage": {
        "standard": "your_provider_storage_standard",
        "premium": "your_provider_storage_premium",
    },
    # Database variants by engine
    "your_provider_database": {
        "postgres": "your_provider_db_postgres",
        "mysql": "your_provider_db_mysql",
    },
    # Add more variant mappings here...
}

# ============================================================================
# ARROW DIRECTION RULES
# ============================================================================
# Resources with reversed arrow direction (dependency flows opposite)
REVERSE_ARROW_LIST = [
    "your_provider_vpc.",
    "your_provider_subnet.",
    "your_provider_dns_zone",
]

# Forced destination (databases, VMs - arrows point TO these)
FORCED_DEST = [
    "your_provider_database",
    "your_provider_vm",
]

# Forced origin (edge services - arrows point FROM these)
FORCED_ORIGIN = [
    "your_provider_dns_zone",
    "your_provider_cdn",
]

# ============================================================================
# CONNECTION PATTERNS
# ============================================================================
# Implied connections based on metadata keywords
IMPLIED_CONNECTIONS = {
    "kms_key_id": "your_provider_kms",
    "certificate_arn": "your_provider_certificate",
}

# ============================================================================
# SPECIAL RESOURCE HANDLERS
# ============================================================================
# Maps resource types to handler function names in resource_handlers/YOUR_PROVIDER.py
# These are optional - can be implemented in Phase 8+
SPECIAL_RESOURCES = {
    "your_provider_vpc": "handle_vpc_subnets",
    "your_provider_load_balancer": "handle_load_balancer",
}

# ============================================================================
# RESOURCE CATEGORIZATION
# ============================================================================
# Shared services (accessible across multiple VPCs)
SHARED_SERVICES = [
    "your_provider_kms",
    "your_provider_storage",
    "your_provider_dns_zone",
]

# Always draw connection lines
ALWAYS_DRAW_LINE = [
    "your_provider_load_balancer",
    "your_provider_security_group",
]

# Never draw connection lines
NEVER_DRAW_LINE = [
    "your_provider_iam_role",
    "your_provider_iam_policy",
]

# Disconnect list (resources to skip in graph)
DISCONNECT_LIST = [
    "your_provider_iam_role",
]

# ============================================================================
# STYLING CONSTANTS
# ============================================================================
# Acronyms to preserve in uppercase
ACRONYMS_LIST = [
    "vm",
    "vpc",
    "dns",
    "cdn",
    "kms",
    "db",
    "ip",
]

# Name replacements for better readability
NAME_REPLACEMENTS = {
    "virtual_machine": "VM",
    "virtual_network": "VPC",
    "load_balancer": "Load Balancer",
    "public_ip": "Public IP",
}
```

### Step 2: Register Provider in Runtime

Edit `modules/provider_runtime.py` and add your provider to the registry:

```python
# Add import at top
from modules.cloud_config import your_provider as YourProviderConfig

# In ProviderRegistry.__init__, add registration:
def __init__(self):
    self._providers = {}
    self.register("aws", AWSConfig)
    self.register("azurerm", AzureConfig)
    self.register("google", GCPConfig)
    self.register("your_provider", YourProviderConfig)  # Add this line
```

### Step 3: Update Provider Detection Logic

Edit `modules/provider_runtime.py` in the `ProviderDetector._detect_from_resources` method:

```python
# Add your provider's resource prefix pattern
if addr.startswith("aws_"):
    return "aws"
elif addr.startswith(("azurerm_", "azuread_")):
    return "azurerm"
elif addr.startswith("google_"):
    return "google"
elif addr.startswith("your_provider_"):  # Add this
    return "your_provider"
```

### Step 4: Create Test Fixtures

Create test files in `tests/json/`:

**`tests/json/your_provider-basic-tfdata.json`:**
```json
{
    "codepath": ["/test/your_provider-basic"],
    "workdir": "/test",
    "plandata": {
        "format_version": "1.2",
        "terraform_version": "1.5.0",
        "variables": {},
        "planned_values": {
            "root_module": {
                "resources": [
                    {
                        "address": "your_provider_vpc.main",
                        "mode": "managed",
                        "type": "your_provider_vpc",
                        "name": "main",
                        "provider_name": "registry.terraform.io/hashicorp/your_provider",
                        "values": {
                            "name": "vpc-test",
                            "cidr_block": "10.0.0.0/16"
                        }
                    }
                ]
            }
        }
    }
}
```

### Step 5: Add Unit Tests

Edit `tests/helpers_unit_test.py` to add provider detection tests:

```python
def test_your_provider_provider_detection(self):
    """Test detection of YourProvider provider."""
    tfdata = {
        "all_resource": {
            "your_provider_vpc.main": {"type": "your_provider_vpc"}
        }
    }
    context = ProviderContext.from_tfdata(tfdata)
    self.assertEqual(context.provider, "your_provider")

def test_your_provider_resource_detection(self):
    """Test YourProvider resource detection from address."""
    detector = ProviderDetector()
    provider = detector._detect_from_resources({
        "your_provider_vm.web": {}
    })
    self.assertEqual(provider, "your_provider")
```

### Step 6: Run Tests

```bash
# Run unit tests
poetry run pytest tests/helpers_unit_test.py::TestMultiProviderIntegration -v

# Run performance tests
poetry run pytest tests/performance_test.py -v

# Run all non-slow tests
poetry run pytest -m "not slow" -v
```

### Step 7: Create Icon Classes (Optional)

If you need custom icons, create them at:
```
resource_classes/your_provider/__init__.py
resource_classes/your_provider/compute.py
resource_classes/your_provider/network.py
resource_classes/your_provider/database.py
# etc.
```

Example icon class:
```python
from diagrams.your_provider.compute import VM

class YourProviderVM(VM):
    """Your Provider Virtual Machine icon."""
    pass
```

---

## Provider Configuration Reference

### Required Constants

| Constant | Type | Required | Description |
|----------|------|----------|-------------|
| `CONSOLIDATED_NODES` | List[Dict] | Yes | Multi-resource consolidations |
| `GROUP_NODES` | List[str] | Yes | Container resources (drawn as subgraphs) |
| `EDGE_NODES` | List[str] | Yes | Network edge services |
| `OUTER_NODES` | List[str] | Yes | External entities (users, internet) |
| `DRAW_ORDER` | List | Yes | Rendering layer order |
| `NODE_VARIANTS` | Dict | No | Resource variant mappings |
| `AUTO_ANNOTATIONS` | List[Dict] | No | Automatic edge creation rules |
| `REVERSE_ARROW_LIST` | List[str] | No | Resources with reversed arrows |
| `FORCED_DEST` | List[str] | No | Resources as forced destinations |
| `FORCED_ORIGIN` | List[str] | No | Resources as forced origins |
| `IMPLIED_CONNECTIONS` | Dict | No | Metadata-based connections |
| `SPECIAL_RESOURCES` | Dict | No | Handler function mappings |
| `SHARED_SERVICES` | List[str] | No | Cross-VPC accessible services |
| `ALWAYS_DRAW_LINE` | List[str] | No | Always show connections |
| `NEVER_DRAW_LINE` | List[str] | No | Never show connections |
| `DISCONNECT_LIST` | List[str] | No | Resources to exclude from graph |
| `ACRONYMS_LIST` | List[str] | No | Acronyms for styling |
| `NAME_REPLACEMENTS` | Dict | No | Name substitutions for labels |

### Consolidated Nodes Structure

```python
{
    "base_resource_pattern": {
        "resource_name": "default_name_format",
        "import_location": "resource_classes.provider.category",
        "vpc": True/False,          # Inside VPC boundary?
        "edge_service": True/False  # At network edge?
    }
}
```

### Auto-Annotations Structure

```python
{
    "resource_type": {
        "link": ["target_pattern_1", "target_pattern_2"],  # Supports wildcards
        "arrow": "forward" or "reverse"
    }
}
```

---

## Testing Requirements

### Minimum Test Coverage

1. **Provider Detection Test**: Verify provider is detected from resource addresses
2. **Resource Detection Test**: Verify resources are correctly identified
3. **Configuration Loading Test**: Verify config module loads without errors
4. **Performance Test**: Verify detection completes in < 1ms

### Test Checklist

- [ ] Provider detection from Terraform JSON
- [ ] Provider detection from resource addresses
- [ ] Configuration constants are valid
- [ ] No import errors in configuration module
- [ ] Provider registry contains new provider
- [ ] Integration test with sample Terraform JSON
- [ ] Performance meets targets (< 1ms detection)

---

## Best Practices

### 1. Start Minimal, Expand Iteratively

**Phase 1: Minimum Viable Provider (2-4 hours)**
- Define `CONSOLIDATED_NODES`, `GROUP_NODES`, `EDGE_NODES`, `OUTER_NODES`, `DRAW_ORDER`
- Register provider in runtime
- Add basic detection logic
- Create 1-2 test cases

**Phase 2: Enhanced Configuration (4-8 hours)**
- Add `NODE_VARIANTS` for common resource types
- Add `AUTO_ANNOTATIONS` for typical connection patterns
- Expand test coverage to 5+ test cases
- Add performance tests

**Phase 3: Advanced Features (Optional, 8+ hours)**
- Implement `SPECIAL_RESOURCES` handlers
- Add comprehensive variant mappings (10+ types)
- Create custom icon classes
- Add integration tests with real Terraform code

### 2. Study Existing Providers

Use Azure and GCP configs as templates:
- **Azure config** (`modules/cloud_config/azure.py`): 303 lines, 12 consolidations, 10 variants
- **GCP config** (`modules/cloud_config/gcp.py`): 398 lines, 12 consolidations, 9 variants

### 3. Document Inline

Add comprehensive comments explaining:
- Why resources are consolidated
- Variant mapping logic (SKU, tier, size patterns)
- Auto-annotation rules and their purpose
- Special cases or exceptions

### 4. Performance Targets

Your provider config should meet these performance targets:
- **Provider detection:** < 0.1ms (target: 0.02ms)
- **Config loading:** < 1ms (target: 0.4ms)
- **Variant checking:** < 0.001ms per resource (target: 0.0002ms)

Run performance tests:
```bash
poetry run pytest tests/performance_test.py::TestProviderPerformance -v
```

### 5. Backward Compatibility

- Don't modify existing AWS config unless absolutely necessary
- Ensure changes don't break existing tests (87 tests must pass)
- Maintain 100% backward compatibility for AWS users

---

## Examples from Existing Providers

### Example 1: Azure Load Balancer Consolidation

```python
# Consolidates LB + backend pools + probes + rules into single node
{
    "azurerm_lb": {
        "resource_name": "azurerm_lb.load_balancer",
        "import_location": "resource_classes.azure.network",
        "vpc": True,  # Operates within VNet
    }
}
```

### Example 2: GCP Storage Variants

```python
# Maps storage classes to variant icons
"google_storage_bucket": {
    "STANDARD": "google_storage_standard",    # Hot data
    "NEARLINE": "google_storage_nearline",    # 30-day min
    "COLDLINE": "google_storage_coldline",    # 90-day min
    "ARCHIVE": "google_storage_archive",      # 365-day min
}
```

### Example 3: Azure Auto-Annotation

```python
# Front Door automatically connects to internet
{
    "azurerm_frontdoor": {
        "link": ["tv_azure_internet.internet"],
        "arrow": "reverse",  # Internet → Front Door
    }
}
```

---

## Troubleshooting

### Provider Not Detected

**Symptom:** Provider defaults to AWS instead of your provider

**Solution:**
1. Check resource prefix pattern in `ProviderDetector._detect_from_resources`
2. Verify Terraform JSON has `provider_name` field
3. Add debug logging: `print(f"Detected provider: {provider}")`

### Configuration Not Loading

**Symptom:** `AttributeError: module has no attribute 'CONSOLIDATED_NODES'`

**Solution:**
1. Verify all required constants are defined
2. Check for Python syntax errors: `poetry run python -m py_compile modules/cloud_config/YOUR_PROVIDER.py`
3. Ensure module is imported in `provider_runtime.py`

### Tests Failing

**Symptom:** Provider detection tests fail

**Solution:**
1. Run with verbose output: `poetry run pytest tests/helpers_unit_test.py -v -s`
2. Check tfdata structure matches expected format
3. Verify provider ID matches registry key

---

## Getting Help

- **Architecture Documentation:** See [ARCHITECTURAL.md](ARCHITECTURAL.md) for system design
- **Code Review:** See [CODEREVIEW.md](CODEREVIEW.md) for Phase 6 implementation review
- **Existing Providers:** Reference `modules/cloud_config/azure.py` and `gcp.py`

---

## Summary Checklist

Before submitting your provider implementation:

- [ ] Provider configuration module created (`modules/cloud_config/YOUR_PROVIDER.py`)
- [ ] All required constants defined
- [ ] Provider registered in `ProviderRegistry`
- [ ] Detection logic added to `ProviderDetector`
- [ ] Test fixtures created (`tests/json/your_provider-basic-tfdata.json`)
- [ ] Unit tests added (minimum 2 tests)
- [ ] All existing tests still pass (87 tests)
- [ ] Performance targets met (< 1ms)
- [ ] Inline documentation complete
- [ ] README.md updated with provider support status

**Estimated Time:** 2-4 hours for basic support, 8-16 hours for complete implementation

---

**Document Version:** 1.0  
**Last Updated:** December 2024  
**Compatible with:** TerraVision v0.8+
