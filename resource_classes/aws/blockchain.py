from . import _AWS


class _Blockchain(_AWS):
    _type = "blockchain"
    _icon_dir = "resource_images/aws/blockchain"


class ManagedBlockchain(_Blockchain):
    _icon = "managed-blockchain.png"


class QuantumLedgerDatabaseQldb(_Blockchain):
    _icon = "quantum-ledger-database-qldb.png"


# Aliases

QLDB = QuantumLedgerDatabaseQldb

# Terraform aliases
aws_managed_blockchain_network = ManagedBlockchain
aws_managed_blockchain_node = ManagedBlockchain
aws_qldb_ledger = QuantumLedgerDatabaseQldb
