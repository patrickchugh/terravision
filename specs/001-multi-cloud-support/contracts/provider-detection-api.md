# Provider Detection API Contract

**Feature**: Multi-Cloud Provider Support
**Module**: `modules/provider_detector.py`
**Version**: 1.0.0
**Date**: 2025-12-07

## Overview

The Provider Detection API identifies cloud providers used in a Terraform project by analyzing provider blocks and resource types. It supports AWS, Azure, and GCP detection with confidence scoring.

---

## API Functions

### 1. `detect_providers(tfdata: Dict[str, Any]) -> ProviderDetectionResult`

**Purpose**: Detect all cloud providers used in Terraform project

**Parameters**:
- `tfdata` (Dict[str, Any]): Terraform data dictionary containing:
  - `all_resource` (List[str]): All resource names from Terraform
  - `graphdict` (Dict): Resource relationship graph
  - `meta_data` (Dict): Resource metadata

**Returns**: `ProviderDetectionResult` dictionary containing:
```python
{
    "providers": List[str],        # ['aws', 'azure', 'gcp']
    "primary_provider": str,       # 'aws' | 'azure' | 'gcp'
    "resource_counts": Dict[str, int],  # {'aws': 45, 'azure': 12}
    "detection_method": str,       # 'provider_block' | 'resource_prefix' | 'hybrid'
    "confidence": float            # 0.0 to 1.0
}
```

**Behavior**:
1. Scan tfdata["all_resource"] for resource prefixes (aws_, azurerm_, google_)
2. Count resources per provider
3. Determine primary provider (most resources)
4. Calculate confidence score based on clarity of detection

**Confidence Scoring**:
- 1.0: All resources have unambiguous prefixes
- 0.8-0.9: Mostly clear with some ambiguous resources
- 0.5-0.7: Mixed signals, provider aliases, or unclear prefixes
- <0.5: Low confidence, defaults applied

**Example**:
```python
tfdata = {
    "all_resource": [
        "aws_instance.web",
        "aws_s3_bucket.data",
        "azurerm_virtual_machine.app",
        "azurerm_storage_account.logs"
    ],
    "graphdict": {...},
    "meta_data": {...}
}

result = detect_providers(tfdata)
# Returns:
{
    "providers": ["aws", "azure"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 2, "azure": 2},
    "detection_method": "resource_prefix",
    "confidence": 1.0
}
```

**Error Handling**:
- Raises `ValueError` if tfdata missing required keys
- Raises `ProviderDetectionError` if no providers detected
- Defaults to AWS with confidence 0.3 if detection fails

---

### 2. `get_provider_for_resource(resource_name: str) -> str`

**Purpose**: Determine cloud provider for a single resource

**Parameters**:
- `resource_name` (str): Full Terraform resource name (e.g., "aws_instance.web")

**Returns**: Provider name as string ('aws' | 'azure' | 'gcp' | 'unknown')

**Behavior**:
1. Extract resource type from name (strip module prefix and instance name)
2. Match resource type prefix against PROVIDER_PREFIXES mapping
3. Return provider or 'unknown'

**Example**:
```python
get_provider_for_resource("aws_instance.web")
# Returns: "aws"

get_provider_for_resource("module.networking.azurerm_virtual_network.main")
# Returns: "azure"

get_provider_for_resource("google_compute_instance.vm1")
# Returns: "gcp"

get_provider_for_resource("random_string.id")
# Returns: "unknown"
```

**Error Handling**:
- Returns 'unknown' for unrecognized prefixes
- Never raises exceptions (safe default)

---

### 3. `filter_resources_by_provider(tfdata: Dict[str, Any], provider: str) -> ResourcesByProvider`

**Purpose**: Extract subset of resources belonging to specific provider

**Parameters**:
- `tfdata` (Dict[str, Any]): Full Terraform data dictionary
- `provider` (str): Provider to filter ('aws' | 'azure' | 'gcp')

**Returns**: `ResourcesByProvider` dictionary containing:
```python
{
    "provider": str,                    # Provider name
    "resources": List[str],             # Resource keys for this provider
    "graphdict": Dict[str, List[str]],  # Filtered relationship graph
    "metadata": Dict[str, Dict]         # Filtered metadata
}
```

