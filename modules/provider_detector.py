"""
Provider Detection Module for TerraVision Multi-Cloud Support

This module provides functionality to detect cloud providers (AWS, Azure, GCP) from
Terraform project data by analyzing resource name prefixes and provider blocks.

"""

from typing import Dict, List, Any, Tuple
import logging

# Configure logging
logger = logging.getLogger(__name__)


# Constants
PROVIDER_PREFIXES = {
    "aws_": "aws",
    "azurerm_": "azure",
    "azuread_": "azure",  # Azure Active Directory
    "azurestack_": "azure",
    "azapi_": "azure",  # Azure API provider
    "google_": "gcp",
}

SUPPORTED_PROVIDERS = ["aws", "azure", "gcp"]


# Error Classes
class ProviderDetectionError(Exception):
    """Raised when no cloud providers can be detected in Terraform project."""

    pass


def _extract_resource_names(all_resources: Any) -> List[str]:
    """
    Extract flat list of resource names from all_resource structure.

    The all_resource structure is a dict with file paths as keys and lists of
    resource dicts as values: {"file.tf": [{"aws_instance": {...}}, ...]}

    Args:
        all_resources: The all_resource structure (dict or list for backward compatibility)

    Returns:
        Flat list of resource names (e.g., ["aws_instance.web", "azurerm_vm.app"])
    """
    resource_names = []
    if isinstance(all_resources, dict):
        for _file_path, resource_list in all_resources.items():
            if isinstance(resource_list, list):
                for resource_item in resource_list:
                    if isinstance(resource_item, dict):
                        # Resource item is a dict like {"aws_instance": {...}}
                        resource_names.extend(resource_item.keys())
                    elif isinstance(resource_item, str):
                        # Sometimes might be a simple string
                        resource_names.append(resource_item)
    elif isinstance(all_resources, list):
        # Backward compatibility: handle flat list format
        resource_names = all_resources
    return resource_names


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

    return "unknown"


def detect_providers(tfdata: Dict[str, Any]) -> Dict[str, Any]:
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
        Dict[str, Any] dictionary containing:
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

    all_resources = tfdata.get("all_resource", {})
    resource_names = _extract_resource_names(all_resources)

    if not resource_names:
        logger.error("No resources found in tfdata - cannot detect provider")
        raise ProviderDetectionError(
            "No resources found in Terraform project. Cannot detect cloud provider without resources."
        )

    # Count resources per provider
    resource_counts: Dict[str, int] = {}

    for resource_name in resource_names:
        provider = get_provider_for_resource(resource_name)
        resource_counts[provider] = resource_counts.get(provider, 0) + 1

    # Extract known providers (exclude 'unknown')
    known_providers = [
        provider
        for provider in resource_counts.keys()
        if provider in SUPPORTED_PROVIDERS
    ]

    if not known_providers:
        logger.error(
            f"No supported providers detected in {len(all_resources)} resources"
        )
        raise ProviderDetectionError(
            f"Could not detect any supported cloud providers in Terraform project. "
            f"Found {len(all_resources)} resources but none matched known provider prefixes."
        )

    # Determine primary provider (most resources)
    primary_provider = max(known_providers, key=lambda p: resource_counts.get(p, 0))

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
        "confidence": confidence,
    }

    logger.info(
        f"Detected {len(known_providers)} provider(s): {', '.join(known_providers)} "
        f"(primary: {primary_provider}, confidence: {confidence:.2f})"
    )

    return result


def _calculate_confidence(
    resource_counts: Dict[str, int], total_resources: int
) -> float:
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

    unknown_count = resource_counts.get("unknown", 0)
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


def validate_provider_detection(result: Dict[str, Any], tfdata: Dict[str, Any]) -> bool:
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

        # Extract flat list of resource names
        all_resources = tfdata.get("all_resource", {})
        resource_names = _extract_resource_names(all_resources)
        total_actual = len(resource_names)

        # Count unknown resources separately
        unknown_count = 0
        for resource_name in resource_names:
            if get_provider_for_resource(resource_name) == "unknown":
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
    Get primary provider from tfdata or raise error if not detectable.

    Args:
        tfdata: Terraform data (may or may not have provider_detection)

    Returns:
        Primary provider name ('aws' | 'azure' | 'gcp')

    Raises:
        ProviderDetectionError: If provider cannot be detected

    Note:
        This function NO LONGER defaults to AWS. If provider detection hasn't
        run or fails, it will raise an error. This prevents incorrect assumptions.
    """
    if "provider_detection" in tfdata:
        return tfdata["provider_detection"]["primary_provider"]

    # Try to detect on-the-fly
    try:
        result = detect_providers(tfdata)
        return result["primary_provider"]
    except (ValueError, ProviderDetectionError):
        # For simple JSON sources (graphdict only), infer from resource names
        if "graphdict" in tfdata and not "all_resource" in tfdata:
            resource_names = list(tfdata["graphdict"].keys())
            provider_counts = {}
            for resource_name in resource_names:
                provider = get_provider_for_resource(resource_name)
                if provider in SUPPORTED_PROVIDERS:
                    provider_counts[provider] = provider_counts.get(provider, 0) + 1

            if provider_counts:
                return max(provider_counts, key=provider_counts.get)

        logger.error(
            "Could not detect provider - provider detection must run before calling this function"
        )
        raise ProviderDetectionError(
            "Provider detection has not been run or failed. "
            "Ensure detect_providers(tfdata) is called before using provider-specific functionality."
        )
