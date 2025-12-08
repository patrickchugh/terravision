"""
Provider Detection Module for TerraVision Multi-Cloud Support

This module provides functionality to detect cloud providers (AWS, Azure, GCP) from
Terraform project data by analyzing resource name prefixes and provider blocks.

API Version: 1.0.0
Author: TerraVision Multi-Cloud Feature
Date: 2025-12-07
"""

from typing import Dict, List, Any, Tuple
import logging

# Configure logging
logger = logging.getLogger(__name__)


# Constants
PROVIDER_PREFIXES = {
    'aws_': 'aws',
    'azurerm_': 'azure',
    'azuread_': 'azure',      # Azure Active Directory
    'azurestack_': 'azure',
    'azapi_': 'azure',        # Azure API provider
    'google_': 'gcp',
}

SUPPORTED_PROVIDERS = ['aws', 'azure', 'gcp']


# Error Classes
class ProviderDetectionError(Exception):
    """Raised when no cloud providers can be detected in Terraform project."""
    pass


# Type Aliases
ProviderDetectionResult = Dict[str, Any]
ResourcesByProvider = Dict[str, Any]


def get_provider_for_resource(resource_name: str) -> str:
    """
    Determine cloud provider for a single Terraform resource.

    Args:
        resource_name: Full Terraform resource name (e.g., "aws_instance.web")

    Returns:
        Provider name ('aws' | 'azure' | 'gcp' | 'unknown')

    Examples:
        >>> get_provider_for_resource("aws_instance.web")
        'aws'
        >>> get_provider_for_resource("azurerm_virtual_machine.app")
        'azure'
        >>> get_provider_for_resource("google_compute_instance.vm1")
        'gcp'
        >>> get_provider_for_resource("random_string.id")
        'unknown'
    """
    # Strip module prefix if present (e.g., "module.networking.aws_vpc.main")
    if "." in resource_name:
        parts = resource_name.split(".")
        # Find the resource type (e.g., "aws_vpc" from "module.networking.aws_vpc.main")
        for part in parts:
            for prefix, provider in PROVIDER_PREFIXES.items():
                if part.startswith(prefix):
                    return provider

    # Check resource name directly against prefixes
    for prefix, provider in PROVIDER_PREFIXES.items():
        if resource_name.startswith(prefix):
            return provider

    return 'unknown'


def detect_providers(tfdata: Dict[str, Any]) -> ProviderDetectionResult:
    """
    Detect all cloud providers used in Terraform project.

    Analyzes resource names to identify which cloud providers are in use,
    counts resources per provider, and determines the primary provider.

    Args:
        tfdata: Terraform data dictionary containing:
            - all_resource (List[str]): All resource names from Terraform
            - graphdict (Dict): Resource relationship graph
            - meta_data (Dict): Resource metadata

    Returns:
        ProviderDetectionResult dictionary containing:
            - providers (List[str]): List of detected providers
            - primary_provider (str): Provider with most resources
            - resource_counts (Dict[str, int]): Resource count per provider
            - detection_method (str): How providers were detected
            - confidence (float): Detection confidence (0.0 to 1.0)

    Raises:
        ValueError: If tfdata missing required keys
        ProviderDetectionError: If no providers can be detected

    Examples:
        >>> tfdata = {"all_resource": ["aws_instance.web", "aws_s3_bucket.data"]}
        >>> result = detect_providers(tfdata)
        >>> result["providers"]
        ['aws']
        >>> result["confidence"]
        1.0
    """
    # Validate input
    if not isinstance(tfdata, dict):
        raise ValueError("tfdata must be a dictionary")

    if "all_resource" not in tfdata:
        raise ValueError("tfdata missing required key 'all_resource'")

    all_resources = tfdata.get("all_resource", [])

    if not all_resources:
        logger.warning("No resources found in tfdata, defaulting to AWS")
        return {
            "providers": ["aws"],
            "primary_provider": "aws",
            "resource_counts": {"aws": 0},
            "detection_method": "default",
            "confidence": 0.3
        }

    # Count resources per provider
    resource_counts: Dict[str, int] = {}

    for resource_name in all_resources:
        provider = get_provider_for_resource(resource_name)
        resource_counts[provider] = resource_counts.get(provider, 0) + 1

    # Extract known providers (exclude 'unknown')
    known_providers = [
        provider for provider in resource_counts.keys()
        if provider in SUPPORTED_PROVIDERS
    ]

    if not known_providers:
        logger.error(f"No supported providers detected in {len(all_resources)} resources")
        raise ProviderDetectionError(
            f"Could not detect any supported cloud providers in Terraform project. "
            f"Found {len(all_resources)} resources but none matched known provider prefixes."
        )

    # Determine primary provider (most resources)
    primary_provider = max(
        known_providers,
        key=lambda p: resource_counts.get(p, 0)
    )

    # Calculate confidence score
    confidence = _calculate_confidence(resource_counts, len(all_resources))

    # Filter resource counts to only include known providers
    filtered_counts = {
        provider: count
        for provider, count in resource_counts.items()
        if provider in SUPPORTED_PROVIDERS
    }

    result = {
        "providers": sorted(known_providers),  # Alphabetical order for consistency
        "primary_provider": primary_provider,
        "resource_counts": filtered_counts,
        "detection_method": "resource_prefix",
        "confidence": confidence
    }

    logger.info(
        f"Detected {len(known_providers)} provider(s): {', '.join(known_providers)} "
        f"(primary: {primary_provider}, confidence: {confidence:.2f})"
    )

    return result