**Behavior**:
1. Iterate through tfdata["all_resource"]
2. For each resource, call `get_provider_for_resource()`
3. Include resource if provider matches
4. Build filtered graphdict with only matching resources
5. Build filtered metadata with only matching resources

**Example**:
```python
tfdata = {
    "all_resource": ["aws_instance.web", "azurerm_virtual_machine.app"],
    "graphdict": {
        "aws_instance.web": [],
        "azurerm_virtual_machine.app": []
    },
    "meta_data": {
        "aws_instance.web": {"instance_type": "t2.micro"},
        "azurerm_virtual_machine.app": {"size": "Standard_B1s"}
    }
}

aws_resources = filter_resources_by_provider(tfdata, "aws")
# Returns:
{
    "provider": "aws",
    "resources": ["aws_instance.web"],
    "graphdict": {"aws_instance.web": []},
    "metadata": {"aws_instance.web": {"instance_type": "t2.micro"}}
}
```

**Error Handling**:
- Raises `ValueError` if provider not in ['aws', 'azure', 'gcp']
- Returns empty ResourcesByProvider if no resources match provider

---

### 4. `validate_provider_detection(result: ProviderDetectionResult, tfdata: Dict[str, Any]) -> bool`

**Purpose**: Validate provider detection result against actual resources

**Parameters**:
- `result` (ProviderDetectionResult): Detection result to validate
- `tfdata` (Dict[str, Any]): Original Terraform data

**Returns**: `True` if validation passes, `False` otherwise

**Validation Checks**:
1. All providers in result.providers are valid ('aws', 'azure', 'gcp')
2. primary_provider is in providers list
3. Sum of resource_counts equals len(tfdata["all_resource"])
4. Confidence is between 0.0 and 1.0
5. At least one provider detected

**Example**:
```python
result = {
    "providers": ["aws", "azure"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 45, "azure": 15},
    "detection_method": "hybrid",
    "confidence": 1.0
}

is_valid = validate_provider_detection(result, tfdata)
# Returns: True if counts match, False otherwise
```

**Error Handling**:
- Returns False on validation failure (does not raise exceptions)
- Logs warning messages for failed validations

---

## Constants

### PROVIDER_PREFIXES

**Purpose**: Map Terraform resource type prefixes to provider names

```python
PROVIDER_PREFIXES = {
    'aws_': 'aws',
    'azurerm_': 'azure',
    'azuread_': 'azure',      # Azure Active Directory
    'azurestack_': 'azure',
    'azapi_': 'azure',        # Azure API provider
    'google_': 'gcp',
}
```

**Usage**: Used by `get_provider_for_resource()` to determine provider from resource name

---

### SUPPORTED_PROVIDERS

**Purpose**: List of all supported cloud providers

```python
SUPPORTED_PROVIDERS = ['aws', 'azure', 'gcp']
```

**Usage**: Validation in `validate_provider_detection()` and error messages

---

## Error Classes

### ProviderDetectionError

**Purpose**: Raised when provider detection fails completely

```python
class ProviderDetectionError(Exception):
    """Raised when no cloud providers can be detected in Terraform project."""
    pass
```

**When Raised**:
- No resources found in tfdata
- All resources have 'unknown' provider
- Critical validation failures

**Handling**: Caller should catch and either:
1. Prompt user to specify provider explicitly
2. Default to AWS with warning message
3. Exit with error if provider required

---

## Integration Points

### Integration with Configuration Loader

```python
# In modules/config_loader.py
from modules.provider_detector import detect_providers

def load_configurations(tfdata: Dict[str, Any]) -> Dict[str, ProviderConfiguration]:
    """Load provider-specific configurations."""
    detection_result = detect_providers(tfdata)

    configs = {}
    for provider in detection_result["providers"]:
        configs[provider] = load_config(provider)

    return configs
```

### Integration with Diagram Generator

