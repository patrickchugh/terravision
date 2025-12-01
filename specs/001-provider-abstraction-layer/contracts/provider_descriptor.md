# API Contract: ProviderDescriptor

**Version**: 1.0.0 | **Status**: Draft | **Last Updated**: 2025-11-26

## Overview

ProviderDescriptor is an immutable dataclass that encapsulates metadata for a cloud provider. It serves as the registration token for the ProviderRegistry and configuration source for ProviderContext initialization.

## Type Signature

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class ProviderDescriptor:
    """
    Immutable descriptor for cloud provider metadata.
    
    Registered in ProviderRegistry during module initialization.
    """
    
    # Identity
    name: str
    display_name: str
    
    # Detection
    resource_prefix: str
    terraform_provider_name: str
    
    # Configuration
    config_module: str
    handler_module: Optional[str]
    
    # Resource Classes
    resource_class_prefix: str
    icon_directory: str
    
    # Capabilities
    supports_annotations: bool = True
    supports_gitlibs: bool = True
    
    # Metadata
    version: str = '1.0.0'
    aliases: Optional[List[str]] = None
```

## Field Specifications

### Identity Fields

#### `name: str`
- **Purpose**: Canonical provider identifier (lowercase, alphanumeric + underscore)
- **Examples**: `'aws'`, `'azure'`, `'gcp'`, `'generic'`
- **Constraints**:
  - Must be valid Python identifier: `name.isidentifier() == True`
  - Must be unique across all registered providers
  - Must be lowercase
- **Usage**: Primary key for ProviderRegistry lookups

#### `display_name: str`
- **Purpose**: Human-readable provider name for UI/logging
- **Examples**: `'Amazon Web Services'`, `'Microsoft Azure'`, `'Google Cloud Platform'`
- **Constraints**: Non-empty string
- **Usage**: Error messages, documentation, CLI help text

### Detection Fields

#### `resource_prefix: str`
- **Purpose**: Terraform resource type prefix for provider detection
- **Examples**: `'aws_'`, `'azurerm_'`, `'google_'`, `''` (generic)
- **Constraints**: 
  - Must end with `'_'` for non-generic providers
  - Can be empty string for generic fallback provider
- **Usage**: Fallback provider detection when Terraform plan metadata unavailable

#### `terraform_provider_name: str`
- **Purpose**: Fully-qualified provider name from Terraform registry
- **Examples**: 
  - `'hashicorp/aws'`
  - `'hashicorp/azurerm'`
  - `'hashicorp/google'`
  - `''` (generic)
- **Format**: `'<namespace>/<provider>'` or empty string
- **Usage**: Primary provider detection from Terraform plan JSON `provider_name` field

### Configuration Fields

#### `config_module: str`
- **Purpose**: Python module path containing provider configuration constants
- **Examples**: 
  - `'modules.cloud_config.aws'`
  - `'modules.cloud_config.azure'`
  - `'modules.cloud_config.common'` (generic)
- **Constraints**:
  - Must be importable via `importlib.import_module()`
  - Module must define: `CONSOLIDATED_NODES`, `DRAW_ORDER`, `NODE_VARIANTS`, `AUTO_ANNOTATIONS`
- **Usage**: Loaded by ProviderContext during initialization

#### `handler_module: Optional[str]`
- **Purpose**: Optional Python module for custom resource handlers
- **Examples**: 
  - `'resource_handlers.aws'`
  - `'resource_handlers.azure'`
  - `None` (no custom handlers)
- **Constraints**: Must be importable if not None
- **Usage**: Future extensibility for provider-specific processing logic

### Resource Class Fields

#### `resource_class_prefix: str`
- **Purpose**: Base path for Diagrams resource class imports
- **Examples**: 
  - `'resource_classes.aws'`
  - `'resource_classes.azure'`
  - `'resource_classes.generic'`
- **Constraints**: Directory must exist with structure: `{prefix}/{category}/{ClassName}.py`
- **Usage**: NodeFactory dynamic imports: `{prefix}.{category}.{ClassName}`

#### `icon_directory: str`
- **Purpose**: Base directory for provider-specific icon images
- **Examples**: 
  - `'resource_images/aws'`
  - `'resource_images/azure'`
  - `'resource_images/generic'`
- **Constraints**: 
  - Directory must exist
  - Structure: `{icon_directory}/{category}/{resource_type}.png`
- **Usage**: ProviderContext.resolve_icon_path() fallback chain

### Capability Fields

#### `supports_annotations: bool`
- **Purpose**: Whether provider supports YAML annotation files
- **Default**: `True`
- **Usage**: Core modules check before loading annotation files
- **Example**: Generic provider sets to `False` (no annotation support)

#### `supports_gitlibs: bool`
- **Purpose**: Whether provider supports Terraform git module references
- **Default**: `True`
- **Usage**: Git module parser checks before processing
- **Example**: Generic provider sets to `False`

### Metadata Fields

#### `version: str`
- **Purpose**: ProviderDescriptor schema version (semantic versioning)
- **Default**: `'1.0.0'`
- **Format**: `'{major}.{minor}.{patch}'`
- **Usage**: Future compatibility checks if descriptor schema evolves

#### `aliases: Optional[List[str]]`
- **Purpose**: Alternative names for provider (for flexible user input)
- **Examples**: 
  - AWS: `['amazon']`
  - Azure: `['azurerm', 'microsoft']`
  - GCP: `['google', 'googlecloud']`
  - Generic: `None`
- **Constraints**: Aliases must be unique across all providers
- **Usage**: ProviderRegistry accepts alias lookups: `get_descriptor('amazon')` → AWS descriptor

## Immutability Contract

**Frozen Dataclass**: `@dataclass(frozen=True)`

**Guarantees**:
- All fields are read-only after initialization
- Attempting to modify raises `FrozenInstanceError`
- Safe to share across threads (though CLI is single-threaded)
- Hash-able (can be used as dict key)

**Rationale**: Provider descriptors are configuration metadata that should never change at runtime. Immutability prevents accidental state corruption and enables safe caching.

## Validation Rules

### Pre-Registration Validation

```python
def validate_descriptor(desc: ProviderDescriptor) -> None:
    """
    Validate descriptor before registration.
    
    Raises:
        ValueError: If validation fails with descriptive error message
    """
    # 1. Name validation
    if not desc.name.isidentifier():
        raise ValueError(f"Provider name '{desc.name}' must be valid Python identifier")
    
    if not desc.name.islower():
        raise ValueError(f"Provider name '{desc.name}' must be lowercase")
    
    # 2. Config module validation
    try:
        importlib.import_module(desc.config_module)
    except ImportError as e:
        raise ValueError(f"Config module '{desc.config_module}' not importable: {e}")
    
    # 3. Resource class prefix validation
    if not os.path.isdir(desc.resource_class_prefix.replace('.', '/')):
        raise ValueError(f"Resource class directory '{desc.resource_class_prefix}' not found")
    
    # 4. Icon directory validation
    if not os.path.isdir(desc.icon_directory):
        raise ValueError(f"Icon directory '{desc.icon_directory}' not found")
    
    # 5. Alias uniqueness validation (checked by ProviderRegistry)
    # (Handled during registration to check against existing descriptors)
