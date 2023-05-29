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
aws_qldb_ledger = QuantumLedgerDatabaseQldb
