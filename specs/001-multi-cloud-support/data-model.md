# Data Model: Multi-Cloud Provider Support

**Feature**: Multi-Cloud Provider Support (GCP & Azure)
**Date**: 2025-12-07
**Phase**: Phase 1 - Design

## Overview

This document defines the key entities and their relationships for adding multi-cloud provider support to TerraVision. The data model extends the existing `tfdata` dictionary structure with provider awareness while maintaining backward compatibility with AWS-only workflows.

## Core Entities

### 1. ProviderDetectionResult

**Purpose**: Encapsulates the result of cloud provider detection from Terraform resources.

**Attributes**:
- `providers`: List[str] - Detected provider names (['aws', 'azure', 'gcp'])
- `primary_provider`: str - Provider with most resources ('aws' | 'azure' | 'gcp')
- `resource_counts`: Dict[str, int] - Resource count per provider ({'aws': 45, 'azure': 12})
- `detection_method`: str - How provider was detected ('provider_block' | 'resource_prefix' | 'hybrid')
- `confidence`: float - Detection confidence score (0.0-1.0)

**Relationships**:
- Has one-to-many relationship with ResourcesByProvider
- Created by ProviderDetector
- Consumed by ConfigurationLoader and OutputFileGenerator

**Validation Rules**:
- `providers` must not be empty
- `primary_provider` must be in `providers` list
- Resource counts must sum to match total resources in tfdata
- Confidence must be between 0.0 and 1.0

**Storage Location**: Added to tfdata dictionary as `tfdata["provider_detection"]`

**Example**:
```python
{
    "providers": ["aws", "azure"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 67, "azure": 15},
    "detection_method": "hybrid",
    "confidence": 1.0
}
```

---

### 2. ProviderConfiguration

**Purpose**: Holds provider-specific configuration settings loaded from cloud_config_{provider}.py files.

**Attributes**:
- `provider_name`: str - Provider identifier ('aws' | 'azure' | 'gcp')
- `consolidated_nodes`: List[Dict] - Grouping rules for similar resources
- `group_nodes`: List[str] - Hierarchy nodes (VPC, Subnet, Security Group)
- `edge_nodes`: List[str] - External boundary resources (Internet Gateway, NAT)
- `outer_nodes`: List[str] - User/external system nodes
- `draw_order`: List[List[str]] - Node rendering sequence
- `auto_annotations`: List[Dict] - Automatic relationship rules
- `node_variants`: Dict[str, str] - Resource type variations
- `reverse_arrow_list`: List[str] - Connection direction reversals
- `forced_dest`: List[str] - Always-destination resources
- `forced_origin`: List[str] - Always-origin resources
- `implied_connections`: Dict[str, List[str]] - Keyword-based auto-linking
- `special_resources`: Dict[str, str] - Handler function mapping
- `shared_services`: List[str] - Shared resource identification
- `always_draw_line`: List[str] - Always show connections
- `never_draw_line`: List[str] - Never show connections
- `acronyms_list`: List[str] - Display name formatting
- `name_replacements`: Dict[str, str] - Resource label mapping
- `refinement_prompt`: str - LLM prompt for diagram refinement
- `documentation_prompt`: str - LLM prompt for documentation
- `cloud_group_class`: str - Cloud boundary group class name

**Relationships**:
- One ProviderConfiguration per provider
- Loaded by ConfigurationLoader based on ProviderDetectionResult
- Consumed by ResourceHandlers, DiagramRenderer, and AIRefinement

**Validation Rules**:
- `provider_name` must be one of: 'aws', 'azure', 'gcp'
- `group_nodes` must be ordered (parent → child hierarchy)
- `special_resources` keys must match resource types in resource_classes
- Prompts must not be empty strings

**Storage Location**: Loaded dynamically, not stored in tfdata (passed to functions as needed)

**Example**:
```python
{
    "provider_name": "azure",
    "consolidated_nodes": [
        {"azurerm_network_security_group": {...}},
        {"azurerm_application_gateway": {...}}
    ],
    "group_nodes": ["azurerm_resource_group", "azurerm_virtual_network", "azurerm_subnet"],
    "refinement_prompt": "You are an Azure architecture diagram expert...",
    "cloud_group_class": "Azuregroup"
}
```