```

### Runtime Validation

```python
def validate_config_module(module) -> None:
    """
    Validate config module has required constants.
    
    Called by ProviderContext._load_config()
    """
    required = ['CONSOLIDATED_NODES', 'DRAW_ORDER', 'NODE_VARIANTS', 'AUTO_ANNOTATIONS']
    missing = [const for const in required if not hasattr(module, const)]
    
    if missing:
        raise ValueError(f"Config module missing required constants: {missing}")
```

## Usage Examples

### Creating Built-in Provider Descriptors

```python
# AWS descriptor
AWS_DESCRIPTOR = ProviderDescriptor(
    name='aws',
    display_name='Amazon Web Services',
    resource_prefix='aws_',
    terraform_provider_name='hashicorp/aws',
    config_module='modules.cloud_config.aws',
    handler_module='resource_handlers.aws',
    resource_class_prefix='resource_classes.aws',
    icon_directory='resource_images/aws',
    supports_annotations=True,
    supports_gitlibs=True,
    version='1.0.0',
    aliases=['amazon']
)

# Azure descriptor (minimal Phase 1)
AZURE_DESCRIPTOR = ProviderDescriptor(
    name='azure',
    display_name='Microsoft Azure',
    resource_prefix='azurerm_',
    terraform_provider_name='hashicorp/azurerm',
    config_module='modules.cloud_config.azure',
    handler_module='resource_handlers.azure',
    resource_class_prefix='resource_classes.azure',
    icon_directory='resource_images/azure',
    version='1.0.0',
    aliases=['azurerm', 'microsoft']
)

# Generic fallback descriptor
GENERIC_DESCRIPTOR = ProviderDescriptor(
    name='generic',
    display_name='Generic Provider',
    resource_prefix='',  # Matches any
    terraform_provider_name='',
    config_module='modules.cloud_config.common',
    handler_module=None,
    resource_class_prefix='resource_classes.generic',
    icon_directory='resource_images/generic',
    supports_annotations=False,  # No provider-specific annotations
    supports_gitlibs=False,
    version='1.0.0',
    aliases=None
)
```

### Registering Descriptors

```python
# In modules/cloud_config/__init__.py
from modules.provider_runtime import ProviderRegistry

# Register built-in providers
ProviderRegistry.register(AWS_DESCRIPTOR)
ProviderRegistry.register(AZURE_DESCRIPTOR)
ProviderRegistry.register(GCP_DESCRIPTOR)
ProviderRegistry.register(GENERIC_DESCRIPTOR)
```

### Plugin Provider (Future Extensibility)

```python
# External plugin: terravision-plugin-oci/oci_provider.py
from modules.provider_runtime import ProviderDescriptor, ProviderRegistry

