# Contract: Helper Modules

**Version**: 1.0.0  
**Status**: Approved  
**Modules**: `modules/utils/*.py` (new), `modules/helpers.py` (deprecated)

## Purpose

Organize utility functions into focused modules for improved discoverability and testability, while maintaining backward compatibility.

## Module Structure

```text
modules/
├── helpers.py              # DEPRECATED: backward compatibility shim
└── utils/
    ├── __init__.py         # Re-exports all utilities
    ├── string_utils.py     # Text parsing and manipulation
    ├── terraform_utils.py  # Terraform-specific operations
    ├── graph_utils.py      # Graph data structure operations
    └── provider_utils.py   # Provider detection and configuration
```

## Interface Contracts

### String Utilities (`modules/utils/string_utils.py`)

```python
"""String parsing and manipulation utilities."""

from typing import Optional

def find_between(
    text: str,
    begin: str,
    end: str,
    alternative: str = "",
    replace: bool = False,
    occurrence: int = 1
) -> str:
    """Extract text between two delimiters.
    
    Handles nested delimiters correctly using stack-based parsing for parentheses.
    
    Args:
        text: Source text to search
        begin: Starting delimiter
        end: Ending delimiter
        alternative: Replacement text if replace=True
        replace: If True, replace extracted text with alternative
        occurrence: Which occurrence to extract (1-indexed)
    
    Returns:
        Extracted text between delimiters, or empty string if not found.
        If replace=True, returns modified text with replacement applied.
    
    Performance:
        O(n) where n is length of text
    
    Examples:
        >>> find_between("start (content) end", "(", ")")
        'content'
        >>> find_between("a (b (c) d) e", "(", ")", occurrence=1)
        'b (c) d'
        >>> find_between("x [y] z", "[", "]", alternative="replaced", replace=True)
        'x replaced z'
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
    
    Examples:
        >>> find_nth("a b a c a", "a", 2)
        4
        >>> find_nth("test", "x", 1)
        -1
    """
    pass
```

**Guarantees**:
- Handles nested parentheses correctly (no mismatched paren bugs)
- Returns empty string (not None) for not-found cases
- 1-indexed occurrence parameter (consistent with human counting)
- O(n) time complexity

---

### Terraform Utilities (`modules/utils/terraform_utils.py`)

```python
"""Terraform-specific parsing and variable resolution utilities."""

from typing import Any, Union, Dict, List, Optional
from modules.exceptions import TerraformParsingError

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
    
    Examples:
        >>> data = {"resource": {"aws_vpc": {"main": {"cidr": "10.0.0.0/16"}}}}
        >>> getvar(data, "resource.aws_vpc.main.cidr")
        '10.0.0.0/16'
        >>> getvar(data, "nonexistent.path", default="N/A")
        'N/A'
    """
    pass


def tfvar_read(tfvars_path: str) -> Dict[str, Any]:
    """Read and parse Terraform .tfvars file.
    
    Args:
        tfvars_path: Path to .tfvars file
    
    Returns:
        Dict of variable name to value mappings
    
    Raises:
        TerraformParsingError: If file cannot be parsed or doesn't exist
    
    Examples:
        >>> vars = tfvar_read("terraform.tfvars")
        >>> print(vars["region"])
        'us-east-1'
    """
    pass
```

**Guarantees**:
- Never raises KeyError/IndexError (returns default instead)
- Supports nested access with dot notation
- Raises TerraformParsingError with file path and parse error context
- Handles HCL2 and JSON .tfvars formats

---

### Graph Utilities (`modules/utils/graph_utils.py`)

