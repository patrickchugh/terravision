# Contract: Provider Handlers

**Version**: 1.0.0  
**Status**: Approved  
**Modules**: `modules/resource_handlers/{aws,azure,gcp}.py`

## Purpose

Define standard interface for provider-specific resource transformation handlers, ensuring consistency across AWS, Azure, and GCP implementations.

## Standard Handler Interface

All provider-specific handlers MUST follow this interface:

```python
from typing import Dict, Any
from modules.exceptions import MissingResourceError, MetadataInconsistencyError

def {provider}_handle_{resource_type}(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle {provider} {resource_type} transformations.
    
    Applies provider-specific graph transformations for {resource_type} resources.
    
    Args:
        tfdata: Terraform data dictionary with structure:
            {
                "graphdict": Dict[str, List[str]],  # Adjacency list
                "metadata": Dict[str, Dict[str, Any]],  # Node metadata
                "all_resource": List[str],  # All resource names
                "annotations": Dict[str, Any]  # YAML annotations
            }
    
    Returns:
        Updated tfdata with transformations applied. Modifies in place but
        returns for method chaining.
    
    Raises:
        MissingResourceError: If required parent resources don't exist
        MetadataInconsistencyError: If metadata missing or invalid after transform
    
    Side Effects:
        - Modifies tfdata["graphdict"] (adds/removes/moves nodes)
        - Modifies tfdata["metadata"] (updates/creates entries)
        - Does NOT modify tfdata["all_resource"] or tfdata["annotations"]
    
    Performance:
        Should complete in O(n) where n is number of affected resources.
        Avoid nested loops over full graphdict.
    
    Example:
        >>> tfdata = load_terraform_data("main.tf")
        >>> tfdata = aws_handle_vpcendpoints(tfdata)
        >>> assert "aws_vpc.main" in tfdata["graphdict"]
    """
    # Implementation pattern:
    # 1. Find relevant resources
    # 2. Validate required parents exist
    # 3. Transform graphdict
    # 4. Update/create metadata
    # 5. Return tfdata
```

## Handler Categories

### Category 1: Grouping Handlers

**Purpose**: Move child resources under parent resources in the graph hierarchy.

**Pattern**:
```python
def {provider}_handle_{parent}_{child}(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group {child} resources under parent {parent}."""
    
    # 1. Find parent and child resources
    parents = list_of_dictkeys_containing(tfdata["graphdict"], "{parent_pattern}")
    children = list_of_dictkeys_containing(tfdata["graphdict"], "{child_pattern}")
    
    # 2. Validate parents exist
    if not parents:
        raise MissingResourceError(
            f"No {parent} found; cannot group {child} resources",
            resource_type="{parent_pattern}",
            required_by="{provider}_handle_{parent}_{child}"
        )
    
    # 3. Group children under parents
    for child in children:
        # Determine parent (from metadata or naming convention)
        parent_key = find_parent_for_child(child, parents, tfdata["metadata"])
        
        # Move child under parent
        tfdata["graphdict"][parent_key].append(child)
        del tfdata["graphdict"][child]
        
        # Metadata stays with child (not moved)
    
    return tfdata
```

**Examples**:
- `aws_handle_vpcendpoints`: Group VPC endpoints under VPCs
- `azure_handle_vnet_subnets`: Group subnets under VNets
- `gcp_handle_network_subnets`: Group subnets under VPC networks

---

### Category 2: Reversal Handlers

**Purpose**: Reverse connection direction (e.g., make security groups wrap resources instead of being children).

**Pattern**:
```python
def {provider}_handle_{wrapper_resource}(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse {wrapper_resource} connections to wrap target resources."""
    
    # 1. Find wrapper resources
    wrappers = list_of_dictkeys_containing(tfdata["graphdict"], "{wrapper_pattern}")
    
    # 2. For each wrapper, find resources it should wrap
    for wrapper in wrappers:
        # Find resources that reference this wrapper
        targets = find_resources_referencing(wrapper, tfdata)
        
        # 3. Reverse: wrapper becomes parent, targets become children
        for target in targets:
            # Remove target from its current parent
            for parent_key, children in tfdata["graphdict"].items():
                if target in children:
                    children.remove(target)
            
            # Add target under wrapper
            tfdata["graphdict"][wrapper].append(target)
        
        # 4. Update metadata to reflect new relationship
        for target in targets:
            tfdata["metadata"][target]["wrapped_by"] = wrapper
    
    return tfdata
```

