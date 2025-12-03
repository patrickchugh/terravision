"""
Provider runtime and abstraction layer for multi-cloud support.

This module provides the ProviderContext system that decouples cloud-specific
logic from core graph building and rendering. It enables dynamic provider
detection, configuration loading, and handler dispatch.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import importlib


@dataclass
class ProviderDescriptor:
    """
    Descriptor defining a Terraform provider integration.

    Args:
        id: Provider identifier (e.g., "aws", "azurerm", "google")
        resource_prefixes: Terraform resource type prefixes for this provider
        cloud_config_module: Python module path for provider config
        handler_module: Python module path for resource handlers
    """

    id: str
    resource_prefixes: Tuple[str, ...]
    cloud_config_module: str
    handler_module: str


class ProviderContext:
    """
    Runtime context for managing multiple Terraform providers.

    Responsibilities:
    - Provider detection from resource names
    - Dynamic loading of provider-specific configurations
    - Handler dispatch for special resource processing
    - Abstraction of provider-specific logic
    """

    def __init__(self, descriptors: Optional[Dict[str, ProviderDescriptor]] = None):
        """
        Initialize ProviderContext with provider descriptors.

        Args:
            descriptors: Dictionary of provider_id -> ProviderDescriptor.
                        If None, loads default AWS/Azure/GCP providers.
        """
        if descriptors is None:
            descriptors = self._get_default_descriptors()

        self.descriptors = descriptors
        self.configs: Dict[str, Any] = {}  # provider_id -> loaded config module
        self.handlers: Dict[str, Any] = {}  # provider_id -> handler module
        self._prefix_map: Dict[str, str] = {}  # cache: prefix -> provider_id

        # Build prefix lookup map
        for provider_id, descriptor in self.descriptors.items():
            for prefix in descriptor.resource_prefixes:
                self._prefix_map[prefix] = provider_id

    @staticmethod
    def _get_default_descriptors() -> Dict[str, ProviderDescriptor]:
        """Returns default provider descriptors for AWS, Azure, and GCP."""
        return {
            "aws": ProviderDescriptor(
                id="aws",
                resource_prefixes=("aws_",),
                cloud_config_module="modules.cloud_config.aws",
                handler_module="resource_handlers.aws",
            ),
            "azurerm": ProviderDescriptor(
                id="azurerm",
                resource_prefixes=("azurerm_", "azuread_"),
                cloud_config_module="modules.cloud_config.azure",
                handler_module="resource_handlers.azure",
            ),
            "google": ProviderDescriptor(
                id="google",
                resource_prefixes=("google_",),
                cloud_config_module="modules.cloud_config.gcp",
                handler_module="resource_handlers.gcp",
            ),
        }

    def detect_provider_for_node(self, node: str) -> Optional[str]:
        """
        Detect provider from node name.

        Args:
            node: Terraform resource node name (e.g., "aws_instance.web",
                  "module.vpc.aws_subnet.private")

        Returns:
            Provider ID if detected, None otherwise
        """
        # Extract resource type from node name
        # Format: "resource_type.name" or "module.path.resource_type.name"
        parts = node.split(".")

        # Look for provider prefix in parts (handle module nesting)
        for part in parts:
            # Check if this part starts with a known provider prefix
            for prefix, provider_id in self._prefix_map.items():
                if part.startswith(prefix):
                    return provider_id

        return None

    def detect_providers_from_tfdata(self, tfdata: Dict[str, Any]) -> Set[str]:
        """
        Detect all providers used in tfdata.

        Args:
            tfdata: TerraVision data structure containing graphdict and metadata

        Returns:
            Set of provider IDs found in the project
        """
        providers: Set[str] = set()

        # Check all nodes in graphdict
        if "graphdict" in tfdata:
            for node in tfdata["graphdict"].keys():
                provider = self.detect_provider_for_node(node)
                if provider:
                    providers.add(provider)

        # Check node_list if available
        if "node_list" in tfdata:
            for node in tfdata["node_list"]:
                provider = self.detect_provider_for_node(node)
                if provider:
                    providers.add(provider)

        return providers

    def get_config(self, provider_id: str) -> Any:
        """
        Load and return provider-specific configuration module.

        Args:
            provider_id: Provider identifier (e.g., "aws", "azurerm")

        Returns:
            Configuration module with constants like CONSOLIDATED_NODES,
            GROUP_NODES, AUTO_ANNOTATIONS, etc.

        Raises:
            KeyError: If provider_id is not registered
            ImportError: If config module cannot be loaded
        """
        if provider_id not in self.descriptors:
            raise KeyError(f"Unknown provider: {provider_id}")

        if provider_id not in self.configs:
            descriptor = self.descriptors[provider_id]
            self.configs[provider_id] = importlib.import_module(
                descriptor.cloud_config_module
            )

        return self.configs[provider_id]

    def get_handler(self, provider_id: str) -> Any:
        """
        Load and return provider-specific handler module.

        Args:
            provider_id: Provider identifier (e.g., "aws", "azurerm")

        Returns:
            Handler module with functions for special resource processing

        Raises:
            KeyError: If provider_id is not registered
            ImportError: If handler module cannot be loaded
        """
        if provider_id not in self.descriptors:
            raise KeyError(f"Unknown provider: {provider_id}")

        if provider_id not in self.handlers:
            descriptor = self.descriptors[provider_id]
            self.handlers[provider_id] = importlib.import_module(
                descriptor.handler_module
            )

        return self.handlers[provider_id]

    def consolidate(self, provider_id: str, resource_type: str) -> Optional[str]:
        """
        Check if resource type should be consolidated and return target type.

        Args:
            provider_id: Provider identifier
            resource_type: Terraform resource type prefix (e.g., "aws_lb")

        Returns:
            Consolidated node type if applicable, None otherwise
        """
        try:
            config = self.get_config(provider_id)
            consolidated = getattr(config, "CONSOLIDATED_NODES", {})
            return consolidated.get(resource_type)
        except (KeyError, ImportError):
            return None

    def map_variant(
        self, provider_id: str, resource_type: str, metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determine node variant based on provider rules and metadata.

        Args:
            provider_id: Provider identifier
            resource_type: Terraform resource type prefix
            metadata: Node metadata dictionary

        Returns:
            Variant resource type if applicable, None otherwise
        """
        try:
            config = self.get_config(provider_id)
            node_variants = getattr(config, "NODE_VARIANTS", {})

            if resource_type not in node_variants:
                return None

            variant_rules = node_variants[resource_type]

            # Check metadata for variant keywords
            metadata_str = str(metadata).lower()
            for keyword, variant_type in variant_rules.items():
                if keyword.lower() in metadata_str:
                    return variant_type

            return None
        except (KeyError, ImportError):
            return None

    def implied_connections(self, provider_id: str, param: str) -> List[str]:
        """
        Get implied connection targets for a parameter.

        Args:
            provider_id: Provider identifier
            param: Parameter name or keyword

        Returns:
            List of resource type prefixes that should be connected
        """
        try:
            config = self.get_config(provider_id)
            implied = getattr(config, "IMPLIED_CONNECTIONS", {})
            return implied.get(param, [])
        except (KeyError, ImportError):
            return []

    def get_special_resources(self, provider_id: str) -> Dict[str, str]:
        """
        Get special resource mapping for provider.

        Args:
            provider_id: Provider identifier

        Returns:
            Dictionary mapping resource_prefix -> handler_function_name
        """
        try:
            config = self.get_config(provider_id)
            return getattr(config, "SPECIAL_RESOURCES", {})
        except (KeyError, ImportError):
            return {}

    def is_group_node(self, provider_id: str, resource_type: str) -> bool:
        """Check if resource type is a group/container node."""
        try:
            config = self.get_config(provider_id)
            group_nodes = getattr(config, "GROUP_NODES", [])
            return resource_type in group_nodes
        except (KeyError, ImportError):
            return False

    def is_edge_node(self, provider_id: str, resource_type: str) -> bool:
        """Check if resource type is an edge/boundary node."""
        try:
            config = self.get_config(provider_id)
            edge_nodes = getattr(config, "EDGE_NODES", [])
            return resource_type in edge_nodes
        except (KeyError, ImportError):
            return False


