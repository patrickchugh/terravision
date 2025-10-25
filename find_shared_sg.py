def find_shared_security_groups(graphdict):
    """Find all keys where the same security group appears in multiple connection lists"""
    sg_to_keys = {}
    
    # Build mapping of security groups to keys that reference them
    for key, connections in graphdict.items():
        for connection in connections:
            if 'aws_security_group' in connection:
                if connection not in sg_to_keys:
                    sg_to_keys[connection] = []
                sg_to_keys[connection].append(key)
    
    # Return keys where security groups are shared (appear in multiple lists)
    return [key for sg, keys in sg_to_keys.items() if len(keys) > 1 for key in keys]