```python
# In terravision.py
from modules.provider_detector import detect_providers, filter_resources_by_provider

def generate_diagrams(tfdata, outfile, format):
    """Generate diagrams for detected providers."""
    detection_result = detect_providers(tfdata)
    tfdata["provider_detection"] = detection_result  # Store in tfdata

    for provider in detection_result["providers"]:
        provider_resources = filter_resources_by_provider(tfdata, provider)

        # Generate diagram for this provider
        filename = generate_filename(outfile, provider, detection_result["providers"])
        render_diagram(provider_resources, filename, format, provider)
```

### Integration with Resource Handlers

```python
# In modules/graphmaker.py
from modules.provider_detector import get_provider_for_resource

def handle_special_resources(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Apply provider-specific resource handlers."""
    for resource in tfdata["all_resource"]:
        provider = get_provider_for_resource(resource)
        handler_registry = get_handler_registry(provider)

        if resource_type in handler_registry.handlers:
            handler = handler_registry.handlers[resource_type]
            tfdata = handler(tfdata)

    return tfdata
```

---

## Testing Requirements

### Unit Tests

```python
def test_detect_aws_only():
    """Test detection of AWS-only project."""
    tfdata = {"all_resource": ["aws_instance.web", "aws_s3_bucket.data"]}
    result = detect_providers(tfdata)
    assert result["providers"] == ["aws"]
    assert result["primary_provider"] == "aws"
    assert result["confidence"] == 1.0

def test_detect_multi_cloud():
    """Test detection of multi-cloud project."""
    tfdata = {
        "all_resource": [
            "aws_instance.web",
            "azurerm_virtual_machine.app",
            "google_compute_instance.vm"
        ]
    }
    result = detect_providers(tfdata)
    assert set(result["providers"]) == {"aws", "azure", "gcp"}
    assert result["primary_provider"] in ["aws", "azure", "gcp"]

def test_get_provider_for_aws_resource():
    """Test provider detection from AWS resource name."""
    assert get_provider_for_resource("aws_instance.web") == "aws"
    assert get_provider_for_resource("module.vpc.aws_subnet.private") == "aws"

def test_get_provider_for_azure_resource():
    """Test provider detection from Azure resource name."""
    assert get_provider_for_resource("azurerm_virtual_machine.app") == "azure"
    assert get_provider_for_resource("azuread_user.admin") == "azure"

def test_get_provider_for_gcp_resource():
    """Test provider detection from GCP resource name."""
    assert get_provider_for_resource("google_compute_instance.vm1") == "gcp"

def test_get_provider_for_unknown_resource():
    """Test provider detection for unknown resource."""
    assert get_provider_for_resource("random_string.id") == "unknown"
    assert get_provider_for_resource("null_resource.trigger") == "unknown"

def test_filter_resources_by_provider():
    """Test filtering resources by provider."""
    tfdata = {
        "all_resource": ["aws_instance.web", "azurerm_virtual_machine.app"],
        "graphdict": {...},
        "meta_data": {...}
    }
    aws_resources = filter_resources_by_provider(tfdata, "aws")
    assert len(aws_resources["resources"]) == 1
    assert "aws_instance.web" in aws_resources["resources"]

def test_validate_provider_detection_success():
    """Test validation of valid detection result."""
    result = {
        "providers": ["aws"],
        "primary_provider": "aws",
        "resource_counts": {"aws": 10},
        "detection_method": "resource_prefix",
        "confidence": 1.0
    }
    tfdata = {"all_resource": ["aws_instance.web"] * 10}
    assert validate_provider_detection(result, tfdata) == True

def test_validate_provider_detection_failure():
    """Test validation catches mismatched counts."""
    result = {
        "providers": ["aws"],
        "primary_provider": "aws",
        "resource_counts": {"aws": 5},  # Mismatch!
        "detection_method": "resource_prefix",
        "confidence": 1.0
    }
    tfdata = {"all_resource": ["aws_instance.web"] * 10}
    assert validate_provider_detection(result, tfdata) == False
```

### Integration Tests