OCI_DESCRIPTOR = ProviderDescriptor(
    name='oci',
    display_name='Oracle Cloud Infrastructure',
    resource_prefix='oci_',
    terraform_provider_name='hashicorp/oci',
    config_module='terravision_plugins.oci.config',
    handler_module='terravision_plugins.oci.handlers',
    resource_class_prefix='terravision_plugins.oci.classes',
    icon_directory='terravision_plugins/oci/icons',
    version='1.0.0',
    aliases=['oracle', 'oraclecloud']
)

# Plugin registers itself on import
ProviderRegistry.register(OCI_DESCRIPTOR)
```

## Error Handling

### Registration Errors

```python
# Duplicate provider name
try:
    ProviderRegistry.register(AWS_DESCRIPTOR)
    ProviderRegistry.register(AWS_DESCRIPTOR)  # Second registration
except ValueError as e:
    # "Provider 'aws' already registered"
    pass

# Invalid config module
try:
    bad_descriptor = ProviderDescriptor(
        name='bad',
        config_module='nonexistent.module',
        # ... other fields
    )
    ProviderRegistry.register(bad_descriptor)
except ValueError as e:
    # "Config module 'nonexistent.module' not importable: No module named 'nonexistent'"
    pass
```

### Immutability Violations

```python
from dataclasses import FrozenInstanceError

descriptor = AWS_DESCRIPTOR

try:
    descriptor.name = 'changed'  # Attempt to modify
except FrozenInstanceError:
    # Cannot assign to field 'name'
    pass
```

## Serialization

**Not Serializable**: ProviderDescriptor is not designed for JSON/YAML serialization. It contains Python module paths that only make sense in the TerraVision runtime environment.

**Registration is Code**: Providers are registered via Python code in `modules/cloud_config/__init__.py`, not via configuration files.

**Rationale**: Prevents security risks from loading arbitrary module paths from external config files.

## Testing Contract

### Unit Tests

```python
# tests/unit/test_provider_descriptor.py
import pytest
from modules.provider_runtime import ProviderDescriptor

class TestProviderDescriptor:
    def test_immutability(self):
        desc = ProviderDescriptor(
            name='test',
            display_name='Test',
            resource_prefix='test_',
            terraform_provider_name='test/test',
            config_module='modules.cloud_config.aws',
            handler_module=None,
            resource_class_prefix='resource_classes.generic',
            icon_directory='resource_images/generic'
        )
        
        with pytest.raises(FrozenInstanceError):
            desc.name = 'changed'
    
    def test_default_values(self):
        desc = ProviderDescriptor(
            name='test',
            display_name='Test',
            resource_prefix='test_',
            terraform_provider_name='test/test',
            config_module='modules.cloud_config.aws',
            resource_class_prefix='resource_classes.generic',
            icon_directory='resource_images/generic'
        )
        
        assert desc.supports_annotations == True
        assert desc.supports_gitlibs == True
        assert desc.version == '1.0.0'
        assert desc.aliases is None
    
    def test_with_aliases(self):
        desc = ProviderDescriptor(
            name='aws',
            display_name='AWS',
            resource_prefix='aws_',
            terraform_provider_name='hashicorp/aws',
            config_module='modules.cloud_config.aws',
            resource_class_prefix='resource_classes.aws',
            icon_directory='resource_images/aws',
            aliases=['amazon', 'amzn']
        )
        
        assert 'amazon' in desc.aliases
        assert 'amzn' in desc.aliases
```

## Migration Path

### Phase 1: Initial Implementation
- Define ProviderDescriptor dataclass
- Create AWS, Azure, GCP, Generic descriptors
- Implement validation logic

### Phase 2: Deprecation
- No changes (descriptors are new API)

### Phase 3: Stabilization
- Lock descriptor schema to 1.0.0
- Document any future schema changes as 1.1.0, 2.0.0, etc.
- Add version compatibility checks if needed

## Related Contracts

- [ProviderContext](./provider_context.md) - Uses ProviderDescriptor for initialization
- [ProviderRegistry](../data-model.md#3-providerregistry) - Manages descriptor registration and lookups
- [ServiceMapping](./service_mapping.md) - Independent of descriptors, but used by contexts

## Open Questions

1. **Should descriptors support custom validation hooks?**
   - Current: Built-in validation only
   - Future: Allow `validate_fn: Optional[Callable[[ProviderDescriptor], None]]` field?
   - Decision: Defer to Phase 2; keep simple for Phase 1

2. **Should we support descriptor versioning for compatibility?**
   - Current: `version` field is metadata only
   - Future: Check version compatibility when loading old providers?
   - Decision: Add if needed; no compatibility issues yet

3. **Should icon_directory support multiple paths (fallback chain)?**
   - Current: Single directory per provider
   - Future: Allow `icon_directories: List[str]` for theme support?
   - Decision: Use single directory; theme support is separate feature

## Changelog

### v1.0.0 (2025-11-26)
- Initial contract definition
- Immutable dataclass with 12 fields
- Validation rules specified
- Usage examples documented
