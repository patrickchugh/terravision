# API Contract: ProviderContext

**Version**: 1.0.0 | **Status**: Draft | **Last Updated**: 2025-11-26

## Overview

ProviderContext is a runtime context class that provides access to provider-specific configuration, resource resolution, and icon management. It serves as the primary interface between core modules and provider-specific logic.

## Type Signature

```python
from typing import Dict, List, Any, Optional
from functools import lru_cache
from modules.provider_runtime import ProviderDescriptor

class ProviderContext:
    """
    Runtime context for cloud provider operations.
    
    Lazily loads provider configuration and caches expensive lookups.
    One instance per provider, managed by ProviderRegistry.
    """
    
    def __init__(self, descriptor: ProviderDescriptor) -> None:
        """
        Initialize context from descriptor.
        
        Does NOT load config module (lazy initialization).
        
        Args:
            descriptor: Provider metadata
        """
        ...
    
    # Identity
    @property
    def name(self) -> str:
        """Provider canonical name"""
        ...
    
    # Configuration Properties (lazy-loaded)
    @property
    def consolidated_nodes(self) -> Dict[str, List[str]]:
        """Node consolidation rules"""
        ...
    
    @property
    def draw_order(self) -> List[str]:
        """Resource drawing order"""
        ...
    
    @property
    def node_variants(self) -> Dict[str, str]:
        """Icon variant mappings"""
        ...
    
    @property
    def auto_annotations(self) -> Dict[str, Any]:
        """Automatic annotation defaults"""
        ...
    
    # Resolution Methods (cached)
    @lru_cache(maxsize=256)
    def resolve_resource_class(self, resource_type: str) -> Any:
        """Resolve Diagrams resource class"""
        ...
    
    @lru_cache(maxsize=256)
    def resolve_icon_path(self, resource_type: str, category: str) -> str:
        """Resolve icon file path with fallback"""
        ...
    
    def get_service_category(self, resource_type: str) -> str:
        """Get canonical service category"""
        ...
```

## Constructor

### `__init__(descriptor: ProviderDescriptor) -> None`

**Purpose**: Initialize context from provider descriptor

**Parameters**:
- `descriptor`: ProviderDescriptor instance (immutable metadata)

**Behavior**:
- Stores descriptor reference
- Initializes private fields to None (lazy loading)
- Does NOT load config module (deferred to first property access)

**Postconditions**:
- `self.descriptor` set
- `self._config_module` is None
- All config properties (`_consolidated_nodes`, etc.) are None

**Example**:
```python
descriptor = ProviderRegistry.get_descriptor('aws')
ctx = ProviderContext(descriptor)  # No module loading yet
# Config loaded on first property access:
order = ctx.draw_order  # Triggers _load_config()
```

## Properties

### Identity Property

#### `name: str` (read-only)

**Purpose**: Provider canonical name (shorthand for `descriptor.name`)

**Returns**: String like `'aws'`, `'azure'`, `'gcp'`

**Complexity**: O(1) attribute access

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
assert ctx.name == 'aws'
```

### Configuration Properties (Lazy-Loaded)

All configuration properties follow this pattern:
1. Check if private field is None
2. If None, call `_load_config()` to import module and extract constants
3. Return cached value

#### `consolidated_nodes: Dict[str, List[str]]` (read-only)

**Purpose**: Node consolidation rules for diagram simplification

**Format**:
```python
{
    'parent_resource_type': ['child_resource_type_1', 'child_resource_type_2'],
    ...
}
```

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
vpc_consolidation = ctx.consolidated_nodes.get('aws_vpc_endpoint', [])
# Returns: ['aws_vpc_endpoint_service']  (VPC endpoints consolidated with services)
```

**Default**: Empty dict `{}` if not defined in config module

**Usage**: `graphmaker.py` uses to group related resources

#### `draw_order: List[str]` (read-only)

**Purpose**: Ordered list of resource types for diagram layering

**Format**: List of resource type strings, ordered from background to foreground

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
order = ctx.draw_order
# Returns: ['aws_vpc', 'aws_subnet', 'aws_route_table', 'aws_instance', ...]
```

**Default**: Empty list `[]` if not defined in config module

**Usage**: `drawing.py` uses to determine z-order of diagram nodes

**Invariant**: All resource types in list should exist in ServiceMapping

#### `node_variants: Dict[str, str]` (read-only)

**Purpose**: Map resource types to icon variant names (abbreviations)

**Format**:
```python
{
    'resource_type': 'variant_name',
    ...
}
```

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
variant = ctx.node_variants.get('aws_instance')
# Returns: 'ec2'  (AWS instance uses EC2 icon variant)
```

