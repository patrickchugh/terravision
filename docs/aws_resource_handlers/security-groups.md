# Security Groups

## Table of Contents

1. [Security Group Transformation](#security-group-transformation)
2. [Security Group Processing Steps](#security-group-processing-steps)
   - [Step 1: Resolve Indirect Associations](#step-1-resolve-indirect-associations)
   - [Step 2: Reverse Security Group Relationships](#step-2-reverse-security-group-relationships)
   - [Step 3: Move Security Groups to Subnet Level](#step-3-move-security-groups-to-subnet-level)
   - [Step 4: Remove Security Groups from VPC Level](#step-4-remove-security-groups-from-vpc-level)
   - [Step 5: Clean Up Orphan Security Groups](#step-5-clean-up-orphan-security-groups)
3. [Security Group Matching by Suffix](#security-group-matching-by-suffix)

---

## Security Group Transformation

**Philosophy**: In AWS, security groups protect resources. The diagram should reflect this by making security groups **containers** that wrap the resources they protect.

**Core Transformation**:
```
Before (Terraform's view):
EC2 Instance → Security Group

After (Architecture view):
Security Group → EC2 Instance
```

This reversal makes security groups appear as protective boundaries around resources.

---

## Security Group Processing Steps

### Step 1: Resolve Indirect Associations

**What Happens**: Security group rules are intermediate resources that shouldn't appear in diagrams.

**Transformation**:
```
Before:
Security Group → Security Group Rule → Resource

After:
Security Group → Resource
```

**Connections**:
- **Removed**: Security group rule nodes
- **Added**: Direct connection from security group to the actual resource

### Implementation

```
FUNCTION resolve_security_group_rules(tfdata):

    // Step 1: Find all security group rules
    sg_rules = FIND_RESOURCES_CONTAINING(graphdict, "aws_security_group_rule")

    // Step 2: For each rule, create direct connections
    FOR EACH rule IN sg_rules:
        // Find the security group this rule belongs to
        rule_parents = GET_PARENTS(graphdict, rule)

        FOR EACH parent IN rule_parents:
            IF parent starts with "aws_security_group"
               AND parent does NOT contain "_rule":

                // Get resources referenced by this rule
                rule_connections = graphdict[rule]

                FOR EACH resource IN rule_connections:
                    // Create direct SG → Resource connection
                    IF resource NOT IN graphdict[parent]:
                        ADD resource TO graphdict[parent]

        // Remove the rule node
        DELETE graphdict[rule]

        // Remove rule from all parent connections
        FOR EACH node IN graphdict:
            IF rule IN graphdict[node]:
                REMOVE rule FROM graphdict[node]

    RETURN tfdata
```

**Result**: Security group rules are bypassed, showing direct SG → Resource relationships.

---

### Step 2: Reverse Security Group Relationships

**What Happens**: For non-group resources, the connection direction is reversed so security groups become containers.

**For Numbered Resources** (resources with `count > 1`):
```
Resource~1 → Security Group

Becomes:
Security Group~1 → Resource~1
```
The security group gets the same numeric suffix as the resource.

**For Single Resources with Reused Security Groups**:
```
Resource1 → Security Group
Resource2 → Security Group

Becomes:
Security Group_Resource1 → Resource1
Security Group_Resource2 → Resource2
```
Unique security group instances are created per resource.

**For Empty Security Groups**:
```
Resource → Empty Security Group

Becomes:
Empty Security Group → Resource
```
The direction is simply reversed.

### Implementation

```
FUNCTION reverse_security_group_relationships(tfdata):

    // Step 1: Find all resources that connect to security groups
    all_sg_parents = GET_PARENTS(graphdict, "aws_security_group.*")
    bound_nodes = FILTER all_sg_parents
                  WHERE resource name does NOT start with "aws_security_group"

    bound_nodes = SORT(bound_nodes)  // For deterministic processing

    // Step 2: Process each resource that references a security group
    FOR EACH target IN bound_nodes:

        target_type = EXTRACT_TYPE(target)  // e.g., "aws_instance" from "aws_instance.web"

        // Only process non-group resources
        IF target_type NOT IN GROUP_NODES AND target_type != "aws_security_group_rule":

            // Create safe copy of connections (avoid mutation during iteration)
            connections = COPY(graphdict[target])

            FOR EACH sg_connection IN connections:

                // Check if this is a security group connection
                IF sg_connection starts with "aws_security_group."
                   AND sg_connection exists in graphdict
                   AND graphdict[sg_connection] is not empty:

                    // Prepare reversed relationship: SG → target
                    new_connections = [target]

                    // Handle numbered resources (e.g., instance~1, instance~2)
                    IF target contains "~":
                        // Extract suffix (e.g., "~1" from "aws_instance.web~1")
                        suffix = EXTRACT_SUFFIX(target)  // e.g., "1"

                        // Create numbered SG (e.g., "sg~1")
                        sg_with_suffix = sg_connection + "~" + suffix
                        CREATE graphdict[sg_with_suffix] = new_connections

                    // Handle reused security groups
                    ELSE:
                        IF graphdict[sg_connection] already has connections:
                            // Create unique SG instance to avoid conflicts
                            unique_name = sg_connection + "_" + EXTRACT_NAME(target)
                            CREATE graphdict[unique_name] = new_connections
                            COPY meta_data[sg_connection] TO meta_data[unique_name]
                        ELSE:
                            // SG is empty, just reverse the relationship
                            SET graphdict[sg_connection] = new_connections

                    // Remove original SG reference from target
                    REMOVE sg_connection FROM graphdict[target]

    RETURN tfdata
```

**Key Patterns**:
- **Safe Iteration**: Copy the list before modifying it during iteration
- **Suffix Matching**: Extract `~1`, `~2` from numbered resources
- **Unique Naming**: Create `sg_name_targetname` for reused security groups
- **Metadata Copying**: Deep copy metadata when creating new SG instances

**Operations**:
- `GET_PARENTS(graphdict, pattern)`: Find all resources pointing to resources matching pattern (supports wildcards like "aws_security_group.*")
- `EXTRACT_TYPE(resource)`: Get resource type (first part before dot)
- `EXTRACT_SUFFIX(resource)`: Get numeric suffix after `~`
- `EXTRACT_NAME(resource)`: Get resource name (last part after dot)

---

### Step 3: Move Security Groups to Subnet Level

**What Happens**: Security groups are moved from individual resources up to the subnet level.

**Hierarchy**:
```
Before:
Subnet → EC2 Instance → Security Group

After:
Subnet → Security Group → EC2 Instance
```

**Connections**:
- **Removed**: Security group from resource's connections
- **Removed**: Resource from subnet's connections
- **Added**: Security group to subnet
- **Added**: Resource to security group

This creates the visual effect of security groups as subnet-level security boundaries.

### Implementation

```
FUNCTION move_security_groups_to_subnet_level(tfdata):

    // Step 1: Find all subnets
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")

    FOR EACH subnet IN subnets:
        // Step 2: Find resources in this subnet
        resources = COPY(graphdict[subnet])

        FOR EACH resource IN resources:
            resource_type = EXTRACT_TYPE(resource)

            // Skip if resource is already a group or security-related
            IF resource_type IN GROUP_NODES
               OR resource_type == "aws_security_group":
                CONTINUE

            // Step 3: Find security groups protecting this resource
            resource_connections = graphdict[resource]

            FOR EACH connection IN resource_connections:
                IF connection starts with "aws_security_group":
                    // Move SG up to subnet level
                    IF connection NOT IN graphdict[subnet]:
                        ADD connection TO graphdict[subnet]

                    // Remove resource from subnet's direct children
                    REMOVE resource FROM graphdict[subnet]

                    // SG already points to resource from Step 2

    RETURN tfdata
```

**Result**: Security groups become intermediate layers between subnets and resources.

---

### Step 4: Remove Security Groups from VPC Level

**What Happens**: Security groups that appear at VPC level are removed (they belong in subnets).

**Connections**:
- **Removed**: Security group from VPC's child list

### Implementation

```
FUNCTION remove_security_groups_from_vpc_level(tfdata):

    // Step 1: Find all VPCs
    vpcs = FIND_RESOURCES_CONTAINING(graphdict, "aws_vpc.")

    FOR EACH vpc IN vpcs:
        // Step 2: Check VPC's children for security groups
        vpc_children = COPY(graphdict[vpc])

        FOR EACH child IN vpc_children:
            IF child starts with "aws_security_group":
                // Remove security group from VPC level
                REMOVE child FROM graphdict[vpc]

    RETURN tfdata
```

**Result**: Security groups only appear at subnet level or below, not at VPC level.

---

### Step 5: Clean Up Orphan Security Groups

**What Happens**: Security groups with no resources to protect and no parent are removed.

**Removal Criteria**:
- Security group has no connections (empty), OR
- Security group has no parent resources

### Implementation

```
FUNCTION cleanup_orphan_security_groups(tfdata):

    // Step 1: Find all security groups
    all_sgs = FIND_RESOURCES_CONTAINING(graphdict, "aws_security_group")

    FOR EACH sg IN all_sgs:
        is_orphan = false

        // Step 2: Check if SG has no connections
        IF graphdict[sg] is empty OR LENGTH(graphdict[sg]) == 0:
            is_orphan = true

        // Step 3: Check if SG has no parents
        IF NOT is_orphan:
            parents = GET_PARENTS(graphdict, sg)
            IF parents is empty OR LENGTH(parents) == 0:
                is_orphan = true

        // Step 4: Remove orphan security groups
        IF is_orphan:
            DELETE graphdict[sg]
            DELETE meta_data[sg]

            // Remove from all other nodes' connections
            FOR EACH node IN graphdict:
                IF sg IN graphdict[node]:
                    REMOVE sg FROM graphdict[node]

    RETURN tfdata
```

**Result**: Only active security groups protecting resources remain in the diagram.

---

## Security Group Matching by Suffix

**What Happens**: Security groups are matched to subnets by numeric suffix.

**Transformation**:
```
Subnet~1 should only show Security Group~1
Subnet~2 should only show Security Group~2
```

**Process**:
1. Group subnets by base name
2. Collect all security groups used by that subnet group
3. For each numbered subnet, add all security groups with matching suffix

**Example**:
```
Subnets:
- private_subnet~1
- private_subnet~2

Security Groups:
- web_sg~1
- web_sg~2
- db_sg~1
- db_sg~2

Result:
private_subnet~1 → web_sg~1, db_sg~1
private_subnet~2 → web_sg~2, db_sg~2
```

### Implementation

```
FUNCTION match_security_groups_by_suffix(tfdata):

    // Step 1: Find all numbered subnets
    all_subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")
    numbered_subnets = FILTER all_subnets WHERE subnet contains "~"

    // Step 2: Group subnets by base name
    subnet_groups = EMPTY MAP

    FOR EACH subnet IN numbered_subnets:
        base_name = REMOVE_SUFFIX(subnet)  // Remove ~1, ~2, etc.

        IF base_name NOT IN subnet_groups:
            subnet_groups[base_name] = EMPTY LIST

        ADD subnet TO subnet_groups[base_name]

    // Step 3: For each subnet group, match SGs by suffix
    FOR EACH base_name IN subnet_groups:
        // Collect all SGs used by this subnet group
        all_sgs_in_group = EMPTY SET

        FOR EACH subnet IN subnet_groups[base_name]:
            FOR EACH child IN graphdict[subnet]:
                IF child starts with "aws_security_group":
                    ADD child TO all_sgs_in_group

        // Step 4: For each numbered subnet, keep only matching SGs
        FOR EACH subnet IN subnet_groups[base_name]:
            subnet_suffix = EXTRACT_SUFFIX(subnet)  // e.g., "1" from "subnet~1"

            // Filter SGs to only those with matching suffix
            matched_sgs = EMPTY LIST

            FOR EACH sg IN all_sgs_in_group:
                IF sg contains "~":
                    sg_suffix = EXTRACT_SUFFIX(sg)
                    IF sg_suffix == subnet_suffix:
                        ADD sg TO matched_sgs
                ELSE:
                    // Unnumbered SG - add to all subnets
                    ADD sg TO matched_sgs

            // Replace subnet's SG children with matched list
            new_children = EMPTY LIST
            FOR EACH child IN graphdict[subnet]:
                IF child starts with "aws_security_group":
                    // Skip - will be replaced
                    CONTINUE
                ELSE:
                    ADD child TO new_children

            // Add matched SGs
            FOR EACH sg IN matched_sgs:
                ADD sg TO new_children

            graphdict[subnet] = new_children

    RETURN tfdata
```

**Result**: Each numbered subnet only contains security groups with matching numeric suffix.