def create_default_provider_context() -> ProviderContext:
    """
    Create a ProviderContext with default AWS/Azure/GCP providers.

    Returns:
        Initialized ProviderContext
    """
    return ProviderContext()


class ProviderRegistry:
    """
    Global registry for provider descriptors and runtime contexts.

    Singleton pattern (class-level state). Not thread-safe.
    """

    _descriptors: Dict[str, ProviderDescriptor] = {}  # name -> descriptor
    _contexts: Dict[str, ProviderContext] = {}  # name -> context instance
    _default_provider: Optional[str] = None  # default provider ID

    @classmethod
    def register(cls, descriptor: ProviderDescriptor, default: bool = False) -> None:
        """
        Register a provider descriptor.

        Called during module initialization to populate built-in providers.
        Can be called by plugins to register custom providers.

        Args:
            descriptor: Provider metadata
            default: Whether this is the default provider (e.g., AWS)

        Raises:
            ValueError: If provider name already registered
        """
        if descriptor.id in cls._descriptors:
            raise ValueError(f"Provider '{descriptor.id}' already registered")

        cls._descriptors[descriptor.id] = descriptor

        if default:
            cls._default_provider = descriptor.id

    @classmethod
    def get_descriptor(cls, name: str) -> Optional[ProviderDescriptor]:
        """
        Get provider descriptor by name.

        Args:
            name: Provider name (e.g., 'aws', 'azure', 'google')

        Returns:
            ProviderDescriptor or None if not found
        """
        return cls._descriptors.get(name.lower())

    @classmethod
    def get_context(cls, name: Optional[str] = None) -> ProviderContext:
        """
        Get or create provider context.

        Caches context instances (singleton per provider).
        Falls back to default provider if name not provided.

        Args:
            name: Provider name (optional, defaults to default provider)

        Returns:
            ProviderContext instance
        """
        if name is None:
            name = cls._default_provider or "aws"

        name = name.lower()

        if name not in cls._contexts:
            descriptor = cls.get_descriptor(name)
            if descriptor is None:
                # Fallback to default provider
                if cls._default_provider:
                    descriptor = cls.get_descriptor(cls._default_provider)
                if descriptor is None:
                    raise KeyError(f"Unknown provider: {name}")

            # Create context with single descriptor
            cls._contexts[name] = ProviderContext({descriptor.id: descriptor})

        return cls._contexts[name]

    @classmethod
    def list_providers(cls) -> Set[str]:
        """List all registered provider names"""
        return set(cls._descriptors.keys())

    @classmethod
    def detect_providers(cls, tfdata: Dict[str, Any]) -> Set[str]:
        """
        Detect providers from Terraform plan data.

        Implementation: Hybrid approach from research.md Section 1.

        Args:
            tfdata: Parsed Terraform plan JSON

        Returns:
            Set of detected provider names (defaults to {default_provider} if none found)
        """
        providers = set()

        # Primary: Extract from Terraform plan metadata
        all_resources = tfdata.get("all_resource", {})
        if isinstance(all_resources, dict):
            for resource in all_resources.values():
                if isinstance(resource, dict) and "provider_name" in resource:
                    # Parse "registry.terraform.io/hashicorp/aws" -> "aws"
                    provider_fqdn = resource["provider_name"]
                    provider_short = provider_fqdn.split("/")[-1]

                    # Match against registered providers
                    if cls.get_descriptor(provider_short):
                        providers.add(provider_short)

        # Fallback: Prefix matching
        if not providers:
            for resource_type in all_resources.keys():
                for name, descriptor in cls._descriptors.items():
                    for prefix in descriptor.resource_prefixes:
                        if resource_type.startswith(prefix):
                            providers.add(descriptor.id)
                            break

        # Default: Return default provider if no detection succeeds
        if not providers and cls._default_provider:
            return {cls._default_provider}

        return providers if providers else set()

    @classmethod
    def reset(cls) -> None:
        """Reset registry state (useful for testing)"""
        cls._descriptors.clear()
        cls._contexts.clear()
        cls._default_provider = None