**Default**: Empty dict `{}` if not defined in config module

**Usage**: `drawing.py` uses to select specific icon files

#### `auto_annotations: Dict[str, Any]` (read-only)

**Purpose**: Provider-specific automatic annotation defaults

**Format**: Arbitrary dict structure (provider-defined)

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
should_consolidate = ctx.auto_annotations.get('consolidate_vpc_endpoints', False)
# Returns: True  (AWS defaults to consolidating VPC endpoints)
```

**Default**: Empty dict `{}` if not defined in config module

**Usage**: `annotations.py` merges with user annotations

## Methods

### Configuration Loading (Private)

#### `_load_config() -> None` (private)

**Purpose**: Load config module and extract constants

**Behavior**:
1. Import config module via `importlib.import_module(descriptor.config_module)`
2. Extract constants using `getattr(module, 'CONSTANT_NAME', default)`
3. Cache in private instance variables

**Called By**: All configuration properties on first access

**Caching**: Module-level (importlib caches modules), instance-level (extracted constants)

**Error Handling**: 
- If module import fails, raises ImportError
- If constants missing, uses defaults (empty dict/list)

**Example**:
```python
# Internal implementation
def _load_config(self) -> None:
    if self._config_module is None:
        self._config_module = importlib.import_module(self.descriptor.config_module)
    
    self._consolidated_nodes = getattr(self._config_module, 'CONSOLIDATED_NODES', {})
    self._draw_order = getattr(self._config_module, 'DRAW_ORDER', [])
    self._node_variants = getattr(self._config_module, 'NODE_VARIANTS', {})
    self._auto_annotations = getattr(self._config_module, 'AUTO_ANNOTATIONS', {})
```

### Resource Resolution (Cached)

#### `resolve_resource_class(resource_type: str) -> Any`

**Purpose**: Resolve Terraform resource type to Diagrams resource class

**Parameters**:
- `resource_type`: Terraform type string (e.g., `'aws_instance'`, `'azurerm_virtual_machine'`)

**Returns**: Diagrams resource class (e.g., `diagrams.aws.compute.EC2`)

**Caching**: `@lru_cache(maxsize=256)` - caches up to 256 unique resource types

**Resolution Strategy**:
1. Delegate to NodeFactory.resolve(descriptor, resource_type)
2. NodeFactory tries provider-specific class
3. Falls back to generic class
4. Final fallback: `diagrams.generic.blank.Blank`

**Complexity**: 
- First call: O(1) module import + class lookup
- Cached calls: O(1) cache hit

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')

# First call: imports diagrams.aws.compute, returns EC2 class
ec2_class = ctx.resolve_resource_class('aws_instance')

# Second call: cache hit, instant return
ec2_class_2 = ctx.resolve_resource_class('aws_instance')
assert ec2_class is ec2_class_2  # Same object
```

**Error Handling**: Never raises (NodeFactory returns Blank on failure)

#### `resolve_icon_path(resource_type: str, category: str) -> str`

**Purpose**: Resolve icon file path with fallback chain

**Parameters**:
- `resource_type`: Terraform type (e.g., `'aws_s3_bucket'`)
- `category`: Service category from ServiceMapping (e.g., `'storage'`)

**Returns**: Absolute path to .png icon file (always valid)

**Caching**: `@lru_cache(maxsize=256)` - caches up to 256 unique (type, category) pairs

**Fallback Chain**:
1. Provider-specific icon: `{icon_directory}/{category}/{resource_type}.png`
2. Generic category icon: `resource_images/generic/{category}/{category}.png`
3. Blank icon: `resource_images/generic/blank/blank.png`

**Complexity**: 
- First call: O(1) × 3 file existence checks (worst case)
- Cached calls: O(1) cache hit

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')

# Fallback chain for S3 bucket:
icon = ctx.resolve_icon_path('aws_s3_bucket', 'storage')
# 1. Tries: resource_images/aws/storage/aws_s3_bucket.png (exists)
# Returns: 'resource_images/aws/storage/aws_s3_bucket.png'

# Fallback chain for unknown Azure resource:
azure_ctx = ProviderContextRegistry.get('azure')
icon = azure_ctx.resolve_icon_path('azurerm_unknown_service', 'compute')
# 1. Tries: resource_images/azure/compute/azurerm_unknown_service.png (missing)
# 2. Tries: resource_images/generic/compute/compute.png (exists)
# Returns: 'resource_images/generic/compute/compute.png'

