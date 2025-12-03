# Quickstart: Contributing Code Quality Fixes

**Feature**: Code Quality and Reliability Improvements  
**Branch**: `002-code-quality-fixes`  
**Date**: 2025-12-01

## Overview

This guide helps developers contribute to TerraVision code quality improvements. Covers setup, development workflow, testing, and submission process.

---

## Prerequisites

### Required Tools

- **Python**: 3.9-3.11 (strict requirement)
- **Poetry**: Package manager for dependencies
- **Git**: Version control
- **Graphviz**: For diagram rendering (optional for pure code fixes)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/terravision.git
cd terravision

# Checkout feature branch
git checkout 002-code-quality-fixes

# Install dependencies
poetry install

# Install pre-commit hooks
poetry run pre-commit install

# Verify installation
poetry run pytest -m "not slow"  # Should pass all fast tests
```

---

## Development Environment Setup

### IDE Configuration

**VS Code** (`settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length=88"],
  "editor.formatOnSave": true,
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

**PyCharm**:
- File > Settings > Tools > Black: Enable
- File > Settings > Tools > Python Integrated Tools > Default test runner: pytest

### Running Tests Locally

```bash
# Run all fast tests (pre-commit default)
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_aws_handlers.py

# Run with coverage
poetry run pytest --cov=modules --cov-report=html
open htmlcov/index.html

# Run including slow integration tests
poetry run pytest -m ""

# Run single test method
poetry run pytest tests/unit/test_aws_handlers.py::TestAWSHandleVPCEndpoints::test_no_vpc_raises_error -v
```

### Code Formatting

```bash
# Format all code
poetry run black .
poetry run isort .

# Check formatting without changes
poetry run black --check .

# Run all pre-commit checks
poetry run pre-commit run --all-files
```

---

## Contribution Workflow

### 1. Pick an Issue

Review `docs/TO_BE_FIXED.md` and choose issue by priority:

- **P1 (High)**: Critical reliability (bare exceptions, missing VPC checks, sys.exit in library)
- **P2 (Medium)**: Azure/GCP provider support (implement handler stubs)
- **P3 (Low)**: Developer experience (split helpers.py, add tests)
- **P4 (Low)**: Performance optimizations (find_common_elements, caching)

### 2. Create Implementation Branch

```bash
# Create branch for your fix
git checkout -b fix/issue-1-5-bare-exception-aws-autoscaling

# Or for feature work
git checkout -b feature/azure-vnet-subnet-handler
```

### 3. Implement Fix

#### Example: Fix Bare Exception (P1)

**Before** (`modules/resource_handlers/aws.py` lines 52-95):
```python
try:
    # ... complex logic ...
except:
    pass  # BAD: swallows all exceptions
```

**After**:
```python
from modules.exceptions import MissingResourceError

try:
    scaler_links = next(
        v for k, v in tfdata["graphdict"].items()
        if "aws_appautoscaling_target" in k
    )
    # ... rest of logic ...
except StopIteration:
    # Expected: no autoscaling targets found
    click.echo(click.style(
        "INFO: No autoscaling targets found; skipping autoscaling handling",
        fg="yellow"
    ))
    return tfdata
except (KeyError, TypeError) as e:
    # Unexpected: metadata missing or invalid
    click.echo(click.style(
        f"WARNING: Skipping autoscaling handling due to invalid data: {e}",
        fg="yellow",
        bold=True
    ))
    return tfdata
```

#### Example: Implement Azure Handler (P2)

**File**: `modules/resource_handlers/azure.py`

