# Data Model: Code Quality and Reliability Improvements

**Feature**: Code Quality and Reliability Improvements  
**Date**: 2025-12-01  
**Status**: Complete

## Overview

This document defines the key entities, data structures, and interfaces for implementing code quality fixes. Covers custom exception types, handler function signatures, utility module interfaces, test fixture structures, and metadata schemas.

---

## 1. Exception Types

### Base Exception

```python
class TerraVisionError(Exception):
    """Base exception for all TerraVision errors.
    
    Attributes:
        message: Human-readable error description
        context: Optional dict with additional error context
    """
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)
```

### Specific Exception Types

```python
class MissingResourceError(TerraVisionError):
    """Required resource not found in Terraform data.
    
    Raised when handlers expect resources (e.g., VPC) that don't exist.
    
    Attributes:
        resource_type: Type of missing resource (e.g., 'aws_vpc')
        required_by: Handler or operation requiring the resource
    """
    def __init__(self, message: str, resource_type: str, required_by: str):
        super().__init__(message, {"resource_type": resource_type, "required_by": required_by})
        self.resource_type = resource_type
        self.required_by = required_by


class ProviderDetectionError(TerraVisionError):
    """Cannot detect cloud provider from resource names.
    
    Raised when provider cannot be inferred from Terraform resource types.
    
    Attributes:
        sample_resources: List of resource names that failed detection
    """
    def __init__(self, message: str, sample_resources: List[str]):
        super().__init__(message, {"sample_resources": sample_resources})
        self.sample_resources = sample_resources


class MetadataInconsistencyError(TerraVisionError):
    """Graph node created without corresponding metadata entry.
    
    Raised when tfdata["graphdict"] and tfdata["metadata"] are out of sync.
    
    Attributes:
        node_key: Graph node key that's missing metadata
        operation: Operation that created the inconsistency
    """
    def __init__(self, message: str, node_key: str, operation: str):
        super().__init__(message, {"node_key": node_key, "operation": operation})
        self.node_key = node_key
        self.operation = operation


class TerraformParsingError(TerraVisionError):
    """Failed to parse Terraform configuration or state.
    
    Raised when HCL2 parsing, JSON loading, or variable resolution fails.
    
    Attributes:
        file_path: Path to file that failed parsing
        parse_error: Original parsing error message
    """
    def __init__(self, message: str, file_path: str, parse_error: str):
        super().__init__(message, {"file_path": file_path, "parse_error": parse_error})
        self.file_path = file_path
        self.parse_error = parse_error
```

**Relationships**:
- All exceptions inherit from `TerraVisionError`
- CLI layer catches specific types for different user messages
- Library code raises exceptions; CLI formats and displays

---

## 2. Handler Function Signatures

### Standard Handler Interface

All resource handlers follow this interface:

```python
from typing import Dict, Any

def {provider}_handle_{resource_type}(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle {provider} {resource_type} transformations.
    
    Args:
        tfdata: Terraform data dictionary with keys:
            - graphdict: Dict[str, List[str]] - adjacency list graph
            - metadata: Dict[str, Dict[str, Any]] - node metadata
            - all_resource: List[str] - all resource names
            - annotations: Dict[str, Any] - YAML annotations
    
    Returns:
        Updated tfdata with transformations applied
    
    Raises:
        MissingResourceError: If required parent resources don't exist
        MetadataInconsistencyError: If metadata is missing or invalid
    
    Example:
        >>> tfdata = {"graphdict": {...}, "metadata": {...}}
        >>> result = aws_handle_vpcendpoints(tfdata)
        >>> assert "aws_vpc.main" in result["graphdict"]
    """
    # Validation
    resources = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "resource_pattern")
    
    if not resources:
        raise MissingResourceError(
            "No {resource} found",
            resource_type="{resource_pattern}",
            required_by="{provider}_handle_{resource_type}"
        )
    
    # Transformation logic
    for resource in resources:
        # Modify graphdict
        # Ensure metadata exists for new nodes
        if new_node_key not in tfdata["metadata"]:
            tfdata["metadata"][new_node_key] = initialize_metadata(...)
    
    return tfdata
```

### Handler Categories

**Grouping Handlers** (parent-child relationships):
- `aws_handle_vpcendpoints`: Group endpoints under VPCs
- `azure_handle_vnet_subnets`: Group subnets under VNets
- `gcp_handle_network_subnets`: Group subnets under VPC networks

**Reversal Handlers** (reverse connections):
- `aws_handle_sg`: Reverse security group connections
- `azure_handle_nsg`: Reverse NSG connections
- `gcp_handle_firewall`: Process firewall rule targets