```python
"""Graph data structure operations for Terraform resource graphs."""

from typing import Dict, List, Any, Optional
from modules.exceptions import MetadataInconsistencyError

def list_of_dictkeys_containing(
    graphdict: Dict[str, List[str]],
    pattern: str
) -> List[str]:
    """Find all graph node keys containing pattern.
    
    Args:
        graphdict: Graph adjacency list
        pattern: Substring to match in keys
    
    Returns:
        List of matching keys (unsorted)
    
    Performance:
        O(n) where n is number of keys in graphdict
    
    Examples:
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
        Sorted list of common elements (deterministic output)
    
    Performance:
        O(n+m) where n=len(list1), m=len(list2)
        Previous implementation: O(n*m) with nested loops
    
    Examples:
        >>> find_common_elements(["a", "b", "c"], ["b", "c", "d"])
        ['b', 'c']
    """
    pass


def ensure_metadata(
    tfdata: Dict[str, Any],
    node_key: str,
    defaults: Optional[Dict[str, Any]] = None
) -> None:
    """Ensure metadata entry exists for graph node.
    
    Creates metadata entry if missing. Raises error if node exists in
    graphdict but not in metadata (indicates inconsistency).
    
    Args:
        tfdata: Terraform data dictionary
        node_key: Graph node key to check
        defaults: Default metadata values (uses empty dict if None)
    
    Raises:
        MetadataInconsistencyError: If node in graphdict but not metadata
    
    Side Effects:
        Modifies tfdata["metadata"] in place
    
    Examples:
        >>> tfdata = {"graphdict": {"aws_vpc.main": []}, "metadata": {}}
        >>> ensure_metadata(tfdata, "aws_vpc.main", {"count": "1"})
        >>> print(tfdata["metadata"]["aws_vpc.main"])
        {'count': '1'}
    """
    pass


def validate_metadata_consistency(tfdata: Dict[str, Any]) -> List[str]:
    """Validate metadata consistency with graphdict.
    
    Args:
        tfdata: Terraform data dictionary
    
    Returns:
        List of error messages (empty list if valid)
    
    Checks:
        - All graphdict keys have metadata entries
        - All metadata entries have required fields (count, provider, type)
        - Parent references (vpc_id, etc.) point to existing nodes
    
    Examples:
        >>> tfdata = {"graphdict": {"a": []}, "metadata": {}}
        >>> errors = validate_metadata_consistency(tfdata)
        >>> print(errors)
        ['Node "a" in graphdict but missing from metadata']
    """
    pass
```

**Guarantees**:
- `find_common_elements`: Returns sorted list (deterministic)
- `ensure_metadata`: Modifies tfdata in place (no return value)
- `validate_metadata_consistency`: Never raises, always returns error list
- All functions handle empty inputs gracefully

---

### Provider Utilities (`modules/utils/provider_utils.py`)

```python
"""Provider detection and configuration utilities."""

from typing import List
from modules.exceptions import ProviderDetectionError
from modules.cloud_config import ProviderRegistry, ProviderConfig

def detect_provider(resource_names: List[str]) -> str:
    """Detect cloud provider from Terraform resource names.
    
    Args:
        resource_names: List of Terraform resource identifiers
    
    Returns:
        Provider name: 'aws', 'azure', 'gcp', or 'unknown'
    
    Raises:
        ProviderDetectionError: If mixed providers detected
    
    Logic:
        - 'aws_*' → 'aws'
        - 'azurerm_*' → 'azure'
        - 'google_*' → 'gcp'
        - Mixed providers → raise ProviderDetectionError
        - No matches → 'unknown'
    
    Examples:
        >>> detect_provider(["aws_vpc.main", "aws_subnet.private"])
        'aws'
        >>> detect_provider(["azurerm_virtual_network.vnet"])
        'azure'
        >>> detect_provider(["aws_vpc.main", "azurerm_vnet.vnet"])
        ProviderDetectionError: Mixed providers detected
    """
    pass


def get_provider_config(provider: str) -> ProviderConfig:
    """Get provider-specific configuration from ProviderRegistry.
    
    Args:
        provider: Provider name ('aws', 'azure', 'gcp')
    
    Returns:
        ProviderConfig with consolidated_nodes, icon_paths, etc.
    
    Raises:
        ValueError: If provider name not recognized
    
    Examples:
        >>> config = get_provider_config('aws')
        >>> print(config.consolidated_nodes)
        ['aws_security_group', 'aws_vpc', ...]
    """
    pass
```

