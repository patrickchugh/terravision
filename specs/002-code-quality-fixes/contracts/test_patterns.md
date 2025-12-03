# Contract: Test Patterns

**Version**: 1.0.0  
**Status**: Approved  
**Test Framework**: pytest + unittest.TestCase patterns

## Purpose

Define standard testing patterns for TerraVision code quality improvements, including test organization, fixture patterns, assertion styles, and performance benchmarks.

## Test Organization

### Directory Structure

```text
tests/
├── unit/                           # Fast, focused unit tests
│   ├── test_aws_handlers.py        # AWS handler transformations
│   ├── test_azure_handlers.py      # Azure handler transformations  
│   ├── test_gcp_handlers.py        # GCP handler transformations
│   ├── test_string_utils.py        # String parsing utilities
│   ├── test_terraform_utils.py     # Terraform operations
│   ├── test_graph_utils.py         # Graph operations
│   ├── test_provider_utils.py      # Provider detection
│   └── test_exceptions.py          # Exception types
├── integration/                     # End-to-end tests (marked slow)
│   ├── test_multicloud.py          # Mixed AWS/Azure/GCP configs
│   └── test_full_pipeline.py       # Complete Terraform → diagram flow
├── fixtures/                        # Shared test data
│   ├── __init__.py
│   ├── tfdata_samples.py           # Python fixture functions
│   ├── terraform_configs/          # Sample .tf files
│   │   ├── aws/
│   │   ├── azure/
│   │   └── gcp/
│   └── expected_outputs/           # Expected graph outputs
└── [existing test files]            # Keep existing tests
```

### Running Tests

```bash
# Run all fast tests (default, used in pre-commit)
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_aws_handlers.py

# Run specific test class
poetry run pytest tests/unit/test_aws_handlers.py::TestAWSHandleVPCEndpoints

# Run specific test method
poetry run pytest tests/unit/test_aws_handlers.py::TestAWSHandleVPCEndpoints::test_no_vpc_raises_error -v

# Run including slow tests (integration)
poetry run pytest -m ""

# Run only slow tests
poetry run pytest -m "slow"

# Run with coverage
poetry run pytest --cov=modules --cov-report=html
```

---

## Unit Test Patterns

### Test Class Structure

Use unittest.TestCase-style classes for organization:

```python
import pytest
from modules.resource_handlers.aws import aws_handle_vpcendpoints
from modules.exceptions import MissingResourceError
from tests.fixtures.tfdata_samples import minimal_tfdata, vpc_tfdata

class TestAWSHandleVPCEndpoints:
    """Unit tests for aws_handle_vpcendpoints handler.
    
    Test Categories:
        - Error cases: Missing resources, invalid inputs
        - Edge cases: Empty graphs, single resource, many resources
        - Transformation correctness: Grouping, relationships
        - Metadata preservation: No data loss
    """
    
    # Error cases
    def test_no_vpc_raises_error(self):
        """Should raise MissingResourceError when no VPC exists."""
        tfdata = minimal_tfdata()
        
        with pytest.raises(MissingResourceError) as exc_info:
            aws_handle_vpcendpoints(tfdata)
        
        assert "No VPC found" in str(exc_info.value)
        assert exc_info.value.resource_type == "aws_vpc"
        assert exc_info.value.required_by == "aws_handle_vpcendpoints"
    
    # Edge cases
    def test_handles_empty_graph(self):
        """Should handle empty graphdict without errors."""
        tfdata = minimal_tfdata()
        tfdata["graphdict"]["aws_vpc.main"] = []  # Add VPC to avoid error
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert result["graphdict"] == {"aws_vpc.main": []}
    
    def test_handles_single_endpoint(self):
        """Should process single VPC endpoint correctly."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=1)
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert "aws_vpc_endpoint.ep0" in result["graphdict"]["aws_vpc.vpc0"]
        assert "aws_vpc_endpoint.ep0" not in result["graphdict"]
    
    def test_handles_multiple_endpoints(self):
        """Should process multiple VPC endpoints correctly."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=5)
        
        result = aws_handle_vpcendpoints(tfdata)
        
        vpc_children = result["graphdict"]["aws_vpc.vpc0"]
        assert len([c for c in vpc_children if "endpoint" in c]) == 5
    
    # Transformation correctness
    def test_groups_endpoints_under_correct_vpc(self):
        """Should group endpoints under matching VPC."""
        tfdata = vpc_tfdata(vpc_count=2, endpoint_count=2)
        # Set vpc_id in endpoint metadata
        tfdata["metadata"]["aws_vpc_endpoint.ep0"]["vpc_id"] = "aws_vpc.vpc0"
        tfdata["metadata"]["aws_vpc_endpoint.ep1"]["vpc_id"] = "aws_vpc.vpc1"
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert "aws_vpc_endpoint.ep0" in result["graphdict"]["aws_vpc.vpc0"]
        assert "aws_vpc_endpoint.ep1" in result["graphdict"]["aws_vpc.vpc1"]
    
    # Metadata preservation
    def test_preserves_endpoint_metadata(self):
        """Should maintain all metadata fields for moved endpoints."""
        tfdata = vpc_tfdata(vpc_count=1, endpoint_count=1)
        original_meta = {
            "count": "1",
            "provider": "aws",
            "type": "aws_vpc_endpoint",
            "vpc_id": "aws_vpc.vpc0",
            "custom_field": "custom_value"  # Ensure custom fields preserved
        }
        tfdata["metadata"]["aws_vpc_endpoint.ep0"] = original_meta.copy()
        
        result = aws_handle_vpcendpoints(tfdata)
        
        assert result["metadata"]["aws_vpc_endpoint.ep0"] == original_meta
    
    # Parametrized tests for variations
    @pytest.mark.parametrize("vpc_count,endpoint_count", [
        (1, 0),   # No endpoints
        (1, 1),   # Single endpoint
        (1, 10),  # Many endpoints
        (3, 9),   # Multiple VPCs and endpoints
    ])
    def test_handles_varying_counts(self, vpc_count, endpoint_count):
        """Should handle varying VPC and endpoint counts."""
        tfdata = vpc_tfdata(vpc_count=vpc_count, endpoint_count=endpoint_count)
        
        result = aws_handle_vpcendpoints(tfdata)
        
        # All endpoints should be moved under VPCs
        endpoint_keys = [k for k in tfdata["graphdict"] if "endpoint" in k]
        for ep in endpoint_keys:
            assert ep not in result["graphdict"], f"{ep} should be moved"
```