**Examples**:
- `aws_handle_sg`: Reverse security group connections
- `azure_handle_nsg`: Reverse NSG connections

**Note**: GCP firewalls use target tags, not reversal pattern.

---

### Category 3: Type Detection Handlers

**Purpose**: Detect resource variants and update metadata for icon/label selection.

**Pattern**:
```python
def {provider}_handle_{resource}(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect {resource} type variants and update metadata."""
    
    # 1. Find all resources of this type
    resources = list_of_dictkeys_containing(tfdata["graphdict"], "{resource_pattern}")
    
    # 2. For each resource, detect variant
    for resource in resources:
        meta = tfdata["metadata"].get(resource, {})
        
        # Provider-specific variant detection
        variant = detect_variant(meta)  # e.g., "alb", "nlb", "clb" for AWS LBs
        
        # 3. Update metadata with variant info
        tfdata["metadata"][resource]["{provider}_{resource}_type"] = variant
        
        # Optionally update display label
        tfdata["metadata"][resource]["display_label"] = f"{resource} ({variant.upper()})"
    
    return tfdata
```

**Examples**:
- `aws_handle_loadbalancer`: Detect ALB/NLB/CLB variants
- `azure_handle_lb`: Detect Basic/Standard SKUs
- `gcp_handle_lb`: Detect HTTP(S)/TCP/Internal LB types

---

## Provider-Specific Contracts

### AWS Handlers (`modules/resource_handlers/aws.py`)

**Required Handlers**:
```python
def aws_handle_vpcendpoints(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group VPC endpoints under parent VPC."""
    pass

def aws_handle_sg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse security group connections (SG wraps instances)."""
    pass

def aws_handle_autoscaling(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process autoscaling groups and their resources."""
    pass

def aws_handle_loadbalancer(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect load balancer types (ALB/NLB/CLB)."""
    pass

def aws_handle_efs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process EFS mount targets and file systems."""
    pass

def aws_handle_natgateways(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group NAT gateways under appropriate subnets."""
    pass

def aws_handle_iam_roles(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process IAM role attachments and policies."""
    pass
```

**Specific Requirements**:
- VPC resources: Always check for VPC existence before processing VPC-dependent resources
- Security groups: Support reversal pattern (SG contains instances)
- Autoscaling: Handle partial metadata gracefully (not all ASG resources have full metadata)

---

### Azure Handlers (`modules/resource_handlers/azure.py`)

**Required Handlers**:
```python
def azure_handle_vnet_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group subnets under parent VNets.
    
    Azure-specific: Match by virtual_network_name or vnet_id in metadata.
    """
    pass

def azure_handle_nsg(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse NSG connections (NSG wraps resources).
    
    Azure-specific: Process both subnet-level and NIC-level NSG associations.
    """
    pass

def azure_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect load balancer SKUs (Basic/Standard).
    
    Azure-specific: Check 'sku' metadata field.
    """
    pass

def azure_handle_app_gateway(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process Application Gateway configurations.
    
    Azure-specific: Detect Standard_v2/WAF_v2 SKUs, process backend pools.
    """
    pass
```

**Specific Requirements**:
- VNets: Use `virtual_network_name` metadata field for subnet-to-VNet matching
- NSGs: Handle both `azurerm_network_interface_security_group_association` and `azurerm_subnet_network_security_group_association`
- Load Balancers: Distinguish Basic (IPv4 only) vs Standard (IPv6 support, zone-redundant)

---

### GCP Handlers (`modules/resource_handlers/gcp.py`)

**Required Handlers**:
```python
def gcp_handle_network_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group subnets under parent VPC networks.
    
    GCP-specific: Subnets are regional (span multiple zones).
    Match by 'network' metadata field.
    """
    pass

def gcp_handle_firewall(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Process firewall rules with target tags.
    
    GCP-specific: Firewalls use target tags, not reversal pattern.
    Add direction (INGRESS/EGRESS) to metadata.
    """
    pass

def gcp_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Detect load balancer types from backend services.
    
    GCP-specific: LBs are composite resources.
    Detect HTTP(S)/TCP/SSL/Internal/Network based on protocol and lb_scheme.
    """
    pass

def gcp_handle_cloud_dns(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group DNS records under managed zones.
    
    GCP-specific: Handle zone types (public/private/forwarding/peering).
    """
    pass
```

**Specific Requirements**:
- VPC Networks: Global resource, subnets are regional
- Firewalls: No wrapping pattern; create edges based on target tags
- Load Balancers: Composite resources (forwarding rule → proxy → url_map → backend_service)
- Cloud DNS: Private zones link to VPC networks