def _calculate_confidence(resource_counts: Dict[str, int], total_resources: int) -> float:
    """
    Calculate confidence score for provider detection.

    Args:
        resource_counts: Count of resources per provider (including 'unknown')
        total_resources: Total number of resources

    Returns:
        Confidence score between 0.0 and 1.0

    Confidence Scoring:
        - 1.0: All resources have unambiguous prefixes (no unknowns)
        - 0.8-0.9: Mostly clear with some unknowns (>80% known)
        - 0.5-0.7: Mixed signals (50-80% known)
        - <0.5: Low confidence, many unknowns
    """
    if total_resources == 0:
        return 0.3  # Default low confidence

    unknown_count = resource_counts.get('unknown', 0)
    known_count = total_resources - unknown_count
    known_ratio = known_count / total_resources

    if known_ratio >= 1.0:
        return 1.0
    elif known_ratio >= 0.9:
        return 0.95
    elif known_ratio >= 0.8:
        return 0.85
    elif known_ratio >= 0.7:
        return 0.75
    elif known_ratio >= 0.5:
        return 0.65
    else:
        return 0.4


def filter_resources_by_provider(
    tfdata: Dict[str, Any],
    provider: str
) -> ResourcesByProvider:
    """
    Extract subset of resources belonging to specific provider.

    Args:
        tfdata: Full Terraform data dictionary containing:
            - all_resource (List[str]): All resource names
            - graphdict (Dict): Resource relationship graph
            - meta_data (Dict): Resource metadata
        provider: Provider to filter ('aws' | 'azure' | 'gcp')

    Returns:
        ResourcesByProvider dictionary containing:
            - provider (str): Provider name
            - resources (List[str]): Resource keys for this provider
            - graphdict (Dict[str, List[str]]): Filtered relationship graph
            - metadata (Dict[str, Dict]): Filtered metadata

    Raises:
        ValueError: If provider not in SUPPORTED_PROVIDERS

    Examples:
        >>> tfdata = {
        ...     "all_resource": ["aws_instance.web", "azurerm_vm.app"],
        ...     "graphdict": {"aws_instance.web": [], "azurerm_vm.app": []},
        ...     "meta_data": {"aws_instance.web": {}, "azurerm_vm.app": {}}
        ... }
        >>> aws_resources = filter_resources_by_provider(tfdata, "aws")
        >>> len(aws_resources["resources"])
        1
    """
    # Validate provider
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' not supported. "
            f"Must be one of: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    all_resources = tfdata.get("all_resource", [])
    graphdict = tfdata.get("graphdict", {})
    meta_data = tfdata.get("meta_data", {})

    # Filter resources for this provider
    filtered_resources = [
        resource_name for resource_name in all_resources
        if get_provider_for_resource(resource_name) == provider
    ]

    # Build filtered graphdict (only include edges between filtered resources)
    filtered_graphdict = {}
    for resource_name in filtered_resources:
        if resource_name in graphdict:
            # Only include dependencies that are also in filtered resources
            dependencies = [
                dep for dep in graphdict[resource_name]
                if dep in filtered_resources
            ]
            filtered_graphdict[resource_name] = dependencies
        else:
            filtered_graphdict[resource_name] = []

    # Build filtered metadata
    filtered_metadata = {
        resource_name: meta_data.get(resource_name, {})
        for resource_name in filtered_resources
    }

    result = {
        "provider": provider,
        "resources": filtered_resources,
        "graphdict": filtered_graphdict,
        "metadata": filtered_metadata
    }

    logger.info(
        f"Filtered {len(filtered_resources)} resources for provider '{provider}'"
    )

    return result