# Fallback to blank:
icon = azure_ctx.resolve_icon_path('totally_unknown', 'nonexistent_category')
# 1. Tries: resource_images/azure/nonexistent_category/totally_unknown.png (missing)
# 2. Tries: resource_images/generic/nonexistent_category/nonexistent_category.png (missing)
# 3. Returns: 'resource_images/generic/blank/blank.png'
```

**Invariant**: Always returns a valid file path (never None)

#### `get_service_category(resource_type: str) -> str`

**Purpose**: Get canonical service category for resource type

**Parameters**:
- `resource_type`: Terraform type (e.g., `'aws_instance'`)

**Returns**: Category string (e.g., `'compute.vm'`)

**Delegation**: Calls `ServiceMapping.get_category(resource_type).value`

**Caching**: Not cached (ServiceMapping.get_category is O(1) dict lookup)

**Example**:
```python
ctx = ProviderContextRegistry.get('aws')
category = ctx.get_service_category('aws_instance')
# Returns: 'compute.vm'

# Cross-provider equivalence:
aws_cat = ctx.get_service_category('aws_instance')
azure_ctx = ProviderContextRegistry.get('azure')
azure_cat = azure_ctx.get_service_category('azurerm_virtual_machine')
assert aws_cat == azure_cat  # Both 'compute.vm'
```

**Default**: Returns `'generic'` for unmapped resource types

## Lifecycle

### Creation
```python
# Created by ProviderRegistry.get_context()
descriptor = ProviderRegistry.get_descriptor('aws')
ctx = ProviderContext(descriptor)
```

### Lazy Loading
```python
# First property access triggers module load
order = ctx.draw_order  # Calls _load_config() internally

# Subsequent accesses use cached values
order_2 = ctx.draw_order  # No module load, instant return
```

### Caching
```python
# resolve_resource_class() uses LRU cache
class1 = ctx.resolve_resource_class('aws_instance')  # Cache miss
class2 = ctx.resolve_resource_class('aws_s3_bucket')  # Cache miss
class3 = ctx.resolve_resource_class('aws_instance')  # Cache hit (same as class1)
```

### Singleton per Provider
```python
# ProviderRegistry maintains one context per provider
ctx1 = ProviderContextRegistry.get('aws')
ctx2 = ProviderContextRegistry.get('aws')
assert ctx1 is ctx2  # Same instance
```

## Performance Characteristics

| Operation | First Call | Cached Call | Notes |
|-----------|------------|-------------|-------|
| `__init__()` | <1ms | N/A | No module loading |
| `.draw_order` (first access) | 10-20ms | <1ms | Imports config module |
| `.draw_order` (subsequent) | <1ms | <1ms | Uses cached instance var |
| `.resolve_resource_class()` | 5-10ms | <1μs | First: import class, Cached: dict lookup |
| `.resolve_icon_path()` | 1-5ms | <1μs | First: 3× os.path.exists, Cached: dict lookup |
| `.get_service_category()` | <1μs | <1μs | Delegates to O(1) dict lookup |

**Memory Usage** (per context instance):
- Descriptor reference: ~1KB
- Config constants: ~50-100KB (AWS has 200+ resource types)
- LRU caches: ~10-20KB (256 entries × 2 caches)
- **Total**: ~70-120KB per provider

**Expected Contexts**: 1-3 per CLI invocation (AWS-only = 1, mixed-cloud = 2-3)

## Thread Safety

**Not Thread-Safe**: ProviderContext is designed for single-threaded CLI execution.

**Concurrent Access Issues**:
- Lazy loading: Multiple threads may trigger `_load_config()` simultaneously
- Cache updates: LRU cache is not thread-safe without lock

**Mitigation** (if needed for future server mode):
```python
import threading

class ProviderContext:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self._lock = threading.Lock()
        # ...
    
    def _load_config(self):
        with self._lock:
            if self._config_module is None:
                # Load module under lock
                ...
```

## Error Handling

### Config Loading Errors
```python
# Missing config module
try:
    bad_descriptor = ProviderDescriptor(config_module='nonexistent.module', ...)
    ctx = ProviderContext(bad_descriptor)
    order = ctx.draw_order  # Triggers _load_config()
except ImportError as e:
    # "No module named 'nonexistent'"
    click.echo(click.style(f"Failed to load provider config: {e}", fg='red'))
    sys.exit(1)
```

### Resource Resolution Fallback
```python
# Unknown resource type: no error, returns generic Blank class
ctx = ProviderContextRegistry.get('aws')
unknown_class = ctx.resolve_resource_class('custom_unknown_resource')
assert unknown_class == diagrams.generic.blank.Blank
```

### Icon Resolution Fallback
```python
# Missing icon: no error, returns blank icon path
ctx = ProviderContextRegistry.get('azure')
icon = ctx.resolve_icon_path('azurerm_nonexistent', 'unknown_category')
assert icon == 'resource_images/generic/blank/blank.png'
assert os.path.exists(icon)  # Guaranteed to exist
```

## Testing Contract

### Unit Tests

```python
# tests/unit/test_provider_context.py
import pytest
from modules.provider_runtime import ProviderContext, ProviderDescriptor, ProviderRegistry