```python
from typing import Dict, Any, List
from modules.exceptions import MissingResourceError
from modules.utils.graph_utils import list_of_dictkeys_containing, ensure_metadata
import click

def azure_handle_vnet_subnets(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group Azure subnets under parent VNets.
    
    Args:
        tfdata: Terraform data dictionary
    
    Returns:
        Updated tfdata with subnets grouped under VNets
    
    Raises:
        MissingResourceError: If no VNets found but subnets exist
    """
    vnets = list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_virtual_network")
    subnets = list_of_dictkeys_containing(tfdata["graphdict"], "azurerm_subnet")
    
    if not vnets and subnets:
        raise MissingResourceError(
            "No Azure VNets found but subnets exist",
            resource_type="azurerm_virtual_network",
            required_by="azure_handle_vnet_subnets"
        )
    
    if not vnets:
        # No VNets or subnets - nothing to do
        return tfdata
    
    # Group subnets under their parent VNet
    for subnet in subnets:
        subnet_meta = tfdata["metadata"].get(subnet, {})
        vnet_name = subnet_meta.get("virtual_network_name")
        
        # Find matching VNet
        matching_vnet = next(
            (v for v in vnets if vnet_name and vnet_name in v),
            vnets[0]  # Default to first VNet if no match
        )
        
        # Move subnet under VNet
        tfdata["graphdict"][matching_vnet].append(subnet)
        del tfdata["graphdict"][subnet]
    
    return tfdata
```

### 4. Write Tests

**File**: `tests/unit/test_azure_handlers.py`

```python
import pytest
from modules.resource_handlers.azure import azure_handle_vnet_subnets
from modules.exceptions import MissingResourceError
from tests.fixtures.tfdata_samples import minimal_tfdata, vnet_tfdata

class TestAzureHandleVNetSubnets:
    """Unit tests for azure_handle_vnet_subnets handler."""
    
    def test_no_vnet_with_subnets_raises_error(self):
        """Should raise error when subnets exist without VNets."""
        tfdata = minimal_tfdata()
        tfdata["graphdict"]["azurerm_subnet.sub1"] = []
        tfdata["metadata"]["azurerm_subnet.sub1"] = {
            "count": "1",
            "provider": "azure",
            "type": "azurerm_subnet"
        }
        
        with pytest.raises(MissingResourceError, match="No Azure VNets"):
            azure_handle_vnet_subnets(tfdata)
    
    def test_groups_subnets_under_vnet(self):
        """Should move subnets under parent VNet."""
        tfdata = vnet_tfdata(vnet_count=1, subnet_count=2)
        
        result = azure_handle_vnet_subnets(tfdata)
        
        assert "azurerm_subnet.subnet0_0" in result["graphdict"]["azurerm_virtual_network.vnet0"]
        assert "azurerm_subnet.subnet0_0" not in result["graphdict"]
    
    def test_preserves_subnet_metadata(self):
        """Should maintain subnet metadata after grouping."""
        tfdata = vnet_tfdata(vnet_count=1, subnet_count=1)
        original_meta = tfdata["metadata"]["azurerm_subnet.subnet0_0"].copy()
        
        result = azure_handle_vnet_subnets(tfdata)
        
        assert result["metadata"]["azurerm_subnet.subnet0_0"] == original_meta
```

### 5. Run Quality Checks

```bash
# Format code
poetry run black .
poetry run isort .

# Run tests
poetry run pytest tests/unit/test_azure_handlers.py -v

# Check coverage
poetry run pytest --cov=modules.resource_handlers.azure --cov-report=term-missing

# Run pre-commit checks
poetry run pre-commit run --all-files
```

### 6. Commit Changes

```bash
# Stage changes
git add modules/resource_handlers/azure.py
git add tests/unit/test_azure_handlers.py
git add tests/fixtures/tfdata_samples.py  # If you added fixtures

# Commit with descriptive message
git commit -m "Implement Azure VNet/subnet grouping handler

- Add azure_handle_vnet_subnets() to group subnets under VNets
- Match subnets to VNets via virtual_network_name metadata
- Add comprehensive unit tests with 100% coverage
- Follows AWS handler patterns adapted for Azure

Closes #45"
```

### 7. Push and Create PR