**Guarantees**:
- `detect_provider`: Raises on mixed providers (never silently defaults)
- `get_provider_config`: Always returns valid ProviderConfig or raises
- No global state (functions are stateless)

---

## Backward Compatibility Shim

### `modules/helpers.py` (Deprecated)

```python
"""DEPRECATED: Use modules.utils.* instead.

This module is maintained for backward compatibility during transition.
Will be removed in a future version.
"""

import warnings
from modules.utils import *

# Emit deprecation warning when imported
warnings.warn(
    "modules.helpers is deprecated. Use modules.utils.* instead:\n"
    "  - string operations: modules.utils.string_utils\n"
    "  - terraform operations: modules.utils.terraform_utils\n"
    "  - graph operations: modules.utils.graph_utils\n"
    "  - provider operations: modules.utils.provider_utils",
    DeprecationWarning,
    stacklevel=2
)
```

### `modules/utils/__init__.py` (Re-exports)

```python
"""Utility modules for TerraVision."""

# Re-export all utilities for convenience
from .string_utils import find_between, find_nth
from .terraform_utils import getvar, tfvar_read
from .graph_utils import (
    list_of_dictkeys_containing,
    find_common_elements,
    ensure_metadata,
    validate_metadata_consistency
)
from .provider_utils import detect_provider, get_provider_config

__all__ = [
    # String utilities
    'find_between',
    'find_nth',
    # Terraform utilities
    'getvar',
    'tfvar_read',
    # Graph utilities
    'list_of_dictkeys_containing',
    'find_common_elements',
    'ensure_metadata',
    'validate_metadata_consistency',
    # Provider utilities
    'detect_provider',
    'get_provider_config',
]
```

## Migration Path

### Phase 1: Create New Modules
- Create `modules/utils/` directory
- Implement `string_utils.py`, `terraform_utils.py`, `graph_utils.py`, `provider_utils.py`
- Create `modules/utils/__init__.py` with re-exports

### Phase 2: Backward Compatibility
- Update `modules/helpers.py` to re-export from `modules.utils`
- Add deprecation warnings

### Phase 3: Internal Migration
- Update internal code to use `modules.utils.*` imports
- Keep `helpers.py` for external users

### Phase 4: Future Removal
- (Future release) Remove `helpers.py` after deprecation period

## Testing Requirements

```python
# tests/unit/test_string_utils.py
def test_find_between_nested_parens():
    """Should handle nested parentheses correctly."""
    assert find_between("a (b (c) d) e", "(", ")") == "b (c) d"

def test_find_nth_occurrence():
    """Should find correct nth occurrence."""
    assert find_nth("a b a c a", "a", 2) == 4

# tests/unit/test_graph_utils.py
def test_find_common_elements_performance():
    """Should use set intersection (O(n+m)) not nested loops (O(n*m))."""
    import time
    list1 = [str(i) for i in range(1000)]
    list2 = [str(i) for i in range(500, 1500)]
    
    start = time.time()
    result = find_common_elements(list1, list2)
    elapsed = time.time() - start
    
    assert elapsed < 0.01  # Should be fast
    assert len(result) == 500  # Correct result

def test_ensure_metadata_creates_entry():
    """Should create metadata entry if missing."""
    tfdata = {"graphdict": {}, "metadata": {}}
    ensure_metadata(tfdata, "aws_vpc.main", {"count": "1"})
    assert "aws_vpc.main" in tfdata["metadata"]
```

## Contract Guarantees

1. **Import Paths**: Both `import modules.helpers` and `import modules.utils.string_utils` work
2. **No Breaking Changes**: Existing code using helpers.py continues to work
3. **Deprecation Warnings**: Users get clear migration guidance
4. **Type Hints**: All new modules have comprehensive type hints
5. **Docstrings**: All functions have Google-style docstrings with examples
6. **Testing**: Each module has dedicated unit test file
7. **Performance**: Optimized implementations (set operations, no nested loops)