class TestProviderContext:
    def test_lazy_loading(self):
        """Config module not loaded until first property access"""
        descriptor = ProviderRegistry.get_descriptor('aws')
        ctx = ProviderContext(descriptor)
        
        # Module not loaded yet
        assert ctx._config_module is None
        
        # First property access triggers load
        _ = ctx.draw_order
        assert ctx._config_module is not None
    
    def test_caching(self):
        """Subsequent property accesses use cached values"""
        ctx = ProviderContextRegistry.get('aws')
        
        order1 = ctx.draw_order
        order2 = ctx.draw_order
        
        # Same object (not re-loaded)
        assert order1 is order2
    
    def test_resolve_resource_class_caching(self):
        """resolve_resource_class uses LRU cache"""
        ctx = ProviderContextRegistry.get('aws')
        
        class1 = ctx.resolve_resource_class('aws_instance')
        class2 = ctx.resolve_resource_class('aws_instance')
        
        # Cache hit: same object
        assert class1 is class2
    
    def test_icon_fallback_chain(self):
        """Icon resolution falls back through 3 levels"""
        ctx = ProviderContextRegistry.get('aws')
        
        # Known AWS icon
        icon = ctx.resolve_icon_path('aws_s3_bucket', 'storage')
        assert 'aws/storage' in icon
        
        # Unknown resource -> generic category
        ctx_azure = ProviderContextRegistry.get('azure')
        icon = ctx_azure.resolve_icon_path('azurerm_unknown', 'compute')
        assert 'generic/compute' in icon
        
        # Unknown category -> blank
        icon = ctx_azure.resolve_icon_path('unknown', 'nonexistent')
        assert 'generic/blank' in icon
    
    def test_service_category_cross_provider(self):
        """Service categories consistent across providers"""
        aws_ctx = ProviderContextRegistry.get('aws')
        azure_ctx = ProviderContextRegistry.get('azure')
        
        aws_cat = aws_ctx.get_service_category('aws_instance')
        azure_cat = azure_ctx.get_service_category('azurerm_virtual_machine')
        
        assert aws_cat == azure_cat == 'compute.vm'
```

## Usage Examples

### Basic Context Usage
```python
# Get AWS context
ctx = ProviderContextRegistry.get('aws')

# Access configuration
vpc_endpoints = ctx.consolidated_nodes.get('aws_vpc_endpoint', [])
resource_order = ctx.draw_order

# Resolve resources
ec2_class = ctx.resolve_resource_class('aws_instance')
s3_icon = ctx.resolve_icon_path('aws_s3_bucket', 'storage')
```

### Mixed-Provider Diagram
```python
# Detect providers from Terraform
providers = ProviderRegistry.detect_providers(tfdata)  # {'aws', 'azure'}

# Get contexts for each provider
contexts = {p: ProviderContextRegistry.get(p) for p in providers}

# Build graph with provider-aware resolution
for resource_type, resource_data in tfdata['all_resource'].items():
    provider = resource_data['provider_name'].split('/')[-1]
    ctx = contexts[provider]
    
    # Use provider-specific config
    resource_class = ctx.resolve_resource_class(resource_type)
    icon_path = ctx.resolve_icon_path(resource_type, ctx.get_service_category(resource_type))
```

### Core Module Integration
```python
# graphmaker.py uses context for consolidation rules
def build_graph(tfdata, provider='aws'):
    ctx = ProviderContextRegistry.get(provider)
    
    # Apply provider-specific consolidation
    for parent, children in ctx.consolidated_nodes.items():
        # Group nodes...
        pass

# drawing.py uses context for resource classes
def render_node(resource_type, provider='aws'):
    ctx = ProviderContextRegistry.get(provider)
    
    category = ctx.get_service_category(resource_type)
    resource_class = ctx.resolve_resource_class(resource_type)
    icon = ctx.resolve_icon_path(resource_type, category)
    
    # Create diagram node...
```

## Related Contracts

- [ProviderDescriptor](./provider_descriptor.md) - Immutable metadata used to initialize ProviderContext
- [ProviderRegistry](../data-model.md#3-providerregistry) - Manages context singleton instances
- [ServiceMapping](./service_mapping.md) - Used by `get_service_category()` method

## Changelog

### v1.0.0 (2025-11-26)
- Initial contract definition
- Lazy loading pattern for config
- LRU caching for resource/icon resolution
- 3-level icon fallback chain
