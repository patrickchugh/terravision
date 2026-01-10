"""
GCP Web3 category - Blockchain Node Engine.

Icon Resolution:
- All web3 resources use category icon (2-color): resource_images/gcp/category/web3.png
"""

from . import _GCP


class _Web3(_GCP):
    _type = "web3"
    _icon_dir = "resource_images/gcp/category"
    _icon = "web3.png"


class BlockchainNodeEngine(_Web3):
    """Blockchain Node Engine for node hosting."""

    pass


class Ethereum(_Web3):
    """Ethereum node hosting."""

    pass


class Solana(_Web3):
    """Solana node hosting."""

    pass


class Polygon(_Web3):
    """Polygon node hosting."""

    pass


# Aliases
BNE = BlockchainNodeEngine
Blockchain = BlockchainNodeEngine

# Terraform resource aliases
google_blockchain_node_engine_blockchain_nodes = BlockchainNodeEngine
