"""
Helper functions to transform graphdict for improved diagram layout.
Add these functions to your terravision.py or a helper module.
"""

def _reverse_route_table_associations(tfdata: dict) -> dict:
    """
    Reverse the relationship between route tables and their associations.
    Route table associations should point back to their route tables.
    """
    graphdict = tfdata["graphdict"]
    
    # Find all route table associations
    for resource in list(graphdict.keys()):
        if "aws_route_table_association" in resource:
            # Find parent route tables
            for parent, connections in graphdict.items():
                if resource in connections and "aws_route_table" in parent:
                    # Reverse: association now points to route table
                    if resource not in graphdict:
                        graphdict[resource] = []
                    if parent not in graphdict[resource]:
                        graphdict[resource].append(parent)
                    # Remove association from route table's connections
                    graphdict[parent].remove(resource)
    
    return tfdata


def _reverse_subnet_associations(tfdata: dict) -> dict:
    """
    Make subnets point to their route table associations instead of vice versa.
    """
    graphdict = tfdata["graphdict"]
    
    # Find all subnets
    for subnet in list(graphdict.keys()):
        if "aws_subnet" in subnet:
            # Find route table associations that should connect to this subnet
            for resource, connections in list(graphdict.items()):
                if "aws_route_table_association" in resource:
                    # Check if this association is for this subnet (matching suffix)
                    if "~" in subnet and "~" in resource:
                        subnet_suffix = subnet.split("~")[1]
                        assoc_suffix = resource.split("~")[1]
                        if subnet_suffix == assoc_suffix:
                            # Determine if private or public based on names
                            if ("private" in subnet and "private" in resource) or \
                               ("public" in subnet and "public" in resource):
                                if resource not in graphdict[subnet]:
                                    graphdict[subnet].append(resource)
    
    return tfdata