```python
def test_end_to_end_aws_project():
    """Test full detection flow for AWS project."""
    tfdata = load_terraform_fixture("aws_vpc_example")
    result = detect_providers(tfdata)
    assert result["providers"] == ["aws"]
    assert result["confidence"] > 0.9

def test_end_to_end_azure_project():
    """Test full detection flow for Azure project."""
    tfdata = load_terraform_fixture("azure_vm_example")
    result = detect_providers(tfdata)
    assert result["providers"] == ["azure"]
    assert result["confidence"] > 0.9

def test_end_to_end_multi_cloud():
    """Test full detection flow for multi-cloud project."""
    tfdata = load_terraform_fixture("aws_azure_hybrid")
    result = detect_providers(tfdata)
    assert "aws" in result["providers"]
    assert "azure" in result["providers"]
    assert len(result["providers"]) == 2
```

---

## Performance Considerations

### Time Complexity

- `detect_providers()`: O(n) where n = number of resources
- `get_provider_for_resource()`: O(1) constant time lookup
- `filter_resources_by_provider()`: O(n) where n = number of resources

### Space Complexity

- `detect_providers()`: O(1) fixed size result dictionary
- `filter_resources_by_provider()`: O(m) where m = resources for provider

### Optimization Notes

- Provider detection is cached in tfdata["provider_detection"] to avoid re-detection
- PROVIDER_PREFIXES uses dictionary lookup (O(1)) instead of list search
- Resource filtering creates new dictionaries to avoid mutating tfdata

---

## Backward Compatibility

### AWS-Only Projects

For existing AWS-only projects that don't call `detect_providers()`:

```python
# Old code (still works):
tfdata = tfwrapper.tf_initplan(source, varfile, workspace, debug)
# ... existing AWS-only pipeline

# No detection result in tfdata, defaults to AWS
```

### Migration Path

Existing code can adopt provider detection incrementally:

```python
# Step 1: Add detection (no behavior change)
detection_result = detect_providers(tfdata)
tfdata["provider_detection"] = detection_result

# Step 2: Use detection for configuration loading
if "provider_detection" in tfdata:
    providers = tfdata["provider_detection"]["providers"]
else:
    providers = ["aws"]  # Default for old tfdata

# Step 3: Generate provider-specific diagrams
for provider in providers:
    ...
```

---

## API Versioning

**Current Version**: 1.0.0

**Versioning Policy**:
- MAJOR: Breaking changes to function signatures or return types
- MINOR: New functions added, new fields in return types (backward compatible)
- PATCH: Bug fixes, internal optimizations

**Deprecation Policy**:
- Deprecated functions marked with @deprecated decorator
- Supported for 2 major versions before removal
- Migration guide provided in deprecation notice

---

## Appendix: Example Detection Scenarios

### Scenario 1: Pure AWS Project
```python
Input:
  all_resource: ["aws_instance.web", "aws_s3_bucket.data", "aws_vpc.main"]

Output:
  {
    "providers": ["aws"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 3},
    "detection_method": "resource_prefix",
    "confidence": 1.0
  }
```

### Scenario 2: Pure Azure Project
```python
Input:
  all_resource: ["azurerm_resource_group.main", "azurerm_virtual_machine.app"]

Output:
  {
    "providers": ["azure"],
    "primary_provider": "azure",
    "resource_counts": {"azure": 2},
    "detection_method": "resource_prefix",
    "confidence": 1.0
  }
```

### Scenario 3: AWS + Azure Hybrid
```python
Input:
  all_resource: [
    "aws_instance.web", "aws_s3_bucket.data",      # 2 AWS
    "azurerm_virtual_machine.app"                   # 1 Azure
  ]

Output:
  {
    "providers": ["aws", "azure"],
    "primary_provider": "aws",  # Most resources
    "resource_counts": {"aws": 2, "azure": 1},
    "detection_method": "resource_prefix",
    "confidence": 1.0
  }
```

### Scenario 4: With Unknown Resources
```python
Input:
  all_resource: [
    "aws_instance.web",
    "random_string.id",         # Unknown provider
    "null_resource.trigger"     # Unknown provider
  ]

Output:
  {
    "providers": ["aws"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 1, "unknown": 2},
    "detection_method": "resource_prefix",
    "confidence": 0.7  # Lower confidence due to unknowns
  }
```