---

### 3. ResourcesByProvider

**Purpose**: Segments Terraform resources by detected cloud provider for multi-cloud project handling.

**Attributes**:
- `provider`: str - Provider name ('aws' | 'azure' | 'gcp')
- `resources`: List[str] - Resource keys from tfdata["graphdict"] for this provider
- `graphdict`: Dict[str, List[str]] - Filtered graphdict with only this provider's resources
- `metadata`: Dict[str, Dict] - Filtered meta_data with only this provider's resources

**Relationships**:
- Multiple ResourcesByProvider entities for multi-cloud projects
- Created by filtering tfdata based on ProviderDetectionResult
- Consumed by DiagramGenerator for creating provider-specific diagrams

**Validation Rules**:
- All resources in `resources` must exist in original tfdata
- `graphdict` keys must match `resources` list
- `metadata` keys must match `resources` list
- No overlap between ResourcesByProvider entities (each resource in exactly one)

**Storage Location**: Created transiently during diagram generation, not stored in tfdata

**Example**:
```python
{
    "provider": "azure",
    "resources": [
        "azurerm_resource_group.main",
        "azurerm_virtual_network.vnet1",
        "azurerm_virtual_machine.vm1"
    ],
    "graphdict": {
        "azurerm_resource_group.main": ["azurerm_virtual_network.vnet1"],
        "azurerm_virtual_network.vnet1": ["azurerm_virtual_machine.vm1"],
        "azurerm_virtual_machine.vm1": []
    },
    "metadata": {
        "azurerm_resource_group.main": {"location": "eastus", "tags": {}},
        ...
    }
}
```

---

### 4. ResourceHandlerRegistry

**Purpose**: Maps resource types to provider-specific handler functions.

**Attributes**:
- `provider`: str - Provider name
- `handlers`: Dict[str, callable] - Resource type → handler function mapping
- `special_case_handler`: callable - General special case processor
- `match_resources_handler`: callable - Post-processing matcher

**Relationships**:
- One ResourceHandlerRegistry per provider
- Created by ResourceHandlerDispatcher
- Consumed by GraphMaker during special resource processing

**Validation Rules**:
- Handler functions must accept tfdata Dict and return tfdata Dict
- Handler names must follow pattern: {provider}_handle_{resource_category}
- All handlers must be importable from resource_handlers_{provider}.py

**Storage Location**: Instantiated in modules/graphmaker.py, not stored in tfdata

**Example**:
```python
{
    "provider": "azure",
    "handlers": {
        "azurerm_resource_group": azure_handle_resource_groups,
        "azurerm_application_gateway": azure_handle_app_gateway,
        "azurerm_network_security_group": azure_handle_nsg
    },
    "special_case_handler": azure_handle_special_cases,
    "match_resources_handler": azure_match_resources
}
```

---

### 5. OutputFileDescriptor

**Purpose**: Describes output file generation for single or multi-provider scenarios.

**Attributes**:
- `base_filename`: str - User-provided base filename (e.g., "architecture")
- `provider`: str - Provider for this output file
- `full_filename`: str - Generated filename with provider suffix if needed
- `format`: str - Output format ('png' | 'svg' | 'pdf' | 'bmp')
- `is_multi_provider`: bool - Whether project has multiple providers

**Relationships**:
- One OutputFileDescriptor per provider per format
- Created by OutputFileGenerator based on ProviderDetectionResult
- Consumed by DiagramRenderer for file generation

**Validation Rules**:
- `base_filename` must not be empty
- `format` must be one of: 'png', 'svg', 'pdf', 'bmp'
- If `is_multi_provider` is True, `full_filename` must include provider suffix
- If `is_multi_provider` is False, `full_filename` equals `base_filename`

**Storage Location**: Created transiently during output generation

