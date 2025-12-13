# Network Topology

## Table of Contents

1. [VPCs (Virtual Private Clouds)](#vpcs-virtual-private-clouds)
2. [Availability Zones](#availability-zones)
3. [Subnets](#subnets)
4. [NAT Gateways](#nat-gateways)
5. [VPC Endpoints](#vpc-endpoints)

---

## VPCs (Virtual Private Clouds)

**Transformation**: VPCs become the primary network boundary in diagrams.

**What Happens**:
- VPC is kept as a top-level container
- All resources within the VPC are organized hierarchically beneath it
- VPC-level resources (endpoints, gateways) are placed directly under the VPC

**Connections**:
- **Added**: Availability Zones are created and connected to the VPC
- **Removed**: Direct connections from VPC to individual resources are replaced with AZ intermediaries

### Implementation

```
FUNCTION handle_vpc_resources(tfdata):

    // Step 1: Find all VPC resources
    vpcs = FIND_RESOURCES_CONTAINING(graphdict, "aws_vpc.")

    IF vpcs is empty:
        RETURN tfdata

    // Step 2: VPCs are typically kept as-is in the graph
    // The main processing happens in child resources (subnets, AZs)
    // This function primarily ensures VPC exists as top-level container

    FOR EACH vpc IN vpcs:
        // Ensure VPC has metadata
        IF vpc NOT IN meta_data:
            CREATE meta_data[vpc] = EMPTY DICT

        // Ensure VPC exists in graphdict
        IF vpc NOT IN graphdict:
            CREATE graphdict[vpc] = EMPTY LIST

    RETURN tfdata
```

**Note**: VPCs require minimal transformation as they serve as containers. The hierarchy is built through child resources (AZs, subnets).

---

## Availability Zones

**Transformation**: TerraVision creates synthetic Availability Zone nodes based on subnet placement.

**What Happens**:
- Synthetic AZ nodes are created with names like `aws_az.availability_zone_us_east_1a~1`
- The AZ letter suffix (a, b, c) is converted to a number (1, 2, 3) for matching
- AZs are inserted between VPCs and subnets in the hierarchy

**Hierarchy Created**:
```
VPC
└── Availability Zone us-east-1a
    ├── Public Subnet
    ├── Private Subnet
    └── Database Subnet
```

**Connections**:
- **Added**: VPC connects to AZ nodes
- **Added**: AZ nodes connect to subnets within that AZ
- **Removed**: Direct VPC-to-subnet connections

**Count Propagation**: AZ nodes inherit the count from their subnets, so if a subnet has `count=3`, the AZ also shows 3 instances.

### Implementation

```
FUNCTION create_availability_zone_nodes(tfdata):

    // Step 1: Find all subnet resources (excluding hidden ones)
    subnet_resources = FIND resources in graphdict
                       WHERE resource name starts with "aws_subnet"
                       AND resource not in hidden list

    // Step 2: Process each subnet
    FOR EACH subnet IN subnet_resources:

        // Find all resources that point to this subnet
        parents = GET_PARENTS(graphdict, subnet)

        FOR EACH parent IN parents:

            // Remove direct connection from parent to subnet
            REMOVE subnet FROM graphdict[parent]

            // Build AZ node name from subnet's metadata
            az_name = subnet.metadata["availability_zone"]
            az_node_name = "aws_az.availability_zone_" + az_name
            az_node_name = REPLACE(az_node_name, "-", "_")

            // Handle region placeholder
            region = subnet.metadata["region"]
            IF region exists:
                az_node_name = REPLACE(az_node_name, "True", region)
            ELSE:
                az_node_name = REPLACE(az_node_name, ".True", ".availability_zone")

            // Convert AZ letter to number
            // Example: "us-east-1a" → "us_east_1a~1"
            //          "us-east-1b" → "us_east_1b~2"
            IF last character is alphabetic:
                suffix = (ASCII_VALUE(last_char) - ASCII_VALUE('a')) + 1
                az_node_name = az_node_name + "~" + suffix

            // Create AZ node if it doesn't exist
            IF az_node_name NOT IN graphdict:
                CREATE graphdict[az_node_name] = empty list
                CREATE meta_data[az_node_name] = {
                    "count": subnet.metadata["count"]
                }

            // Link AZ to subnet (if parent is VPC)
            IF "aws_vpc" IN parent name:
                ADD subnet TO graphdict[az_node_name]

            // Link parent to AZ
            IF az_node_name NOT IN graphdict[parent]:
                ADD az_node_name TO graphdict[parent]

    RETURN tfdata
```

**Key Operations**:
- `GET_PARENTS(graphdict, resource)`: Find all resources that point to the given resource
- `REMOVE x FROM list`: Remove connection from graph
- `ADD x TO list`: Add connection to graph
- `REPLACE(string, old, new)`: String replacement
- Suffix conversion uses ASCII values: 'a'=97 → suffix 1, 'b'=98 → suffix 2

**Data Structures**:
- `graphdict[resource_name]` = list of resources this resource points to
- `meta_data[resource_name]` = dictionary of resource attributes

---

## Subnets

**Transformation**: Subnets are positioned within their Availability Zones.

**What Happens**:
- Subnets are removed from direct VPC attachment
- Subnets are connected to their AZ based on the `availability_zone` attribute
- Resources within subnets (EC2, RDS, etc.) remain connected to the subnet

**Connections**:
- **Removed**: Direct parent connections to VPC
- **Added**: Parent connection to Availability Zone
- **Maintained**: Child connections to resources (EC2, Lambda, etc.)

**Numbered Subnets**: When subnets have `count > 1`, they're expanded to numbered instances (`subnet~1`, `subnet~2`) and matched to correspondingly numbered AZs.

### Implementation

```
FUNCTION handle_subnet_resources(tfdata):

    // Step 1: Find all subnets
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")
    subnets = FILTER subnets WHERE subnet NOT IN hidden_list

    FOR EACH subnet IN subnets:
        // Step 2: Ensure subnet metadata exists
        IF subnet NOT IN meta_data:
            CREATE meta_data[subnet] = EMPTY DICT

        // Step 3: Extract availability zone information
        IF "availability_zone" IN meta_data[subnet]:
            az_name = meta_data[subnet]["availability_zone"]

            // Step 4: Handle numbered subnets (count > 1)
            IF subnet contains "~":
                suffix = EXTRACT_SUFFIX(subnet)

                // Match to corresponding numbered AZ
                az_node = "aws_az.availability_zone_" + az_name + "~" + suffix
            ELSE:
                az_node = "aws_az.availability_zone_" + az_name

            // Step 5: Ensure subnet remains in graphdict
            IF subnet NOT IN graphdict:
                CREATE graphdict[subnet] = EMPTY LIST

    RETURN tfdata
```

**Note**: Most subnet transformation happens in the `create_availability_zone_nodes` function which reorganizes the parent-child relationships.

---

## NAT Gateways

**Transformation**: NAT gateways are split into per-subnet instances.

**What Happens**:
- If a single NAT gateway resource is referenced by multiple numbered public subnets, it's split into numbered instances
- Each public subnet gets its own NAT gateway instance with matching suffix

**Example**:
```
Before:
aws_nat_gateway.main

After:
aws_nat_gateway.main~1  (for public_subnet~1)
aws_nat_gateway.main~2  (for public_subnet~2)
aws_nat_gateway.main~3  (for public_subnet~3)
```

**Connections**:
- **Removed**: Generic NAT gateway reference from subnets
- **Added**: Suffix-matched NAT gateway per subnet

### Implementation

```
FUNCTION split_nat_gateways(graphdict):

    // Step 1: Find unnumbered NAT gateways
    nat_gateways = FIND resources in graphdict
                   WHERE resource contains "aws_nat_gateway"
                   AND resource does NOT contain "~"

    // Step 2: For each generic NAT gateway
    FOR EACH nat_gw IN nat_gateways:

        // Find public subnets that reference this NAT
        subnet_suffixes = EMPTY SET

        FOR EACH resource IN graphdict:
            IF resource contains "public_subnets" AND resource contains "~":
                // Extract suffix from subnet (e.g., "~1", "~2")
                suffix = EXTRACT_SUFFIX(resource)

                // Check if this subnet references the NAT gateway
                IF nat_gw IN graphdict[resource]:
                    ADD suffix TO subnet_suffixes

        // Step 3: Create numbered NAT gateway instances
        FOR EACH suffix IN subnet_suffixes:
            numbered_nat = nat_gw + "~" + suffix
            CREATE graphdict[numbered_nat] = COPY(graphdict[nat_gw])

        // Step 4: Remove original if numbered ones were created
        IF subnet_suffixes is not empty:
            DELETE graphdict[nat_gw]

    // Step 5: Update subnet references to use numbered NATs
    FOR EACH resource IN graphdict:
        IF resource contains "public_subnets" AND resource contains "~":
            suffix = EXTRACT_SUFFIX(resource)

            // Replace generic NAT with numbered NAT
            new_deps = EMPTY LIST
            FOR EACH dep IN graphdict[resource]:
                IF dep contains "aws_nat_gateway" AND dep does NOT contain "~":
                    ADD (dep + "~" + suffix) TO new_deps
                ELSE:
                    ADD dep TO new_deps
            graphdict[resource] = new_deps

    RETURN graphdict
```

**Pattern**: One NAT gateway per public subnet (common HA pattern)

---

## VPC Endpoints

**Transformation**: VPC endpoints are consolidated into the VPC container.

**What Happens**:
- VPC endpoints are removed as standalone nodes
- They're added to the VPC's internal resource list
- This keeps the diagram cleaner while maintaining visibility

**Connections**:
- **Removed**: VPC endpoint as a separate node
- **Added**: VPC endpoint shown inside VPC container

### Implementation

```
FUNCTION consolidate_vpc_endpoints(tfdata):

    // Step 1: Find VPC endpoints
    vpc_endpoints = FIND_RESOURCES_CONTAINING(graphdict, "aws_vpc_endpoint")

    // Step 2: Find the VPC
    vpcs = FIND_RESOURCES_CONTAINING(graphdict, "aws_vpc.")
    IF vpcs is empty:
        RETURN tfdata

    vpc = vpcs[0]  // Assume single VPC (most common case)

    // Step 3: Move endpoints into VPC
    FOR EACH vpc_endpoint IN vpc_endpoints:
        // Add endpoint to VPC's children
        ADD vpc_endpoint TO graphdict[vpc]

        // Remove endpoint as standalone node
        DELETE graphdict[vpc_endpoint]

    RETURN tfdata
```

**Result**: VPC endpoints appear inside VPC boundary, not as separate nodes