**Type Detection Handlers** (classify variants):
- `aws_handle_loadbalancer`: Detect ALB/NLB/CLB
- `azure_handle_lb`: Detect Basic/Standard LB SKU
- `gcp_handle_lb`: Detect HTTP(S)/TCP/Internal LB

---

## 3. Utility Module Interfaces

### String Utilities (`modules/utils/string_utils.py`)

```python
def find_between(
    text: str,
    begin: str,
    end: str,
    alternative: str = "",
    replace: bool = False,
    occurrence: int = 1
) -> str:
    """Extract text between two delimiters.
    
    Handles nested delimiters correctly using stack-based parsing.
    
    Args:
        text: Source text to search
        begin: Starting delimiter
        end: Ending delimiter
        alternative: Replacement text if replace=True
        replace: If True, replace extracted text with alternative
        occurrence: Which occurrence to extract (1-indexed)
    
    Returns:
        Extracted text between delimiters, or empty string if not found
    
    Performance:
        O(n) where n is length of text
    """
    pass


def find_nth(text: str, substring: str, n: int) -> int:
    """Find index of nth occurrence of substring.
    
    Args:
        text: Text to search
        substring: Substring to find
        n: Which occurrence (1-indexed)
    
    Returns:
        Index of nth occurrence, or -1 if not found
    """
    pass
```

### Terraform Utilities (`modules/utils/terraform_utils.py`)

```python
def getvar(
    obj: Union[Dict, List],
    path: str,
    default: Any = None
) -> Any:
    """Get nested value from Terraform data structure.
    
    Supports dot notation for nested dicts and bracket notation for lists.
    
    Args:
        obj: Dict or list to search
        path: Dot-separated path (e.g., "resource.aws_vpc.main.cidr_block")
        default: Default value if path not found
    
    Returns:
        Value at path, or default if not found
    
    Raises:
        TerraformParsingError: If path syntax is invalid
    
    Example:
        >>> data = {"resource": {"aws_vpc": {"main": {"cidr_block": "10.0.0.0/16"}}}}
        >>> getvar(data, "resource.aws_vpc.main.cidr_block")
        '10.0.0.0/16'
    """
    pass


def tfvar_read(tfvars_path: str) -> Dict[str, Any]:
    """Read and parse Terraform .tfvars file.
    
    Args:
        tfvars_path: Path to .tfvars file
    
    Returns:
        Dict of variable name to value mappings
    
    Raises:
        TerraformParsingError: If file cannot be parsed
    """
    pass
```

### Graph Utilities (`modules/utils/graph_utils.py`)

```python
def list_of_dictkeys_containing(
    graphdict: Dict[str, List[str]],
    pattern: str
) -> List[str]:
    """Find all graph node keys containing pattern.
    
    Args:
        graphdict: Graph adjacency list
        pattern: Substring to match in keys
    
    Returns:
        List of matching keys
    
    Example:
        >>> graphdict = {"aws_vpc.main": [], "aws_subnet.private": []}
        >>> list_of_dictkeys_containing(graphdict, "aws_vpc")
        ['aws_vpc.main']
    """
    pass


def find_common_elements(list1: List[str], list2: List[str]) -> List[str]:
    """Find common elements between two lists efficiently.
    
    Uses set intersection for O(n+m) performance.
    
    Args:
        list1: First list
        list2: Second list
    
    Returns:
        Sorted list of common elements
    
    Performance:
        O(n+m) where n=len(list1), m=len(list2)
        Previously O(n*m) with nested loops
    """
    pass


def ensure_metadata(
    tfdata: Dict[str, Any],
    node_key: str,
    defaults: Optional[Dict[str, Any]] = None
) -> None:
    """Ensure metadata entry exists for graph node.
    
    Creates metadata entry if missing, using defaults or empty dict.
    
    Args:
        tfdata: Terraform data dictionary
        node_key: Graph node key to check
        defaults: Default metadata values
    
    Raises:
        MetadataInconsistencyError: If node exists in graphdict but not metadata
    
    Side Effects:
        Modifies tfdata["metadata"] in place
    """
    pass
```

### Provider Utilities (`modules/utils/provider_utils.py`)

```python
def detect_provider(resource_names: List[str]) -> str:
    """Detect cloud provider from Terraform resource names.
    
    Args:
        resource_names: List of Terraform resource identifiers
    
    Returns:
        Provider name: 'aws', 'azure', 'gcp', or 'unknown'
    
    Raises:
        ProviderDetectionError: If provider cannot be determined
    
    Logic:
        - 'aws_*' → 'aws'
        - 'azurerm_*' → 'azure'
        - 'google_*' → 'gcp'
        - Mixed providers → raise error
        - No matches → 'unknown'
    """
    pass


def get_provider_config(provider: str) -> ProviderConfig:
    """Get provider-specific configuration from ProviderRegistry.
    
    Args:
        provider: Provider name ('aws', 'azure', 'gcp')
    
    Returns:
        ProviderConfig with consolidated_nodes, icon_paths, etc.
    
    Example:
        >>> config = get_provider_config('aws')
        >>> print(config.consolidated_nodes)
        ['aws_security_group', 'aws_vpc', ...]
    """
    pass
```

