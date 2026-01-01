"""Azure resource handler configurations.

Defines transformation pipelines for Azure resources.
Patterns support wildcards via substring matching.
"""

RESOURCE_HANDLER_CONFIGS = {
    # Association resource removal (Pure Config) - Decision 4
    # Removes linking resources like NSG associations, NIC associations
    "association": {
        "description": "Remove Azure association resources from diagram (Pure Config)",
        "transformations": [
            {
                "operation": "delete_nodes",
                "params": {
                    "resource_pattern": "association",
                    "remove_from_parents": True,
                },
            }
        ],
    },
}

COMPLEX_HANDLERS = {
    # Azure complex handlers that need custom functions
}