```bash
# Push branch
git push origin feature/azure-vnet-subnet-handler

# Create PR via GitHub CLI or web interface
gh pr create --title "Implement Azure VNet/subnet grouping handler" \
  --body "Implements azure_handle_vnet_subnets() following research patterns from research.md.

**Changes**:
- New handler in modules/resource_handlers/azure.py
- Unit tests in tests/unit/test_azure_handlers.py
- Updated vnet_tfdata fixture in tests/fixtures/tfdata_samples.py

**Testing**:
- 100% coverage for new handler
- All existing tests pass
- Pre-commit hooks pass

Closes #45"
```

---

## Common Tasks

### Adding a New Exception Type

1. **Define in `modules/exceptions.py`**:
```python
class NewCustomError(TerraVisionError):
    """Description of error."""
    def __init__(self, message: str, context_field: str):
        super().__init__(message, {"context_field": context_field})
        self.context_field = context_field
```

2. **Write tests in `tests/unit/test_exceptions.py`**:
```python
def test_new_custom_error_has_attributes():
    exc = NewCustomError("test", context_field="value")
    assert exc.context_field == "value"
    assert "value" in str(exc)
```

3. **Use in handler code**:
```python
from modules.exceptions import NewCustomError

def handler(tfdata):
    if invalid_condition:
        raise NewCustomError("Explanation", context_field="details")
```

### Splitting Function from helpers.py to utils/

1. **Copy function to new module** (e.g., `modules/utils/string_utils.py`)
2. **Add to `modules/utils/__init__.py` exports**
3. **Update `modules/helpers.py`** to re-export from utils
4. **Add deprecation warning** in helpers.py
5. **Write unit tests** in `tests/unit/test_string_utils.py`
6. **Update internal imports** to use `modules.utils.*`

### Adding Test Fixtures

1. **Add factory function to `tests/fixtures/tfdata_samples.py`**:
```python
def new_resource_tfdata(count: int = 1) -> Dict[str, Any]:
    """Create tfdata with new resource type."""
    tfdata = minimal_tfdata()
    for i in range(count):
        key = f"resource.name{i}"
        tfdata["graphdict"][key] = []
        tfdata["metadata"][key] = {"count": "1", "provider": "aws"}
    return tfdata
```

2. **Use in tests**:
```python
def test_handler():
    tfdata = new_resource_tfdata(count=5)
    result = handler(tfdata)
    # assertions...
```

---

## Troubleshooting

### Tests Failing Locally

```bash
# Check Python version (must be 3.9-3.11)
python --version

# Clear cache and reinstall
rm -rf .pytest_cache __pycache__ modules/__pycache__
poetry install --no-cache

# Run single test to isolate issue
poetry run pytest tests/unit/test_file.py::TestClass::test_method -vv
```

### Pre-commit Hooks Failing

```bash
# See what failed
poetry run pre-commit run --all-files

# Fix formatting
poetry run black .
poetry run isort .

# Skip hooks temporarily (NOT recommended for final commit)
git commit --no-verify
```

### Import Errors

```bash
# Ensure module path is correct
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use poetry run
poetry run python -c "from modules.utils.string_utils import find_between; print('OK')"
```

### Coverage Too Low

```bash
# See which lines are missing coverage
poetry run pytest --cov=modules --cov-report=term-missing

# Add tests for uncovered lines
# Aim for 80%+ overall, 90%+ for handlers
```

---

## Code Review Checklist

Before submitting PR, verify:

- [ ] **Tests pass**: `poetry run pytest`
- [ ] **Coverage adequate**: 80%+ overall, 90%+ for new handlers
- [ ] **Formatting correct**: `poetry run black --check .`
- [ ] **Imports organized**: `poetry run isort --check .`
- [ ] **Pre-commit hooks pass**: `poetry run pre-commit run --all-files`
- [ ] **Type hints present**: All public functions have type annotations
- [ ] **Docstrings complete**: Google-style docstrings with Args/Returns/Raises
- [ ] **Exceptions specific**: No bare `except:`, specific exception types only
- [ ] **Metadata handled**: New graph nodes have corresponding metadata entries
- [ ] **Constitution compliant**: Changes align with TerraVision principles
- [ ] **Commit message descriptive**: Explains "why" not just "what"