**Example**:
```python
# Single provider:
{
    "base_filename": "architecture",
    "provider": "aws",
    "full_filename": "architecture",
    "format": "png",
    "is_multi_provider": False
}

# Multi-provider:
{
    "base_filename": "architecture",
    "provider": "azure",
    "full_filename": "architecture-azure",
    "format": "png",
    "is_multi_provider": True
}
```

---

## Entity Relationships Diagram

```
┌─────────────────────────────┐
│   Terraform tfdata          │
│   (existing structure)      │
└──────────┬──────────────────┘
           │
           ├──> ProviderDetector.detect()
           │
           v
    ┌──────────────────────────┐
    │ ProviderDetectionResult  │
    │  - providers: List[str]  │
    │  - primary_provider: str │
    └────┬────────────┬────────┘
         │            │
         │            └──> ConfigurationLoader.load()
         │                      │
         │                      v
         │              ┌──────────────────────┐
         │              │ ProviderConfiguration │
         │              │  (per provider)       │
         │              └───────┬──────────────┘
         │                      │
         v                      v
┌────────────────────┐   ┌─────────────────────────┐
│ ResourcesByProvider│   │ ResourceHandlerRegistry │
│  (per provider)    │   │   (per provider)        │
└────────┬───────────┘   └──────────┬──────────────┘
         │                          │
         └────────┬─────────────────┘
                  │
                  v
          ┌───────────────────────┐
          │ OutputFileDescriptor  │
          │   (per provider)      │
          └───────────┬───────────┘
                      │
                      v
              ┌──────────────────┐
              │ Generated Diagram │
              │   (per provider)  │
              └──────────────────┘
```

---

## State Transitions

### Provider Detection State Machine

```
[Terraform Project]
    │
    └──> [Scanning Provider Blocks]
            │
            ├──> Found explicit provider(s) ──> [Validating with Resource Scan]
            │                                         │
            └──> No provider blocks ──────────────────┘
                                                      │
                                                      v
                                            [Resource Prefix Matching]
                                                      │
                                                      v
                                            [ProviderDetectionResult Created]
                                                      │
                                                      ├──> Single Provider ──> [Load Single Config]
                                                      │
                                                      └──> Multi-Provider ──> [Load Multiple Configs]
```

### Diagram Generation State Machine (Multi-Provider)

```
[ProviderDetectionResult]
    │
    └──> For each provider:
            │
            ├──> [Filter Resources by Provider] ──> ResourcesByProvider
            │
            ├──> [Load ProviderConfiguration]
            │
            ├──> [Import Provider Resource Classes]
            │
            ├──> [Apply Resource Handlers]
            │
            ├──> [Generate Diagram] ──> OutputFileDescriptor
            │
            └──> [Render to File]
```

---

## Data Model Extensions to Existing tfdata Structure

The multi-cloud feature extends the existing tfdata dictionary without breaking backward compatibility:

**Before (AWS-only)**:
```python
tfdata = {
    "graphdict": {...},        # Resource relationships
    "meta_data": {...},        # Resource metadata
    "all_resource": [...],     # All resource names
    "codepath": "...",         # Source code path
    "annotations": {...}       # User annotations
}
```

**After (Multi-cloud aware)**:
```python
tfdata = {
    "graphdict": {...},                    # ✅ Unchanged
    "meta_data": {...},                    # ✅ Unchanged
    "all_resource": [...],                 # ✅ Unchanged
    "codepath": "...",                     # ✅ Unchanged
    "annotations": {...},                  # ✅ Unchanged
    "provider_detection": {                # 🆕 NEW
        "providers": ["aws", "azure"],
        "primary_provider": "aws",
        "resource_counts": {"aws": 67, "azure": 15},
        "detection_method": "hybrid",
        "confidence": 1.0
    }
}
```

**Backward Compatibility**:
- If `provider_detection` key does not exist, assume AWS (default behavior)
- All existing AWS-only code paths continue working unchanged

---

## Validation Rules Summary

### Cross-Entity Constraints

