"""Custom exception types for TerraVision.

This module defines the exception hierarchy for TerraVision errors, enabling
precise error handling and contextual error messages throughout the application.

Exception Hierarchy:
    TerraVisionError (base)
    ├── MissingResourceError - Required resources not found in tfdata
    ├── ProviderDetectionError - Unable to detect cloud provider
    ├── MetadataInconsistencyError - Graph metadata validation failures
    └── TerraformParsingError - Terraform file parsing failures
"""

from typing import Any, Dict, Optional


class TerraVisionError(Exception):
    """Base exception for all TerraVision-specific errors.

    Attributes:
        message: Human-readable error description
        context: Additional contextual information (e.g., resource IDs, file paths)
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize TerraVisionError.

        Args:
            message: Human-readable error description
            context: Optional dict with additional context (resource IDs, paths, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message


class MissingResourceError(TerraVisionError):
    """Raised when a required resource is not found in tfdata.

    Examples:
        - VPC endpoints defined but no VPCs exist
        - Subnets reference non-existent VNet
        - NAT gateways without parent VPC
    """

    pass


class ProviderDetectionError(TerraVisionError):
    """Raised when cloud provider cannot be detected from resource types.

    Examples:
        - Mixed providers in single config (AWS + Azure + GCP)
        - Unknown resource type prefixes
        - Empty resource list
    """

    pass


class MetadataInconsistencyError(TerraVisionError):
    """Raised when graph metadata validation fails.

    Examples:
        - Missing required metadata keys (name, type, provider)
        - Invalid metadata structure
        - Metadata mismatch between parent and child resources
    """

    pass


class TerraformParsingError(TerraVisionError):
    """Raised when Terraform file parsing fails.

    Examples:
        - Invalid HCL2 syntax
        - Unsupported Terraform version features
        - File read errors
        - JSON parsing failures
    """

    pass