### Assertion Patterns

**Structure Assertions** (graphdict changes):
```python
# Check node exists
assert "aws_vpc.main" in result["graphdict"]

# Check node removed
assert "aws_vpc_endpoint.s3" not in result["graphdict"]

# Check parent-child relationship
assert "aws_vpc_endpoint.s3" in result["graphdict"]["aws_vpc.main"]

# Check list contents
vpc_children = result["graphdict"]["aws_vpc.main"]
assert len(vpc_children) == 3
assert all("subnet" in child for child in vpc_children)
```

**Metadata Assertions**:
```python
# Check metadata exists
assert "aws_vpc.main" in result["metadata"]

# Check specific field
assert result["metadata"]["aws_vpc.main"]["count"] == "1"

# Check metadata preserved
assert result["metadata"]["aws_subnet.private"] == original_metadata

# Check required fields present
required_fields = {"count", "provider", "type"}
assert all(field in result["metadata"]["aws_vpc.main"] for field in required_fields)
```

**Exception Assertions**:
```python
# Check exception raised
with pytest.raises(MissingResourceError) as exc_info:
    handler_function(tfdata)

# Check exception message
assert "No VPC found" in str(exc_info.value)

# Check exception attributes
assert exc_info.value.resource_type == "aws_vpc"
assert exc_info.value.required_by == "handler_function"
```

---

## Fixture Patterns

### Location
`tests/fixtures/tfdata_samples.py`

### Minimal Fixture

```python
from typing import Dict, Any

def minimal_tfdata() -> Dict[str, Any]:
    """Create minimal valid tfdata structure.
    
    Returns empty graphdict, metadata, all_resource, annotations.
    Use as base for building specific test scenarios.
    """
    return {
        "graphdict": {},
        "metadata": {},
        "all_resource": [],
        "annotations": {}
    }
```

### Parametrized Fixture Factory