1. **Resource Consistency**: Total resources in ResourcesByProvider must equal tfdata["all_resource"] count
2. **Provider Coverage**: Every resource in tfdata must be assigned to exactly one provider
3. **Configuration Completeness**: Each detected provider must have a corresponding ProviderConfiguration
4. **Handler Registration**: Each provider must have a ResourceHandlerRegistry with required handlers
5. **Output Consistency**: Number of OutputFileDescriptors must equal number of detected providers × formats requested

### Entity-Specific Constraints

| Entity | Primary Key | Required Fields | Validation |
|--------|------------|-----------------|------------|
| ProviderDetectionResult | N/A (singleton per tfdata) | providers, primary_provider | providers not empty, primary in providers |
| ProviderConfiguration | provider_name | provider_name, group_nodes, refinement_prompt | Valid provider name |
| ResourcesByProvider | provider | provider, resources, graphdict | All resources exist in tfdata |
| ResourceHandlerRegistry | provider | provider, special_case_handler | Handler is callable |
| OutputFileDescriptor | full_filename | base_filename, provider, format | Valid format |

---

## Usage Examples

### Example 1: Single Provider Project (AWS)

```python
# After provider detection
tfdata["provider_detection"] = {
    "providers": ["aws"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 52},
    "detection_method": "provider_block",
    "confidence": 1.0
}

# Load configuration
config = load_config("aws")  # Returns ProviderConfiguration for AWS

# No need to split resources (single provider)
# Generate single output file
output = OutputFileDescriptor(
    base_filename="architecture",
    provider="aws",
    full_filename="architecture",
    format="png",
    is_multi_provider=False
)
```

### Example 2: Multi-Provider Project (AWS + Azure)

```python
# After provider detection
tfdata["provider_detection"] = {
    "providers": ["aws", "azure"],
    "primary_provider": "aws",
    "resource_counts": {"aws": 67, "azure": 15},
    "detection_method": "hybrid",
    "confidence": 1.0
}

# Split resources by provider
aws_resources = ResourcesByProvider(
    provider="aws",
    resources=["aws_instance.web", "aws_s3_bucket.data", ...],
    graphdict={...},
    metadata={...}
)

azure_resources = ResourcesByProvider(
    provider="azure",
    resources=["azurerm_virtual_machine.app", "azurerm_storage_account.logs", ...],
    graphdict={...},
    metadata={...}
)

# Generate separate output files
aws_output = OutputFileDescriptor(
    base_filename="architecture",
    provider="aws",
    full_filename="architecture-aws",
    format="png",
    is_multi_provider=True
)

azure_output = OutputFileDescriptor(
    base_filename="architecture",
    provider="azure",
    full_filename="architecture-azure",
    format="png",
    is_multi_provider=True
)
```

---

## Migration Notes

### Adding New Providers (Future)

To add support for a new cloud provider (e.g., Alibaba Cloud):

1. **Create Configuration**: `modules/cloud_config_alicloud.py` with ALICLOUD_* variables
2. **Create Handlers**: `modules/resource_handlers_alicloud.py` with alicloud_handle_* functions
3. **Create Resource Classes**: `resource_classes/alicloud/` with service categories
4. **Update Provider Detection**: Add 'alicloud_' prefix to PROVIDER_PREFIXES in provider_detector.py
5. **Update Configuration Loader**: Add 'alicloud' case to load_config()
6. **Update Handler Dispatcher**: Add 'alicloud' case to handle_special_cases()

### Backward Compatibility Guarantee

- Existing AWS-only projects: No changes required
- `import modules.cloud_config` continues working (redirects to cloud_config_aws)
- All existing handler function names preserved (aws_handle_*)
- Output filename unchanged for single-provider projects
- If provider_detection missing from tfdata, assumes AWS default

---

## Data Model Review Checklist

- [x] All entities have clear purpose and attributes
- [x] Relationships between entities documented
- [x] Validation rules defined per entity
- [x] State transitions documented
- [x] Backward compatibility preserved
- [x] Extension points for new providers identified
- [x] Storage locations specified
- [x] Examples provided for single and multi-provider scenarios
