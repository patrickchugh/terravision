# Contract: Exception Types

**Version**: 1.0.0  
**Status**: Approved  
**Module**: `modules/exceptions.py` (new)

## Purpose

Define custom exception types for TerraVision library code, enabling proper error handling separation between library and CLI layers.

## Interface

### Base Exception

```python
class TerraVisionError(Exception):
    """Base exception for all TerraVision errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize exception with message and optional context.
        
        Args:
            message: Human-readable error description
            context: Optional dict with additional error context
        """
        self.message = message
        self.context = context or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.context:
            return f"{self.message} (context: {self.context})"
        return self.message
```

### Specific Exceptions

```python
class MissingResourceError(TerraVisionError):
    """Required resource not found in Terraform data."""
    
    def __init__(self, message: str, resource_type: str, required_by: str):
        """Initialize with resource details.
        
        Args:
            message: Error description
            resource_type: Type of missing resource (e.g., 'aws_vpc')
            required_by: Handler or operation requiring the resource
        """
        super().__init__(message, {
            "resource_type": resource_type,
            "required_by": required_by
        })
        self.resource_type = resource_type
        self.required_by = required_by


class ProviderDetectionError(TerraVisionError):
    """Cannot detect cloud provider from resource names."""
    
    def __init__(self, message: str, sample_resources: List[str]):
        """Initialize with sample resources that failed detection.
        
        Args:
            message: Error description
            sample_resources: List of resource names that failed detection
        """
        super().__init__(message, {"sample_resources": sample_resources})
        self.sample_resources = sample_resources


class MetadataInconsistencyError(TerraVisionError):
    """Graph node created without corresponding metadata entry."""
    
    def __init__(self, message: str, node_key: str, operation: str):
        """Initialize with node details.
        
        Args:
            message: Error description
            node_key: Graph node key that's missing metadata
            operation: Operation that created the inconsistency
        """
        super().__init__(message, {
            "node_key": node_key,
            "operation": operation
        })
        self.node_key = node_key
        self.operation = operation


class TerraformParsingError(TerraVisionError):
    """Failed to parse Terraform configuration or state."""
    
    def __init__(self, message: str, file_path: str, parse_error: str):
        """Initialize with parsing details.
        
        Args:
            message: Error description
            file_path: Path to file that failed parsing
            parse_error: Original parsing error message
        """
        super().__init__(message, {
            "file_path": file_path,
            "parse_error": parse_error
        })
        self.file_path = file_path
        self.parse_error = parse_error
```

## Usage Patterns

### Library Code (Raising Exceptions)

```python
# modules/resource_handlers/aws.py
from modules.exceptions import MissingResourceError

def aws_handle_vpcendpoints(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle VPC endpoints."""
    vpcs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_vpc.")
    
    if not vpcs:
        raise MissingResourceError(
            message="No VPC found; cannot process VPC endpoints",
            resource_type="aws_vpc",
            required_by="aws_handle_vpcendpoints"
        )
    
    # ... processing logic
    return tfdata
```

### CLI Code (Catching Exceptions)

```python
# terravision.py
from modules.exceptions import (
    TerraVisionError,
    MissingResourceError,
    ProviderDetectionError
)

@click.command()
def draw(...):
    try:
        tfdata = process_terraform_files(source)
        tfdata = apply_resource_handlers(tfdata)
        
    except MissingResourceError as e:
        # Non-fatal: continue with partial diagram
        click.echo(click.style(
            f"INFO: {e.message}",
            fg="yellow"
        ))
        # Continue processing
        
    except ProviderDetectionError as e:
        # Warning: defaulting to AWS
        click.echo(click.style(
            f"WARNING: {e.message}. Defaulting to AWS.",
            fg="yellow",
            bold=True
        ))
        # Continue with AWS provider
        
    except TerraVisionError as e:
        # Fatal: cannot proceed
        click.echo(click.style(
            f"ERROR: {e.message}",
            fg="red",
            bold=True
        ))
        sys.exit(1)
```

## Contract Guarantees

1. **Inheritance**: All exceptions inherit from `TerraVisionError`
2. **Context Preservation**: All exceptions store structured context in `.context` dict
3. **Type-Specific Attributes**: Each exception type exposes relevant attributes (e.g., `resource_type`, `file_path`)
4. **String Representation**: All exceptions have meaningful `__str__()` output including context
5. **No sys.exit()**: Library code never calls sys.exit(), only raises exceptions
6. **Serializable Context**: Exception context is JSON-serializable for logging

## Testing Requirements

### Unit Tests (test_exceptions.py)

```python
def test_base_exception_stores_context():
    """TerraVisionError should store context dict."""
    exc = TerraVisionError("test error", {"key": "value"})
    assert exc.context == {"key": "value"}
    assert "key" in str(exc)

def test_missing_resource_error_has_attributes():
    """MissingResourceError should expose resource_type and required_by."""
    exc = MissingResourceError(
        "No VPC found",
        resource_type="aws_vpc",
        required_by="aws_handle_vpcendpoints"
    )
    assert exc.resource_type == "aws_vpc"
    assert exc.required_by == "aws_handle_vpcendpoints"
    assert "aws_vpc" in exc.context["resource_type"]

def test_exception_hierarchy():
    """All custom exceptions should inherit from TerraVisionError."""
    assert issubclass(MissingResourceError, TerraVisionError)
    assert issubclass(ProviderDetectionError, TerraVisionError)
    assert issubclass(MetadataInconsistencyError, TerraVisionError)
    assert issubclass(TerraformParsingError, TerraVisionError)
```

## Migration Notes

**Existing Code Impact**:
- Replace bare `except:` blocks with specific exception types
- Replace `sys.exit()` calls in library code with exceptions
- Update CLI error handling to catch and format exceptions

**Backward Compatibility**:
- New module; no breaking changes
- Existing code continues to work until migrated
