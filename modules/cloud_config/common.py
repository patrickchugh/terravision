"""
Common types and interfaces for cloud provider configurations.

This module defines the contract that all provider configuration modules
must follow to ensure consistent behavior across AWS, Azure, GCP, and other providers.
"""

from typing import Any, Dict, List, TypedDict


class ConsolidatedNodeConfig(TypedDict, total=False):
    """
    Configuration for a consolidated node type.

    Attributes:
        resource_name: The canonical resource name for the consolidated node
        import_location: Python module path to the resource class
        vpc: Whether the resource belongs inside a VPC/network boundary
        edge_service: Whether the resource is an edge/boundary service
    """

    resource_name: str
    import_location: str
    vpc: bool
    edge_service: bool


# Type aliases for clarity
ConsolidatedNodes = List[Dict[str, ConsolidatedNodeConfig]]
GroupNodes = List[str]
EdgeNodes = List[str]
OuterNodes = List[str]
DrawOrder = List[List[str]]
AutoAnnotations = List[Dict[str, Dict[str, Any]]]
NodeVariants = Dict[str, Dict[str, str]]
ReverseArrowList = List[str]
ForcedDest = List[str]
ForcedOrigin = List[str]
ImpliedConnections = Dict[str, str]
SpecialResources = Dict[str, str]
SharedServices = List[str]
AlwaysDrawLine = List[str]
NeverDrawLine = List[str]
DisconnectList = List[str]
AcronymsList = List[str]
NameReplacements = Dict[str, str]
