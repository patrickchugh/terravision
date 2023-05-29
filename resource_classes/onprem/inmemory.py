from . import _OnPrem


class _Inmemory(_OnPrem):
    _type = "inmemory"
    _icon_dir = "resource_images/onprem/inmemory"


class Aerospike(_Inmemory):
    _icon = "aerospike.png"


class Hazelcast(_Inmemory):
    _icon = "hazelcast.png"


class Memcached(_Inmemory):
    _icon = "memcached.png"


class Redis(_Inmemory):
    _icon = "redis.png"


# Aliases