---

## Metadata Management Contract

### Required Metadata Fields

Every handler that creates or modifies nodes MUST ensure these metadata fields exist:

```python
{
    "count": str,          # Required: "1" or resource count
    "provider": str,       # Required: "aws" | "azure" | "gcp"
    "type": str,           # Required: Terraform resource type
}
```

### Handler-Specific Metadata Fields

Handlers MAY add provider/resource-specific fields:

```python
# AWS-specific
{
    "vpc_id": str,                    # For VPC-dependent resources
    "aws_lb_type": str,               # "alb" | "nlb" | "clb"
}

# Azure-specific
{
    "vnet_id": str,                   # For VNet-dependent resources
    "sku": str,                       # "Basic" | "Standard"
    "azure_lb_type": str,             # "basic" | "standard"
    "azure_appgw_type": str,          # "standard_v2" | "waf_v2"
}

# GCP-specific
{
    "network_id": str,                # For network-dependent resources
    "protocol": str,                  # "HTTP" | "HTTPS" | "TCP" | "SSL"
    "load_balancing_scheme": str,    # "EXTERNAL" | "INTERNAL"
    "gcp_lb_type": str,               # "http_lb" | "tcp_lb" | "internal_lb"
    "direction": str,                 # "INGRESS" | "EGRESS" (for firewalls)
    "target_tags": List[str],         # Firewall target tags
}
```

### Metadata Helper Usage

```python
from modules.utils.graph_utils import ensure_metadata

def example_handler(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Example showing metadata management."""
    
    # When creating new graph nodes
    new_node_key = "aws_vpc_endpoint.s3_custom"
    tfdata["graphdict"][new_node_key] = []
    
    # ALWAYS ensure metadata exists
    ensure_metadata(
        tfdata,
        new_node_key,
        defaults={
            "count": "1",
            "provider": "aws",
            "type": "aws_vpc_endpoint",
            "vpc_id": "aws_vpc.main"
        }
    )
    
    return tfdata
```

---

## Testing Contract

### Unit Test Requirements

Each handler MUST have unit tests covering:

1. **Missing parent resource** → raises `MissingResourceError`
2. **Single resource** → transforms correctly
3. **Multiple resources** → all transformed
4. **Metadata preservation** → original metadata not lost
5. **Edge cases** → empty graphs, partial metadata

**Example Test Structure**:
```python
# tests/unit/test_aws_handlers.py
import pytest
from modules.resource_handlers.aws import aws_handle_vpcendpoints
from modules.exceptions import MissingResourceError
from tests.fixtures.tfdata_samples import minimal_tfdata, vpc_tfdata

class TestAWSHandleVPCEndpoints:
    def test_no_vpc_raises_error(self):
        """Should raise MissingResourceError when no VPC exists."""
        tfdata = minimal_tfdata()
        with pytest.raises(MissingResourceError, match="No .* VPC"):
            aws_handle_vpcendpoints(tfdata)
    
    def test_groups_endpoints_under_vpc(self):
        """Should move endpoints under parent VPC."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=2)
        result = aws_handle_vpcendpoints(tfdata)
        
        assert "aws_vpc_endpoint.s3" in result["graphdict"]["aws_vpc.vpc0"]
        assert "aws_vpc_endpoint.s3" not in result["graphdict"]
    
    def test_preserves_endpoint_metadata(self):
        """Should maintain metadata for moved endpoints."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=1)
        original_meta = tfdata["metadata"]["aws_vpc_endpoint.s3"].copy()
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert result["metadata"]["aws_vpc_endpoint.s3"] == original_meta
```

---

## Contract Guarantees

1. **Interface Consistency**: All handlers follow standard signature
2. **Exception Safety**: Handlers only raise documented exceptions
3. **Metadata Integrity**: New nodes always have metadata entries
4. **Idempotence**: Running handler twice produces same result
5. **No Side Effects**: Only modifies graphdict and metadata, not all_resource/annotations
6. **Performance**: O(n) complexity for n affected resources
7. **Deterministic Output**: Same input always produces same output
8. **Documentation**: All handlers have comprehensive docstrings with examples

## Migration Notes

**AWS Handlers**: Already exist; add missing exception handling and metadata checks

**Azure/GCP Handlers**: Currently stubs; implement following AWS patterns with provider-specific adaptations

**Backward Compatibility**: Existing handler signatures unchanged; added exception raising is new behavior