---

## 4. Test Fixture Structures

### Minimal TFData Fixture

```python
def minimal_tfdata() -> Dict[str, Any]:
    """Create minimal valid tfdata structure.
    
    Returns:
        Dict with empty graphdict, metadata, all_resource, annotations
    """
    return {
        "graphdict": {},
        "metadata": {},
        "all_resource": [],
        "annotations": {}
    }
```

### VPC TFData Fixture (AWS)

```python
def vpc_tfdata(
    vpc_count: int = 1,
    subnet_count: int = 0,
    endpoint_count: int = 0,
    nat_gateway_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with AWS VPC resources.
    
    Args:
        vpc_count: Number of VPCs to create
        subnet_count: Number of subnets per VPC
        endpoint_count: Number of VPC endpoints
        nat_gateway_count: Number of NAT gateways
    
    Returns:
        tfdata with specified AWS resources
    
    Structure:
        graphdict:
            - aws_vpc.vpc{i}: [subnets, endpoints, nat_gateways]
            - aws_subnet.subnet{i}: []
            - aws_vpc_endpoint.ep{i}: []
            - aws_nat_gateway.nat{i}: []
        
        metadata:
            - Each resource has {"count": "1", "provider": "aws"}
            - Subnets have {"vpc_id": "aws_vpc.vpc0"}
            - Endpoints have {"vpc_id": "aws_vpc.vpc0"}
    """
    pass
```

### Azure VNet Fixture

```python
def vnet_tfdata(
    vnet_count: int = 1,
    subnet_count: int = 0,
    nsg_count: int = 0,
    lb_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with Azure VNet resources.
    
    Args:
        vnet_count: Number of VNets
        subnet_count: Number of subnets per VNet
        nsg_count: Number of NSGs
        lb_count: Number of load balancers
    
    Returns:
        tfdata with specified Azure resources
    """
    pass
```

### GCP VPC Fixture

```python
def gcp_network_tfdata(
    network_count: int = 1,
    subnet_count: int = 0,
    firewall_count: int = 0,
    lb_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with GCP VPC network resources.
    
    Args:
        network_count: Number of VPC networks
        subnet_count: Number of subnets per network
        firewall_count: Number of firewall rules
        lb_count: Number of backend services (LBs)
    
    Returns:
        tfdata with specified GCP resources
    """
    pass
```

### Multicloud Fixture

```python
def multicloud_tfdata(
    aws_vpcs: int = 1,
    azure_vnets: int = 1,
    gcp_networks: int = 1
) -> Dict[str, Any]:
    """Create tfdata with mixed provider resources.
    
    Args:
        aws_vpcs: Number of AWS VPCs
        azure_vnets: Number of Azure VNets
        gcp_networks: Number of GCP networks
    
    Returns:
        tfdata with resources from multiple providers
    
    Used For:
        Testing provider detection, mixed configurations, edge cases
    """
    pass
```

---

## 5. Metadata Schema

### Standard Metadata Structure

Every node in `tfdata["metadata"]` has this structure:

```python
{
    "node_key": {
        # Required fields
        "count": str,              # "1" or "3" for resource count
        "provider": str,           # "aws" | "azure" | "gcp" | "unknown"
        "type": str,               # Resource type (e.g., "aws_vpc")
        
        # Optional fields (resource-specific)
        "vpc_id": str,             # For VPC-dependent resources
        "network_id": str,         # For GCP network-dependent resources
        "vnet_id": str,            # For Azure VNet-dependent resources
        "sku": str,                # For Azure resources (Basic, Standard)
        "protocol": str,           # For GCP backend services (HTTP, HTTPS, TCP)
        "load_balancing_scheme": str,  # For GCP LBs (EXTERNAL, INTERNAL)
        "direction": str,          # For GCP firewalls (INGRESS, EGRESS)
        "target_tags": List[str],  # For GCP firewall targets
        
        # Display overrides (from annotations or handlers)
        "display_label": str,      # Custom label for diagram
        "display_icon": str,       # Custom icon path
        "display_direction": str,  # For directional resources (firewalls)
        
        # Internal tracking
        "original_key": str,       # If node was renamed/suffixed
        "consolidated": bool,      # If node is a consolidated group
    }
}
```

### Metadata Validation Rules

1. **Required Fields**: All nodes must have `count`, `provider`, `type`
2. **Consistency**: If node exists in `graphdict`, must exist in `metadata`
3. **Parent References**: VPC-dependent resources must have valid `vpc_id`
4. **Type Matching**: `type` field must match resource prefix (e.g., "aws_vpc" for aws_vpc.main)

