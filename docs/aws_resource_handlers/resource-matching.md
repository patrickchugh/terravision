# Resource Matching

## Table of Contents

1. [Availability Zone to Subnet Matching](#availability-zone-to-subnet-matching)
2. [EC2 to IAM Role Linking](#ec2-to-iam-role-linking)
3. [SQS Queue Policy Resolution](#sqs-queue-policy-resolution)
4. [Consolidated Subnet References Cleanup](#consolidated-subnet-references-cleanup)
5. [Special Behaviors](#special-behaviors)
   - [Empty Resource Cleanup](#empty-resource-cleanup)
   - [Count Propagation Rules](#count-propagation-rules)
   - [Numbered Resource Matching](#numbered-resource-matching)
6. [Helper Functions Reference](#helper-functions-reference)

---

## Availability Zone to Subnet Matching

**Purpose**: Ensure AZs only contain subnets with matching numeric suffixes.

**What Happens**:
- Extract numeric suffix from AZ name (`~1`, `~2`, `~3`)
- Extract numeric suffix from subnet name
- Keep only subnets where suffix matches AZ suffix

**Example**:
```
Before:
aws_az.us_east_1a~1: [subnet_public~1, subnet_public~2, subnet_private~1]

After:
aws_az.us_east_1a~1: [subnet_public~1, subnet_private~1]
```

**Why**: Prevents cross-AZ connections that don't make architectural sense.

### Implementation

```
FUNCTION match_subnets_to_availability_zones(tfdata):

    // Step 1: Find all numbered AZ nodes
    all_azs = FIND_RESOURCES_CONTAINING(graphdict, "aws_az.")
    numbered_azs = FILTER all_azs WHERE az contains "~"

    FOR EACH az IN numbered_azs:
        // Step 2: Extract AZ suffix
        az_suffix = EXTRACT_SUFFIX(az)  // e.g., "1" from "aws_az.us_east_1a~1"

        // Step 3: Filter subnets to only those with matching suffix
        current_subnets = COPY(graphdict[az])
        matched_subnets = EMPTY LIST

        FOR EACH subnet IN current_subnets:
            IF subnet contains "~":
                subnet_suffix = EXTRACT_SUFFIX(subnet)

                // Keep only if suffixes match
                IF subnet_suffix == az_suffix:
                    ADD subnet TO matched_subnets
            ELSE:
                // Unnumbered subnet - add to all AZs
                ADD subnet TO matched_subnets

        // Step 4: Replace AZ's subnet list with matched subnets
        graphdict[az] = matched_subnets

    RETURN tfdata
```

**Pattern**: Suffix matching ensures one-to-one AZ-to-subnet relationships in scaled infrastructure.

---

## EC2 to IAM Role Linking

**Purpose**: Show the IAM permissions associated with EC2 instances.

**What Happens**:
1. **Map instance profiles to IAM roles**:
   - Find all `aws_iam_role` → `aws_iam_instance_profile` connections
   - Build a mapping: profile → role

2. **Link EC2 to roles**:
   - Find all `aws_iam_instance_profile` → `aws_instance` connections
   - Add direct connection: IAM Role → EC2 Instance

**Transformation**:
```
Before:
aws_iam_role.app_role → aws_iam_instance_profile.app_profile
aws_iam_instance_profile.app_profile → aws_instance.web

After:
aws_iam_role.app_role → aws_instance.web
```

**Connections**:
- **Added**: IAM Role → EC2 Instance
- **Maintained**: Instance profile connections (for reference)

**Why**: Instance profiles are implementation details; architects care about role-to-instance relationships.

## Implementation

```
FUNCTION link_ec2_to_iam_roles(graphdict):

    // Step 1: Build mapping from instance profiles to IAM roles
    profile_to_role = EMPTY MAP

    FOR EACH resource IN graphdict:
        IF resource is "aws_iam_role":
            FOR EACH dependency IN graphdict[resource]:
                IF dependency is "aws_iam_instance_profile":
                    // Store: profile → role mapping
                    profile_to_role[dependency] = resource

    // Step 2: Create direct connections from roles to EC2 instances
    FOR EACH resource IN graphdict:
        IF resource is "aws_iam_instance_profile":
            IF resource exists in profile_to_role:
                iam_role = profile_to_role[resource]

                FOR EACH dependency IN graphdict[resource]:
                    IF dependency is "aws_instance":
                        // Create direct link: IAM Role → EC2 Instance
                        IF dependency NOT IN graphdict[iam_role]:
                            ADD dependency TO graphdict[iam_role]

    RETURN graphdict
```

**Two-Step Pattern**:
1. **Build Mapping**: Create intermediate mapping (instance profile → IAM role)
2. **Apply Mapping**: Use mapping to create direct connections (bypass instance profile)

**Result**: `IAM Role → EC2 Instance` instead of `IAM Role → Instance Profile → EC2 Instance`

---

## SQS Queue Policy Resolution

**Purpose**: Show direct connections from resources to SQS queues.

**What Happens**:
1. **Map queue policies to queues**:
   - Find all `aws_sqs_queue` → `aws_sqs_queue_policy` connections
   - Build a mapping: policy → queue

2. **Create transitive connections**:
   - For any resource that references a queue policy
   - Add a direct connection to the SQS queue

**Transformation**:
```
Before:
Lambda Function → SQS Queue Policy → SQS Queue

After:
Lambda Function → SQS Queue
```

**Connections**:
- **Added**: Resource → SQS Queue (direct)
- **Maintained**: Policy connections (for reference)

**Why**: Queue policies are access control; they shouldn't obscure the data flow relationship.

### Implementation

```
FUNCTION resolve_sqs_queue_policies(tfdata):

    // Step 1: Build mapping from queue policies to queues
    policy_to_queue = EMPTY MAP

    FOR EACH resource IN graphdict:
        IF resource starts with "aws_sqs_queue"
           AND resource does NOT contain "_policy":

            // This is a queue, check for policy connection
            FOR EACH dependency IN graphdict[resource]:
                IF dependency starts with "aws_sqs_queue_policy":
                    // Store: policy → queue mapping
                    policy_to_queue[dependency] = resource

    // Step 2: Find all resources that reference queue policies
    FOR EACH resource IN graphdict:
        connections = COPY(graphdict[resource])

        FOR EACH dependency IN connections:
            IF dependency IN policy_to_queue:
                // This resource references a queue policy
                actual_queue = policy_to_queue[dependency]

                // Create direct connection to the actual queue
                IF actual_queue NOT IN graphdict[resource]:
                    ADD actual_queue TO graphdict[resource]

                // Optionally remove the policy reference
                REMOVE dependency FROM graphdict[resource]

    RETURN tfdata
```

**Two-Step Pattern**:
1. **Build Mapping**: Create intermediate mapping (queue policy → SQS queue)
2. **Apply Mapping**: Use mapping to create direct connections (bypass queue policy)

**Result**: `Lambda → SQS Queue` instead of `Lambda → Queue Policy → SQS Queue`

---

## Consolidated Subnet References Cleanup

**Purpose**: Remove generic subnet references after numbered subnets are created.

**What Happens**:
- After subnets are expanded to `subnet~1`, `subnet~2`, etc.
- Remove any connections to the base `aws_subnet.name` (without suffix)
- Keep only connections to numbered instances

**Example**:
```
Before:
VPC → aws_subnet.public
VPC → aws_subnet.public~1
VPC → aws_subnet.public~2

After:
VPC → aws_subnet.public~1
VPC → aws_subnet.public~2
```

**Why**: Prevents duplicate/ghost subnet nodes in the diagram.

### Implementation

```
FUNCTION cleanup_consolidated_subnet_references(tfdata):

    // Step 1: Find all subnet base names that have numbered instances
    subnet_base_names = EMPTY SET
    numbered_subnets = EMPTY SET

    FOR EACH resource IN graphdict:
        IF resource starts with "aws_subnet" AND resource contains "~":
            base_name = REMOVE_SUFFIX(resource)
            ADD base_name TO subnet_base_names
            ADD resource TO numbered_subnets

    // Step 2: Remove base subnet references from all nodes
    FOR EACH node IN graphdict:
        connections = COPY(graphdict[node])
        has_numbered_subnet = false

        // Check if node has numbered subnet references
        FOR EACH connection IN connections:
            IF connection IN numbered_subnets:
                has_numbered_subnet = true
                BREAK

        // If node has numbered subnets, remove base subnet reference
        IF has_numbered_subnet:
            FOR EACH connection IN connections:
                IF connection IN subnet_base_names:
                    // Remove the base (unnumbered) subnet reference
                    REMOVE connection FROM graphdict[node]

    // Step 3: Remove base subnet nodes if they exist
    FOR EACH base_name IN subnet_base_names:
        IF base_name IN graphdict:
            DELETE graphdict[base_name]
        IF base_name IN meta_data:
            DELETE meta_data[base_name]

    RETURN tfdata
```

**Pattern**: After resource expansion (count > 1), remove generic base references to prevent duplicates.

**Result**: Clean diagram showing only numbered subnet instances, no base subnet ghosts.

---

## Special Behaviors

### Empty Resource Cleanup

**Random Strings**: All `random_string` resources are removed from the graph. They're Terraform utilities, not architecture components.

**Null Resources**: Null resources are removed as they don't represent actual infrastructure.

**Orphan Resources**: Resources with no connections and no parents are removed to keep diagrams clean.

---

### Count Propagation Rules

**Upward Propagation**: Count values propagate from child to parent:
- Subnet count → AZ count → VPC count
- Service count → Load Balancer count
- Backend count → Autoscaling Target count

**Maximum Count**: When multiple children have different counts, the parent takes the maximum:
```
ECS Service (count=3) → ALB
ECS Service (count=5) → ALB

Result: ALB count = 5
```

**Why**: Ensures the infrastructure can handle the maximum demand.

---

### Numbered Resource Matching

**Suffix Matching**: Resources with `count > 1` get numeric suffixes (`~1`, `~2`, etc.). Matching ensures:
- Resources with same suffix are connected
- Resources with different suffixes are not connected

**Pattern**:
```
resource~1 → dependency~1
resource~2 → dependency~2
resource~3 → dependency~3
```

**Prevents Invalid Connections**:
```
❌ resource~1 → dependency~2  (cross-connection)
✅ resource~1 → dependency~1  (matched)
```

**Why**: Maintains one-to-one relationships in scaled infrastructure.

---

## Helper Functions Reference

### Core Helper Functions

```
FUNCTION FIND_RESOURCES_CONTAINING(graphdict, pattern):
    // Find all resource names containing pattern
    // Example: FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")
    //          returns ["aws_subnet.public", "aws_subnet.private", ...]

    results = EMPTY LIST
    FOR EACH resource_name IN graphdict.keys():
        IF pattern is in resource_name:
            ADD resource_name TO results
    RETURN results

FUNCTION GET_PARENTS(graphdict, resource):
    // Find all resources that point to (depend on) the given resource
    // Supports wildcards: GET_PARENTS(graphdict, "aws_security_group.*")

    parents = EMPTY LIST
    FOR EACH resource IN graphdict:
        FOR EACH dependency IN graphdict[resource]:
            IF resource matches dependency pattern:
                IF resource NOT IN parents:
                    ADD resource TO parents
    RETURN parents

FUNCTION STRIP_MODULE_PREFIX(resource_name):
    // Remove module prefix from resource name
    // Example: "module.networking.aws_vpc.main" → "aws_vpc.main"

    IF resource_name contains "module.":
        parts = SPLIT resource_name by "."
        skip = true
        FOR EACH part IN parts:
            IF part != "module" AND skip is false:
                RETURN JOIN remaining parts with "."
            IF part == "module":
                skip = true
            ELSE:
                skip = false
    RETURN resource_name

FUNCTION CHECK_CONSOLIDATED(resource_type):
    // Check if resource type should be consolidated
    // Example: Multiple "aws_iam_role.role1", "aws_iam_role.role2"
    //          become single "aws_iam_role" node

    FOR EACH consolidated_type IN CONSOLIDATED_NODES:
        IF resource_type starts with consolidated_type:
            RETURN consolidated_type
    RETURN null

FUNCTION GET_VARIANT(resource, metadata):
    // Determine resource variant from metadata
    // Example: aws_lb with type="application" → "aws_alb"

    resource_type = EXTRACT_TYPE(resource)
    IF resource_type IN NODE_VARIANTS:
        attribute = NODE_VARIANTS[resource_type]
        IF attribute IN metadata:
            value = metadata[attribute]
            RETURN MAP_VARIANT(resource_type, value)
    RETURN null
```

### Common Patterns

**Safe Iteration**:
```
// GOOD: Copy list before modifying
connections = COPY(graphdict[resource])
FOR EACH connection IN connections:
    REMOVE connection FROM graphdict[resource]

// BAD: Modify during iteration
FOR EACH connection IN graphdict[resource]:
    REMOVE connection FROM graphdict[resource]  // ERROR: modifying during iteration
```

**Deep Copy Metadata**:
```
// GOOD: Deep copy nested structures
meta_data[new_node] = DEEP_COPY(meta_data[old_node])

// BAD: Shallow copy (references same object)
meta_data[new_node] = meta_data[old_node]
```

**Suffix Matching**:
```
// Extract numeric suffix from resource name
// Example: "aws_subnet.public~2" → "2"

IF resource_name contains "~":
    parts = SPLIT resource_name by "~"
    suffix = LAST part  // "2"
    base_name = ALL parts except last  // "aws_subnet.public"
```