```python
def vpc_tfdata(
    vpc_count: int = 1,
    subnet_count: int = 0,
    endpoint_count: int = 0,
    nat_gateway_count: int = 0,
    security_group_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with AWS VPC resources.
    
    Args:
        vpc_count: Number of VPCs to create
        subnet_count: Number of subnets PER VPC
        endpoint_count: Total number of VPC endpoints
        nat_gateway_count: Total number of NAT gateways
        security_group_count: Total number of security groups
    
    Returns:
        tfdata with specified resources and proper metadata
    
    Example:
        >>> tfdata = vpc_tfdata(vpc_count=2, subnet_count=3, endpoint_count=2)
        >>> # Creates: 2 VPCs, 6 subnets (3 per VPC), 2 endpoints
    """
    tfdata = minimal_tfdata()
    
    # Create VPCs
    for i in range(vpc_count):
        vpc_key = f"aws_vpc.vpc{i}"
        tfdata["graphdict"][vpc_key] = []
        tfdata["metadata"][vpc_key] = {
            "count": "1",
            "provider": "aws",
            "type": "aws_vpc",
            "cidr_block": f"10.{i}.0.0/16"
        }
    
    # Create subnets
    for i in range(vpc_count):
        vpc_key = f"aws_vpc.vpc{i}"
        for j in range(subnet_count):
            subnet_key = f"aws_subnet.subnet{i}_{j}"
            tfdata["graphdict"][subnet_key] = []
            tfdata["metadata"][subnet_key] = {
                "count": "1",
                "provider": "aws",
                "type": "aws_subnet",
                "vpc_id": vpc_key,
                "cidr_block": f"10.{i}.{j}.0/24"
            }
    
    # Create VPC endpoints
    vpc_key = f"aws_vpc.vpc0" if vpc_count > 0 else None
    for i in range(endpoint_count):
        ep_key = f"aws_vpc_endpoint.ep{i}"
        tfdata["graphdict"][ep_key] = []
        tfdata["metadata"][ep_key] = {
            "count": "1",
            "provider": "aws",
            "type": "aws_vpc_endpoint",
            "vpc_id": vpc_key,
            "service_name": f"com.amazonaws.region.service{i}"
        }
    
    # Similar pattern for NAT gateways, security groups, etc.
    
    return tfdata
```