---

## Resources

### Documentation
- **Constitution**: `.specify/memory/constitution.md`
- **Code Review Issues**: `docs/TO_BE_FIXED.md`
- **Research Decisions**: `specs/002-code-quality-fixes/research.md`
- **Data Model**: `specs/002-code-quality-fixes/data-model.md`
- **Contracts**: `specs/002-code-quality-fixes/contracts/`

### Key Files
- **Exception Types**: `modules/exceptions.py` (create new)
- **AWS Handlers**: `modules/resource_handlers/aws.py`
- **Azure Handlers**: `modules/resource_handlers/azure.py`
- **GCP Handlers**: `modules/resource_handlers/gcp.py`
- **Test Fixtures**: `tests/fixtures/tfdata_samples.py`
- **Agent Guidelines**: `AGENTS.md`

### Commands
```bash
# Install dependencies
poetry install

# Run fast tests
poetry run pytest

# Run all tests (including slow)
poetry run pytest -m ""

# Run specific test
poetry run pytest tests/unit/test_aws_handlers.py::TestClass::test_method -v

# Check coverage
poetry run pytest --cov=modules --cov-report=html

# Format code
poetry run black .
poetry run isort .

# Pre-commit checks
poetry run pre-commit run --all-files

# Single test example
poetry run pytest tests/helpers_unit_test.py::TestGetvar::test_getvar_from_dict -v
```

---

## Getting Help

- **Questions**: Open issue with `question` label
- **Bugs**: Open issue with `bug` label and reference `docs/TO_BE_FIXED.md` entry
- **Discussions**: GitHub Discussions for architecture questions

---

## Example: Complete Fix Workflow

**Scenario**: Fix bare exception in `aws_handle_autoscaling` (Issue 1.5)

```bash
# 1. Create branch
git checkout -b fix/issue-1-5-bare-exception-aws-autoscaling

# 2. Edit handler
# modules/resource_handlers/aws.py lines 52-95
# Replace bare except: with specific exceptions

# 3. Write test
# tests/unit/test_aws_handlers.py
# Add TestAWSHandleAutoscaling class

# 4. Run tests
poetry run pytest tests/unit/test_aws_handlers.py::TestAWSHandleAutoscaling -v

# 5. Format code
poetry run black .
poetry run isort .

# 6. Check coverage
poetry run pytest --cov=modules.resource_handlers.aws --cov-report=term-missing

# 7. Pre-commit checks
poetry run pre-commit run --all-files

# 8. Commit
git add modules/resource_handlers/aws.py tests/unit/test_aws_handlers.py
git commit -m "Fix bare exception in aws_handle_autoscaling

Replace bare except: with specific exception handling:
- StopIteration: when no autoscaling targets found (expected)
- KeyError/TypeError: when metadata missing or invalid (log warning)

Add comprehensive unit tests covering:
- Missing autoscaling targets (StopIteration case)
- Invalid metadata (KeyError case)
- Successful processing (happy path)

Closes #XX"

# 9. Push and create PR
git push origin fix/issue-1-5-bare-exception-aws-autoscaling
gh pr create --title "Fix bare exception in aws_handle_autoscaling" \
  --body "Fixes issue 1.5 from docs/TO_BE_FIXED.md..."
```

---

## Summary

This quickstart covered:
- ✅ Environment setup with Poetry and pre-commit hooks
- ✅ Development workflow from issue selection to PR
- ✅ Testing patterns and coverage requirements
- ✅ Code quality standards and formatting
- ✅ Common tasks and troubleshooting
- ✅ Complete example workflow

Ready to contribute! Pick an issue from `docs/TO_BE_FIXED.md` and follow this guide.