def validate_provider_detection(
    result: ProviderDetectionResult,
    tfdata: Dict[str, Any]
) -> bool:
    """
    Validate provider detection result against actual resources.

    Args:
        result: Detection result to validate
        tfdata: Original Terraform data

    Returns:
        True if validation passes, False otherwise

    Validation Checks:
        1. All providers in result are valid
        2. primary_provider is in providers list
        3. Sum of resource_counts matches total resources
        4. Confidence is between 0.0 and 1.0
        5. At least one provider detected

    Examples:
        >>> result = {
        ...     "providers": ["aws"],
        ...     "primary_provider": "aws",
        ...     "resource_counts": {"aws": 2},
        ...     "detection_method": "resource_prefix",
        ...     "confidence": 1.0
        ... }
        >>> tfdata = {"all_resource": ["aws_instance.web", "aws_s3_bucket.data"]}
        >>> validate_provider_detection(result, tfdata)
        True
    """
    try:
        # Check 1: All providers are valid
        providers = result.get("providers", [])
        for provider in providers:
            if provider not in SUPPORTED_PROVIDERS:
                logger.warning(
                    f"Validation failed: Invalid provider '{provider}' in result"
                )
                return False

        # Check 2: At least one provider detected
        if not providers:
            logger.warning("Validation failed: No providers detected")
            return False

        # Check 3: primary_provider is in providers list
        primary_provider = result.get("primary_provider")
        if primary_provider not in providers:
            logger.warning(
                f"Validation failed: Primary provider '{primary_provider}' "
                f"not in providers list {providers}"
            )
            return False

        # Check 4: Confidence is valid range
        confidence = result.get("confidence", 0.0)
        if not (0.0 <= confidence <= 1.0):
            logger.warning(
                f"Validation failed: Confidence {confidence} not in range [0.0, 1.0]"
            )
            return False

        # Check 5: Resource counts sum matches total (allowing for unknown resources)
        resource_counts = result.get("resource_counts", {})
        total_detected = sum(resource_counts.values())
        total_actual = len(tfdata.get("all_resource", []))

        # Count unknown resources separately
        unknown_count = 0
        for resource_name in tfdata.get("all_resource", []):
            if get_provider_for_resource(resource_name) == 'unknown':
                unknown_count += 1

        expected_detected = total_actual - unknown_count

        if total_detected != expected_detected:
            logger.warning(
                f"Validation failed: Resource count mismatch. "
                f"Detected {total_detected}, expected {expected_detected} "
                f"(total: {total_actual}, unknown: {unknown_count})"
            )
            return False

        logger.info("Provider detection validation passed")
        return True

    except Exception as e:
        logger.error(f"Validation failed with exception: {e}")
        return False


# Utility functions for integration

def get_primary_provider_or_default(tfdata: Dict[str, Any]) -> str:
    """
    Get primary provider from tfdata or return default (AWS).

    Useful for backward compatibility with existing code that doesn't
    use provider detection.

    Args:
        tfdata: Terraform data (may or may not have provider_detection)

    Returns:
        Primary provider name ('aws' | 'azure' | 'gcp')
    """
    if "provider_detection" in tfdata:
        return tfdata["provider_detection"]["primary_provider"]

    # Try to detect on-the-fly
    try:
        result = detect_providers(tfdata)
        return result["primary_provider"]
    except (ValueError, ProviderDetectionError):
        logger.warning("Could not detect provider, defaulting to AWS")
        return "aws"


def has_multiple_providers(tfdata: Dict[str, Any]) -> bool:
    """
    Check if Terraform project uses multiple cloud providers.

    Args:
        tfdata: Terraform data dictionary

    Returns:
        True if multiple providers detected, False otherwise
    """
    if "provider_detection" in tfdata:
        providers = tfdata["provider_detection"]["providers"]
        return len(providers) > 1

    # Try to detect on-the-fly
    try:
        result = detect_providers(tfdata)
        return len(result["providers"]) > 1
    except (ValueError, ProviderDetectionError):
        return False
