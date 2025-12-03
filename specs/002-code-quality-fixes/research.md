# Research: Code Quality and Reliability Improvements

**Feature**: Code Quality and Reliability Improvements  
**Date**: 2025-12-01  
**Status**: Complete

## Overview

This document consolidates research findings for implementing fixes identified in docs/TO_BE_FIXED.md. Research covers exception handling patterns, Azure/GCP resource relationship patterns, module organization strategies, test patterns, and performance optimization approaches.

---

## 1. Exception Handling Best Practices for Library Code

### Decision: Custom Exceptions + CLI Error Handler Pattern

**Rationale**:
- Library code (modules/*) should raise specific exceptions with context
- CLI layer (terravision.py) catches and formats user-friendly messages
- Enables programmatic use of modules without forcing sys.exit()
- Follows Click framework patterns and Python best practices

**Pattern**:
```python
# modules/exceptions.py (NEW)
class TerraVisionError(Exception):
    """Base exception for TerraVision errors."""
    pass

class MissingResourceError(TerraVisionError):
    """Required resource not found in Terraform data."""
    pass

class ProviderDetectionError(TerraVisionError):
    """Cannot detect provider from resource names."""
    pass

# modules/resource_handlers/aws.py
def aws_handle_vpcendpoints(tfdata):
    vpcs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_vpc.")
    if not vpcs:
        raise MissingResourceError("No VPC found; cannot process VPC endpoints")
    # ... rest of logic

# terravision.py (CLI layer)
@click.command()
def draw(...):
    try:
        tfdata = process_terraform(...)
    except MissingResourceError as e:
        click.echo(click.style(f"INFO: {e}", fg="yellow"))
        # Continue with partial diagram
    except TerraVisionError as e:
        click.echo(click.style(f"ERROR: {e}", fg="red", bold=True))
        sys.exit(1)
```

**Alternatives Considered**:
- **Return error tuples**: Rejected - requires every caller to check return values
- **Logging only**: Rejected - doesn't provide control flow for CLI to decide severity
- **Keep sys.exit() in library**: Rejected - makes modules unusable as libraries

**Implementation Notes**:
- Replace bare `except:` with `except (KeyError, TypeError, StopIteration) as e:`
- Add logging with context: `click.echo(click.style(f"Skipping {resource}: {e}", fg="yellow"))`
- Document expected exceptions in function docstrings

---

## 2. Azure Resource Handler Patterns

### Decision: Follow AWS Handler Structure with Azure-Specific Adaptations

**Rationale**:
- AWS handlers in modules/resource_handlers/aws.py provide proven patterns
- Azure networking concepts map closely to AWS (VNet↔VPC, NSG↔Security Group)
- Reusing helper functions (list_of_dictkeys_containing) maintains consistency
- Provider-specific differences isolated in handler implementation details

**Azure VNet/Subnet Grouping Pattern**:
```python
def azure_handle_vnet_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group Azure subnets under parent VNets based on metadata or naming."""
    vnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_virtual_network")
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_subnet")
    
    if not vnets:
        raise MissingResourceError("No Azure VNets found")
    
    # Azure-specific: subnets reference parent VNet via virtual_network_name
    for subnet in subnets:
        subnet_meta = tfdata["metadata"].get(subnet, {})
        vnet_name = subnet_meta.get("virtual_network_name") or subnet_meta.get("vnet_id")
        
        # Find matching VNet
        matching_vnet = next(
            (v for v in vnets if vnet_name in v),
            vnets[0]  # Default to first VNet if no match
        )
        
        # Add subnet as child of VNet
        tfdata["graphdict"][matching_vnet].append(subnet)
        del tfdata["graphdict"][subnet]
    
    return tfdata
```

**Azure NSG Pattern** (similar to AWS security groups with reversal):
```python
def azure_handle_nsg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse NSG connections so NSGs wrap resources instead of being children."""
    nsgs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_network_security_group")
    
    for nsg in nsgs:
        # Get resources that reference this NSG
        nsg_associations = helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], "azurerm_network_interface_security_group_association"
        )
        
        # Reverse: NSG contains resources, not vice versa
        for assoc in nsg_associations:
            # Extract NIC reference from association
            # Move NIC under NSG in graph
            # Similar to AWS sg_reversal logic
            pass
    
    return tfdata
```

**Azure Load Balancer Types**:
```python
def azure_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect Azure LB SKU and set appropriate icon."""
    lbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_lb")
    
    for lb in lbs:
        lb_meta = tfdata["metadata"].get(lb, {})
        sku = lb_meta.get("sku", "Basic")  # Basic or Standard
        
        # Update node attributes for icon selection
        tfdata["metadata"][lb]["azure_lb_type"] = sku.lower()
        
        # Process backend pools
        backend_pools = helpers.list_of_dictkeys_containing(
            tfdata["graphdict"], f"azurerm_lb_backend_address_pool.{lb_name}"
        )
        # Link backend pools to LB
    
    return tfdata
```

**Alternatives Considered**:
- **Terraform metadata parsing**: Rejected - too fragile, prefers graph relationships
- **Separate Azure module structure**: Rejected - increases complexity, violates DRY
- **Hard-coded Azure assumptions in core**: Rejected - violates multi-provider principle

**Reference Resources**:
- Azure Terraform provider docs: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
- AWS handler implementations: modules/resource_handlers/aws.py lines 100-750
- Existing Azure stubs: modules/resource_handlers/azure.py

---

## 3. GCP Resource Handler Patterns

### Decision: Adapt AWS Patterns with GCP Architectural Differences

**Rationale**:
- GCP networking differs more from AWS than Azure does (regional subnets, global VPC)
- Firewall rules use target tags instead of security groups
- Load balancers composed of multiple resources (backend services, forwarding rules, URL maps)

**GCP VPC Network/Subnet Pattern**:
```python
def gcp_handle_network_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group GCP subnets under parent VPC networks.
    
    Note: GCP subnets are regional (not zonal) and can span multiple AZs.
    """
    networks = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "google_compute_network")
    subnets = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "google_compute_subnetwork")
    
    if not networks:
        raise MissingResourceError("No GCP networks found")
    
    # GCP subnets reference network via 'network' attribute
    for subnet in subnets:
        subnet_meta = tfdata["metadata"].get(subnet, {})
        network_ref = subnet_meta.get("network")
        
        # Match by network name or ID
        matching_network = next(
            (n for n in networks if network_ref in n),
            networks[0]
        )
        
        tfdata["graphdict"][matching_network].append(subnet)
        del tfdata["graphdict"][subnet]
    
    return tfdata
```

**GCP Firewall Rules** (different pattern - no wrapping):
```python
def gcp_handle_firewall(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process GCP firewall rules with target tags.
    
    Unlike AWS/Azure security groups, GCP firewalls are network-level resources
    that use target tags to apply to instances.
    """
    firewalls = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "google_compute_firewall")
    
    for firewall in firewalls:
        fw_meta = tfdata["metadata"].get(firewall, {})
        direction = fw_meta.get("direction", "INGRESS")  # INGRESS or EGRESS
        target_tags = fw_meta.get("target_tags", [])
        
        # Add direction to node label
        tfdata["metadata"][firewall]["display_direction"] = direction
        
        # Create edges to instances with matching tags
        # (More complex - requires instance tag lookup)
    
    return tfdata
```

**GCP Load Balancer Detection**:
```python
def gcp_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect GCP LB type from backend service configuration.
    
    GCP LBs are composite resources:
    - HTTP(S): forwarding_rule → target_http_proxy → url_map → backend_service
    - TCP/SSL: forwarding_rule → target_tcp_proxy → backend_service
    - Internal: forwarding_rule → backend_service (regional)
    """
    backend_services = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "google_compute_backend_service"
    )
    
    for backend in backend_services:
        backend_meta = tfdata["metadata"].get(backend, {})
        
        # Detect LB type from protocol and load balancing scheme
        protocol = backend_meta.get("protocol", "HTTP")
        lb_scheme = backend_meta.get("load_balancing_scheme", "EXTERNAL")
        
        if protocol in ["HTTP", "HTTPS"]:
            lb_type = "http_lb"
        elif lb_scheme == "INTERNAL":
            lb_type = "internal_lb"
        else:
            lb_type = "network_lb"
        
        tfdata["metadata"][backend]["gcp_lb_type"] = lb_type
    
    return tfdata
```

**Alternatives Considered**:
- **Treat GCP firewalls like security groups**: Rejected - architecture too different
- **Composite LB resource**: Rejected - graph shows individual components for accuracy
- **Global vs regional handling**: Deferred - initial implementation treats all as resources

**Reference Resources**:
- GCP Terraform provider: https://registry.terraform.io/providers/hashicorp/google/latest/docs
- GCP VPC architecture: https://cloud.google.com/vpc/docs/vpc
- GCP load balancing: https://cloud.google.com/load-balancing/docs/load-balancing-overview

---

## 4. Module Organization Strategy (Splitting helpers.py)

### Decision: Create Focused Utility Modules with Backward-Compatible Imports

**Rationale**:
- helpers.py is 1100+ lines with mixed concerns (string parsing, Terraform ops, graph utils)
- Splitting improves discoverability and testability
- Backward compatibility prevents breaking existing code during transition

**Proposed Structure**:
```text
modules/
├── helpers.py              # DEPRECATED: re-exports for backward compatibility
├── utils/
│   ├── __init__.py         # Re-export all utilities
│   ├── string_utils.py     # find_between, find_nth, text parsing
│   ├── terraform_utils.py  # getvar, tfvar_read, Terraform-specific parsing
│   ├── graph_utils.py      # list_of_dictkeys_containing, graph operations
│   └── provider_utils.py   # Provider detection, resource type parsing
```

**Migration Pattern**:
```python
# modules/utils/string_utils.py
def find_between(text: str, begin: str, end: str, ...) -> str:
    """Extract text between delimiters."""
    # Implementation moved from helpers.py

# modules/utils/__init__.py
from .string_utils import find_between, find_nth
from .terraform_utils import getvar, tfvar_read
from .graph_utils import list_of_dictkeys_containing
from .provider_utils import detect_provider

# Export all for convenience
__all__ = ['find_between', 'find_nth', 'getvar', ...]

# modules/helpers.py (backward compatibility shim)
"""DEPRECATED: Use modules.utils.* instead.

Maintained for backward compatibility during transition.
"""
from modules.utils import *

import warnings
warnings.warn(
    "modules.helpers is deprecated. Use modules.utils.* instead.",
    DeprecationWarning,
    stacklevel=2
)
```

**Phased Approach**:
1. **Phase 1**: Create new utils/ modules, populate with functions
2. **Phase 2**: Update helpers.py to re-export with deprecation warnings
3. **Phase 3**: Migrate internal code to use utils.* imports
4. **Phase 4**: (Future) Remove helpers.py after deprecation period

**Alternatives Considered**:
- **Single large refactor**: Rejected - too risky, hard to review
- **Keep helpers.py monolithic**: Rejected - maintainability issues persist
- **Create new namespace entirely**: Rejected - breaks too much existing code

**Implementation Notes**:
- Use type hints in all new utility functions
- Add comprehensive docstrings with Args/Returns sections
- Create unit tests for each utils module independently

---

## 5. Test Coverage Strategy

### Decision: Comprehensive Unit Tests + Integration Tests with Slow Markers

**Rationale**:
- Current tests focus on integration; need granular unit tests for handlers
- AWS handlers (aws.py 39KB) have complex logic without test coverage
- Pytest slow markers enable fast feedback loop (constitution requirement)

**Test Structure**:
```text
tests/
├── unit/                           # NEW: Fast, focused unit tests
│   ├── test_aws_handlers.py        # AWS handler transformations
│   │   ├── TestHandleVPCEndpoints
│   │   ├── TestHandleAutoscaling
│   │   ├── TestHandleSecurityGroups
│   │   ├── TestHandleLoadBalancers
│   │   └── TestHandleNATGateways
│   ├── test_azure_handlers.py      # Azure handler tests
│   ├── test_gcp_handlers.py        # GCP handler tests
│   ├── test_string_utils.py        # String parsing utilities
│   ├── test_terraform_utils.py     # Terraform variable resolution
│   ├── test_graph_utils.py         # Graph operations
│   └── test_provider_utils.py      # Provider detection
├── integration/                     # Existing + new integration tests
│   ├── test_multicloud.py          # NEW: Mixed AWS/Azure/GCP configs
│   └── test_end_to_end.py          # Full pipeline tests (marked slow)
├── fixtures/                        # NEW: Shared test data
│   ├── tfdata_samples.py           # Sample tfdata structures
│   ├── aws_configs/                # Terraform config snippets
│   ├── azure_configs/
│   └── gcp_configs/
└── [existing test files]            # Keep existing tests
```

**Test Pattern for Handlers**:
```python
# tests/unit/test_aws_handlers.py
import pytest
from modules.resource_handlers.aws import aws_handle_vpcendpoints
from modules.exceptions import MissingResourceError
from tests.fixtures.tfdata_samples import minimal_tfdata, vpc_tfdata

class TestHandleVPCEndpoints:
    """Unit tests for aws_handle_vpcendpoints handler."""
    
    def test_no_vpc_raises_error(self):
        """Should raise MissingResourceError when no VPC exists."""
        tfdata = minimal_tfdata()  # No VPC
        with pytest.raises(MissingResourceError, match="No VPC found"):
            aws_handle_vpcendpoints(tfdata)
    
    def test_groups_endpoints_under_vpc(self):
        """Should move VPC endpoints under parent VPC."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=2)
        result = aws_handle_vpcendpoints(tfdata)
        
        vpc_key = "aws_vpc.main"
        assert vpc_key in result["graphdict"]
        assert "aws_vpc_endpoint.s3" in result["graphdict"][vpc_key]
        assert "aws_vpc_endpoint.s3" not in result["graphdict"]
    
    def test_preserves_metadata(self):
        """Should maintain metadata for moved endpoints."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=1)
        original_meta = tfdata["metadata"]["aws_vpc_endpoint.s3"].copy()
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert result["metadata"]["aws_vpc_endpoint.s3"] == original_meta
```

**Fixture Pattern**:
```python
# tests/fixtures/tfdata_samples.py
def minimal_tfdata() -> Dict[str, Any]:
    """Return minimal valid tfdata structure."""
    return {
        "graphdict": {},
        "metadata": {},
        "all_resource": [],
        "annotations": {}
    }

def vpc_tfdata(vpc_count=1, endpoint_count=0, subnet_count=0) -> Dict[str, Any]:
    """Return tfdata with VPC resources."""
    tfdata = minimal_tfdata()
    
    for i in range(vpc_count):
        vpc_key = f"aws_vpc.vpc{i}"
        tfdata["graphdict"][vpc_key] = []
        tfdata["metadata"][vpc_key] = {"count": "1", "provider": "aws"}
    
    for i in range(endpoint_count):
        ep_key = f"aws_vpc_endpoint.ep{i}"
        tfdata["graphdict"][ep_key] = []
        tfdata["metadata"][ep_key] = {"count": "1", "vpc_id": "aws_vpc.vpc0"}
    
    return tfdata
```

**Alternatives Considered**:
- **Only integration tests**: Rejected - too slow, poor failure localization
- **Mock-heavy unit tests**: Rejected - fragile to implementation changes
- **Snapshot testing**: Deferred - useful for graph outputs, not for logic testing

**Implementation Notes**:
- Run unit tests in pre-commit hooks (fast)
- Run integration tests in CI only (marked @pytest.mark.slow)
- Target 80%+ code coverage for resource handlers
- Use pytest parametrize for edge case variations

---

## 6. Performance Optimization Approaches

### Decision: Indexed Lookups + Caching for find_common_elements

**Rationale**:
- Current O(n²×m) nested loops cause slowdowns on 100+ resource configs
- Set-based operations provide O(n×m) performance with same correctness
- Caching sorted results prevents repeated sorting in loops

**Optimized Pattern**:
```python
# modules/utils/graph_utils.py (from helpers.py)
def find_common_elements(list1: List[str], list2: List[str]) -> List[str]:
    """Find common elements between two lists efficiently.
    
    Optimized with set intersection instead of nested loops.
    
    Args:
        list1: First list of strings
        list2: Second list of strings
    
    Returns:
        Sorted list of common elements
    
    Performance:
        O(n+m) using set intersection vs O(n×m) nested loops
    """
    # Convert to sets for O(1) lookup
    set1 = set(list1)
    set2 = set(list2)
    
    # Set intersection is O(min(len(set1), len(set2)))
    common = set1 & set2
    
    # Return sorted for deterministic output
    return sorted(common)

# Before (O(n²×m)):
# common = []
# for item1 in list1:
#     for item2 in list2:
#         if item1 == item2 and item1 not in common:
#             common.append(item1)
# return sorted(common)
```

**Caching Pattern for Repeated Sorts**:
```python
# modules/resource_handlers/aws.py (example from sg handling)
def aws_handle_sg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle security groups with cached sorting."""
    sgs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_security_group")
    
    # Cache sorted list outside loop (only sort once)
    sorted_graphdict_keys = sorted(tfdata["graphdict"].keys())
    
    for sg in sgs:
        # Use cached sorted keys instead of sorting in each iteration
        for key in sorted_graphdict_keys:
            if sg in tfdata["graphdict"][key]:
                # Process...
                pass
    
    return tfdata
```

**Benchmark Targets**:
- 100 resources: < 2 seconds (currently ~5-8 seconds)
- 500 resources: < 10 seconds
- 30% overall improvement minimum

**Alternatives Considered**:
- **Parallel processing**: Rejected - adds complexity, graph operations are sequential
- **C extension for parsing**: Rejected - violates simplicity principle
- **Lazy evaluation**: Deferred - requires architectural changes

**Implementation Notes**:
- Add performance tests with 100/500 resource fixtures
- Measure before/after with pytest-benchmark
- Document performance characteristics in docstrings

---

## 7. ProviderRegistry Migration

### Decision: Use Existing ProviderRegistry, Deprecate cloud_config Constants

**Rationale**:
- ProviderRegistry already implemented in modules/cloud_config/common.py
- Provides centralized provider-specific configuration access
- Eliminates hard-coded AWS assumptions spread across codebase

**Migration Pattern**:
```python
# OLD (deprecated):
from modules.cloud_config import AWS_CONSOLIDATED_NODES

if resource_type in AWS_CONSOLIDATED_NODES:
    # ...

# NEW:
from modules.cloud_config import ProviderRegistry

registry = ProviderRegistry()
provider_config = registry.get_provider("aws")

if resource_type in provider_config.consolidated_nodes:
    # ...
```

**Affected Modules**:
- modules/graphmaker.py line 19 (TODO comment references this)
- modules/drawing.py (icon path lookups)
- modules/service_mapping.py (resource type mappings)
- modules/resource_handlers/*.py (provider detection)

**Alternatives Considered**:
- **Keep cloud_config.py constants**: Rejected - violates multi-provider architecture
- **New configuration system**: Rejected - ProviderRegistry already exists

---

## 8. Error Handling and Logging Guidelines

### Decision: Structured Severity Levels with Click Styling

**Severity Levels**:
- **INFO** (yellow): Expected conditions (skipping, defaulting to AWS provider)
- **WARNING** (yellow, bold): Unusual but recoverable (missing metadata, partial data)
- **ERROR** (red, bold): Fatal errors requiring user action

**Pattern**:
```python
import click

# INFO: Expected informational message
click.echo(click.style("INFO: No VPC found; skipping VPC endpoints", fg="yellow"))

# WARNING: Unusual condition
click.echo(click.style("WARNING: Provider detection defaulted to AWS", fg="yellow", bold=True))

# ERROR: Fatal condition
click.echo(click.style("ERROR: Invalid Terraform configuration", fg="red", bold=True))
sys.exit(1)  # Only in CLI layer
```

**Documentation Location**: docs/CONTRIBUTING.md (to be created)

---

## Summary of Key Decisions

| Decision Area | Chosen Approach | Rationale |
|---------------|-----------------|-----------|
| Exception Handling | Custom exceptions + CLI handler | Library reusability, follows Click patterns |
| Azure Handlers | Follow AWS patterns with adaptations | Proven structure, similar concepts |
| GCP Handlers | Adapt AWS with architectural differences | Different networking model requires variation |
| Module Organization | Split helpers.py with backward compat | Improves discoverability without breaking code |
| Test Strategy | Unit tests + integration with slow markers | Fast feedback, comprehensive coverage |
| Performance | Set-based operations + caching | O(n×m) instead of O(n²×m), measurable gains |
| Provider Config | Use existing ProviderRegistry | Already implemented, removes hard-coding |
| Error Logging | Structured severity with Click styling | User-friendly, consistent across CLI |

All decisions align with TerraVision Constitution principles (client-side security, multi-provider architecture, testability, simplicity).

---

## Next Steps

Phase 1 outputs:
1. **data-model.md**: Define exception types, handler interfaces, test structures
2. **contracts/**: API contracts for new utilities, handlers, and test fixtures
3. **quickstart.md**: Developer onboarding for contributing fixes
4. **Update AGENTS.md**: Add new testing patterns and module structure

Research complete. All unknowns resolved. Ready for Phase 1 design.