### Azure Fixture

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
        subnet_count: Number of subnets PER VNet
        nsg_count: Total number of NSGs
        lb_count: Total number of load balancers
    
    Returns:
        tfdata with Azure resources
    """
    tfdata = minimal_tfdata()
    
    # Create VNets
    for i in range(vnet_count):
        vnet_key = f"azurerm_virtual_network.vnet{i}"
        tfdata["graphdict"][vnet_key] = []
        tfdata["metadata"][vnet_key] = {
            "count": "1",
            "provider": "azure",
            "type": "azurerm_virtual_network",
            "address_space": [f"10.{i}.0.0/16"]
        }
    
    # Create subnets
    for i in range(vnet_count):
        vnet_key = f"azurerm_virtual_network.vnet{i}"
        for j in range(subnet_count):
            subnet_key = f"azurerm_subnet.subnet{i}_{j}"
            tfdata["graphdict"][subnet_key] = []
            tfdata["metadata"][subnet_key] = {
                "count": "1",
                "provider": "azure",
                "type": "azurerm_subnet",
                "virtual_network_name": vnet_key,
                "address_prefixes": [f"10.{i}.{j}.0/24"]
            }
    
    # NSGs, LBs, etc.
    
    return tfdata
```

### GCP Fixture

```python
def gcp_network_tfdata(
    network_count: int = 1,
    subnet_count: int = 0,
    firewall_count: int = 0,
    backend_service_count: int = 0
) -> Dict[str, Any]:
    """Create tfdata with GCP VPC network resources.
    
    Args:
        network_count: Number of VPC networks
        subnet_count: Number of subnets PER network
        firewall_count: Total number of firewall rules
        backend_service_count: Total number of backend services (LBs)
    
    Returns:
        tfdata with GCP resources
    """
    tfdata = minimal_tfdata()
    
    # Create VPC networks
    for i in range(network_count):
        network_key = f"google_compute_network.network{i}"
        tfdata["graphdict"][network_key] = []
        tfdata["metadata"][network_key] = {
            "count": "1",
            "provider": "gcp",
            "type": "google_compute_network",
            "auto_create_subnetworks": False
        }
    
    # Create subnets (regional in GCP)
    for i in range(network_count):
        network_key = f"google_compute_network.network{i}"
        for j in range(subnet_count):
            subnet_key = f"google_compute_subnetwork.subnet{i}_{j}"
            tfdata["graphdict"][subnet_key] = []
            tfdata["metadata"][subnet_key] = {
                "count": "1",
                "provider": "gcp",
                "type": "google_compute_subnetwork",
                "network": network_key,
                "ip_cidr_range": f"10.{i}.{j}.0/24",
                "region": f"us-west{j+1}"
            }
    
    # Firewalls, backend services, etc.
    
    return tfdata
```

### Multicloud Fixture

```python
def multicloud_tfdata(
    aws_vpcs: int = 1,
    azure_vnets: int = 1,
    gcp_networks: int = 1
) -> Dict[str, Any]:
    """Create tfdata with mixed provider resources.
    
    Combines AWS, Azure, and GCP resources in single tfdata.
    Used for testing provider detection and mixed configurations.
    """
    tfdata = minimal_tfdata()
    
    # Merge AWS resources
    aws_data = vpc_tfdata(vpc_count=aws_vpcs)
    tfdata["graphdict"].update(aws_data["graphdict"])
    tfdata["metadata"].update(aws_data["metadata"])
    
    # Merge Azure resources
    azure_data = vnet_tfdata(vnet_count=azure_vnets)
    tfdata["graphdict"].update(azure_data["graphdict"])
    tfdata["metadata"].update(azure_data["metadata"])
    
    # Merge GCP resources
    gcp_data = gcp_network_tfdata(network_count=gcp_networks)
    tfdata["graphdict"].update(gcp_data["graphdict"])
    tfdata["metadata"].update(gcp_data["metadata"])
    
    return tfdata
```

---

## Integration Test Patterns

### Slow Test Marker

```python
import pytest

@pytest.mark.slow
def test_full_terraform_pipeline():
    """End-to-end test processing real Terraform files.
    
    Marked 'slow' - excluded from pre-commit hooks, run in CI only.
    """
    # Load actual .tf files
    # Run full processing pipeline
    # Verify output diagram correctness
    pass
```

### Integration Test Structure

```python
# tests/integration/test_multicloud.py
import pytest
from pathlib import Path
from modules.fileparser import parse_terraform_files
from modules.graphmaker import build_graph
from modules.resource_handlers import apply_all_handlers

@pytest.mark.slow
class TestMulticloudIntegration:
    """Integration tests for mixed AWS/Azure/GCP configurations."""
    
    def test_aws_azure_mixed_config(self, tmp_path):
        """Should process Terraform config with AWS and Azure resources."""
        # Create test .tf files
        tf_file = tmp_path / "main.tf"
        tf_file.write_text("""
        resource "aws_vpc" "main" {
          cidr_block = "10.0.0.0/16"
        }
        
        resource "azurerm_virtual_network" "vnet" {
          address_space = ["10.1.0.0/16"]
        }
        """)
        
        # Process
        tfdata = parse_terraform_files(str(tmp_path))
        tfdata = build_graph(tfdata)
        tfdata = apply_all_handlers(tfdata)
        
        # Verify both providers handled
        assert "aws_vpc.main" in tfdata["graphdict"]
        assert "azurerm_virtual_network.vnet" in tfdata["graphdict"]
        assert tfdata["metadata"]["aws_vpc.main"]["provider"] == "aws"
        assert tfdata["metadata"]["azurerm_virtual_network.vnet"]["provider"] == "azure"
```

---

## Performance Test Patterns

### Benchmark Pattern

```python
import pytest
import time
from modules.utils.graph_utils import find_common_elements

def test_find_common_elements_performance():
    """Should complete in O(n+m) time, not O(n*m)."""
    # Large lists
    list1 = [str(i) for i in range(10000)]
    list2 = [str(i) for i in range(5000, 15000)]
    
    # Measure time
    start = time.time()
    result = find_common_elements(list1, list2)
    elapsed = time.time() - start
    
    # Assertions
    assert len(result) == 5000  # Correct result
    assert elapsed < 0.1, f"Too slow: {elapsed:.3f}s (expected <0.1s)"

@pytest.mark.benchmark
def test_handler_performance_100_resources(benchmark):
    """Benchmark handler with 100 resources (typical enterprise config)."""
    tfdata = vpc_tfdata(vpc_count=10, subnet_count=10, endpoint_count=100)
    
    # Run handler multiple times and measure
    result = benchmark(aws_handle_vpcendpoints, tfdata)
    
    assert result is not None  # Ensure handler completed
```

---

## Coverage Requirements

### Target Coverage

- **Overall**: 80%+ code coverage
- **Resource handlers**: 90%+ (critical business logic)
- **Utilities**: 85%+ (frequently used functions)
- **Exceptions**: 100% (all exception types tested)

### Coverage Report

```bash
# Generate HTML coverage report
poetry run pytest --cov=modules --cov-report=html

# View report
open htmlcov/index.html

# Check coverage threshold (fails if below 80%)
poetry run pytest --cov=modules --cov-fail-under=80
```

---

## Contract Guarantees

1. **Test Organization**: Unit/integration/fixtures clearly separated
2. **Fast Tests**: Unit tests run in <5 seconds total
3. **Slow Tests**: Integration tests marked with @pytest.mark.slow
4. **Fixtures**: Reusable tfdata factories in tests/fixtures/
5. **Assertions**: Structured checks for graphdict, metadata, exceptions
6. **Coverage**: Minimum 80% overall, 90% for handlers
7. **Performance**: Benchmark tests for optimized functions
8. **Documentation**: All test classes have descriptive docstrings