### Metadata Helper Functions

```python
def initialize_metadata(
    node_key: str,
    provider: str,
    resource_type: str,
    count: str = "1",
    **kwargs
) -> Dict[str, Any]:
    """Create standard metadata entry for a graph node.
    
    Args:
        node_key: Graph node identifier
        provider: Cloud provider ('aws', 'azure', 'gcp')
        resource_type: Terraform resource type
        count: Resource count as string
        **kwargs: Additional metadata fields
    
    Returns:
        Metadata dict with required fields plus kwargs
    """
    metadata = {
        "count": count,
        "provider": provider,
        "type": resource_type,
    }
    metadata.update(kwargs)
    return metadata


def validate_metadata_consistency(tfdata: Dict[str, Any]) -> List[str]:
    """Validate metadata consistency with graphdict.
    
    Args:
        tfdata: Terraform data dictionary
    
    Returns:
        List of error messages (empty if valid)
    
    Checks:
        - All graphdict keys have metadata entries
        - All metadata entries have required fields
        - Parent references (vpc_id, etc.) point to existing nodes
    """
    pass
```

---

## 6. Provider Configuration Schema

### ProviderConfig Structure

```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ProviderConfig:
    """Provider-specific configuration.
    
    Attributes:
        name: Provider name ('aws', 'azure', 'gcp')
        consolidated_nodes: Resource types that consolidate children
        icon_base_path: Base path for resource icons
        resource_prefixes: List of Terraform resource prefixes
        handler_module: Module containing resource handlers
    """
    name: str
    consolidated_nodes: List[str]
    icon_base_path: str
    resource_prefixes: List[str]
    handler_module: str
```

### ProviderRegistry Interface

```python
class ProviderRegistry:
    """Registry of provider-specific configurations."""
    
    def get_provider(self, name: str) -> ProviderConfig:
        """Get configuration for named provider.
        
        Args:
            name: Provider name ('aws', 'azure', 'gcp')
        
        Returns:
            ProviderConfig instance
        
        Raises:
            ValueError: If provider name not recognized
        """
        pass
    
    def detect_provider_from_resources(self, resource_names: List[str]) -> str:
        """Detect provider from resource name prefixes.
        
        Args:
            resource_names: List of Terraform resource identifiers
        
        Returns:
            Provider name or 'unknown'
        """
        pass
```

---

## 7. Test Case Structure

### Unit Test Class Structure

```python
import pytest
from typing import Dict, Any

class TestHandlerFunction:
    """Unit tests for {handler_name}.
    
    Test Categories:
        - Error cases (missing resources, invalid metadata)
        - Edge cases (empty graphs, single resource, many resources)
        - Transformation correctness (grouping, reversal, type detection)
        - Metadata preservation (no data loss during transformations)
    """
    
    def test_missing_required_resource_raises_error(self):
        """Should raise MissingResourceError when required resource absent."""
        tfdata = minimal_tfdata()
        with pytest.raises(MissingResourceError, match="No .* found"):
            handler_function(tfdata)
    
    def test_groups_children_under_parent(self):
        """Should move child resources under parent in graphdict."""
        tfdata = fixture_with_parent_and_children()
        result = handler_function(tfdata)
        
        assert parent_key in result["graphdict"]
        assert child_key in result["graphdict"][parent_key]
        assert child_key not in result["graphdict"]  # Moved, not copied
    
    def test_preserves_metadata_during_transformation(self):
        """Should maintain all metadata fields after transformation."""
        tfdata = fixture_with_metadata()
        original_meta = copy.deepcopy(tfdata["metadata"])
        
        result = handler_function(tfdata)
        
        for key in original_meta:
            if key in result["metadata"]:
                assert result["metadata"][key] == original_meta[key]
    
    @pytest.mark.parametrize("count", [0, 1, 10, 100])
    def test_handles_varying_resource_counts(self, count):
        """Should work correctly with different resource counts."""
        tfdata = fixture_with_n_resources(count)
        result = handler_function(tfdata)
        # Assertions...
```

---

## Summary

Key entities defined:
1. **Exception Types**: 5 custom exceptions for library error handling
2. **Handler Signatures**: Standard interface for all provider handlers
3. **Utility Modules**: 4 focused modules (string, terraform, graph, provider)
4. **Test Fixtures**: Reusable tfdata structures for AWS/Azure/GCP
5. **Metadata Schema**: Standard structure for graph node metadata
6. **Provider Config**: ProviderRegistry and ProviderConfig interfaces
7. **Test Structure**: Patterns for unit/integration tests

All entities support the functional requirements from spec.md and align with research decisions from research.md.
