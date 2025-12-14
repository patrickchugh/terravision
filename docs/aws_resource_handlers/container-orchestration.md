# Container Orchestration

## Table of Contents

1. [EKS Cluster Grouping](#eks-cluster-grouping)
2. [EKS Node Groups](#eks-node-groups)
3. [EKS Control Plane to Node Linking](#eks-control-plane-to-node-linking)
4. [EKS Fargate Profiles](#eks-fargate-profiles)

---

## EKS Cluster Grouping

**Philosophy**: EKS clusters consist of a managed control plane (master) and worker nodes distributed across subnets. The diagram should show the control plane as a grouped service that orchestrates the worker nodes.

**Transformation**: Create an EKS group container that holds the control plane and points to worker nodes in their respective subnets.

**Core Transformation**:
```
Before (Terraform's view):
Subnet → EKS Node Group → Worker Nodes
EKS Cluster (separate, disconnected)

After (Architecture view):
aws_group.eks_service
└── EKS Control Plane (aws_eks_cluster)
    ├── Worker Nodes in Subnet~1
    ├── Worker Nodes in Subnet~2
    └── Worker Nodes in Subnet~3
```

This reflects how EKS actually works: a centralized control plane managing distributed worker nodes.

---

## EKS Node Groups

**Transformation**: EKS node groups and their worker nodes remain in their subnets but are linked to the control plane.

**What Happens**:
1. **Identify EKS resources**:
   - Find `aws_eks_cluster` (control plane)
   - Find `aws_eks_node_group` (node group definitions)
   - Find worker nodes (EC2 instances or Auto Scaling groups)

2. **Create EKS service group**:
   - A synthetic group `aws_group.eks_service` is created
   - The EKS cluster (control plane) is placed inside this group
   - The group is positioned outside the VPC hierarchy

3. **Link control plane to nodes**:
   - The EKS cluster points to all worker nodes
   - Worker nodes remain in their subnets
   - Node groups act as intermediaries showing the scaling configuration

**Hierarchy**:
```
aws_group.eks_service
└── aws_eks_cluster.main (Control Plane)
    └── Points to:
        ├── Subnet~1 → aws_eks_node_group.workers~1 → Worker Nodes
        ├── Subnet~2 → aws_eks_node_group.workers~2 → Worker Nodes
        └── Subnet~3 → aws_eks_node_group.workers~3 → Worker Nodes
```

**Connections**:
- **Added**: EKS service group container
- **Added**: Control plane inside EKS service group
- **Added**: Control plane → Worker nodes (across all subnets)
- **Maintained**: Worker nodes remain in subnets
- **Removed**: Direct node group connections that bypass the control plane

**Why**: This shows the Kubernetes architecture pattern where a control plane manages pods/nodes across multiple availability zones.

---

## EKS Control Plane to Node Linking

**Transformation**: Establish explicit connections from the EKS control plane to all worker nodes.

**What Happens**:
1. **Collect all worker nodes**: Find EC2 instances or ASG resources associated with EKS node groups
2. **Create control plane links**: The EKS cluster points to all worker nodes
3. **Propagate count**: If node groups have multiple instances, the control plane connection reflects this
4. **Suffix matching**: Node groups with `~1`, `~2`, `~3` suffixes are matched to corresponding subnet instances

**Example**:
```
Terraform Resources:
- aws_eks_cluster.main
- aws_eks_node_group.workers (desired_size=3)
- aws_subnet.private~1, private~2, private~3

After Transformation:
aws_group.eks_service
└── aws_eks_cluster.main
    ├── aws_eks_node_group.workers~1 (in private~1)
    ├── aws_eks_node_group.workers~2 (in private~2)
    └── aws_eks_node_group.workers~3 (in private~3)
```

**Connections**:
- **Added**: EKS Cluster → Node Group instances (suffix-matched)
- **Added**: Node Group → Worker Nodes (EC2/ASG)
- **Maintained**: Worker nodes stay in their subnets

### Implementation

```
FUNCTION handle_eks_cluster_grouping(tfdata):

    // Step 1: Find EKS resources
    eks_clusters = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_cluster")
    eks_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")

    IF eks_clusters is empty:
        RETURN tfdata  // No EKS resources to process

    // Step 2: Create EKS service group for each cluster
    FOR EACH cluster IN eks_clusters:
        cluster_name = EXTRACT_NAME(cluster)
        eks_group_name = "aws_group.eks_service_" + cluster_name

        // Create EKS service group
        IF eks_group_name NOT IN graphdict:
            CREATE graphdict[eks_group_name] = EMPTY LIST
            CREATE meta_data[eks_group_name] = {
                "type": "eks_service",
                "name": "EKS Service - " + cluster_name
            }

        // Step 3: Move control plane into EKS service group
        IF cluster NOT IN graphdict[eks_group_name]:
            ADD cluster TO graphdict[eks_group_name]

        // Step 4: Remove cluster from VPC/subnet hierarchy (if present)
        FOR EACH node IN graphdict:
            node_type = EXTRACT_TYPE(node)
            IF node_type IN ["aws_vpc", "aws_subnet", "aws_az"]:
                IF cluster IN graphdict[node]:
                    REMOVE cluster FROM graphdict[node]

    RETURN tfdata
```

**Key Operations**:
- `EXTRACT_NAME(resource)`: Get resource name (e.g., "main" from "aws_eks_cluster.main")
- `EXTRACT_TYPE(resource)`: Get resource type portion (e.g. "aws_subnet" from aws_subnet.prviate)
- Creates synthetic group with naming pattern `aws_group.eks_service_{cluster_name}`
- Removes control plane from network hierarchy (it's a managed service)

---

### Implementation: Link Control Plane to Nodes

```
FUNCTION link_eks_control_plane_to_nodes(tfdata):

    // Step 1: Find EKS clusters and node groups
    eks_clusters = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_cluster")
    eks_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")

    FOR EACH cluster IN eks_clusters:
        // Step 2: Find node groups belonging to this cluster
        cluster_node_groups = EMPTY LIST

        FOR EACH node_group IN eks_node_groups:
            // Check if node group references this cluster
            IF "cluster_name" IN meta_data[node_group]:
                cluster_ref = meta_data[node_group]["cluster_name"]
                IF cluster IN cluster_ref OR EXTRACT_NAME(cluster) IN cluster_ref:
                    ADD node_group TO cluster_node_groups

        // Step 3: Expand node groups if they have count/desired_size
        FOR EACH node_group IN cluster_node_groups:
            node_count = 1

            // Get desired instance count
            IF "desired_size" IN meta_data[node_group]:
                node_count = meta_data[node_group]["desired_size"]
            ELSE IF "count" IN meta_data[node_group]:
                node_count = meta_data[node_group]["count"]

            // Step 4: Create numbered node group instances if needed
            IF node_count > 1 AND node_group does NOT contain "~":
                // Create numbered instances
                FOR i FROM 1 TO node_count:
                    numbered_node_group = node_group + "~" + i
                    CREATE graphdict[numbered_node_group] = COPY(graphdict[node_group])
                    CREATE meta_data[numbered_node_group] = DEEP_COPY(meta_data[node_group])

                // Remove original unnumbered node group
                DELETE graphdict[node_group]

        // Step 5: Link cluster to all node groups (numbered or not)
        all_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")

        FOR EACH node_group IN all_node_groups:
            // Verify this node group belongs to this cluster
            IF "cluster_name" IN meta_data[node_group]:
                cluster_ref = meta_data[node_group]["cluster_name"]
                IF cluster IN cluster_ref OR EXTRACT_NAME(cluster) IN cluster_ref:
                    // Add connection from cluster to node group
                    IF node_group NOT IN graphdict[cluster]:
                        ADD node_group TO graphdict[cluster]

    RETURN tfdata
```

**Process Flow**:
1. Find clusters and their associated node groups (via `cluster_name` metadata)
2. Expand node groups based on `desired_size` attribute
3. Create numbered node group instances (`node_group~1`, `node_group~2`, etc.)
4. Link control plane to all node group instances

---

### Implementation: Match Node Groups to Subnets

```
FUNCTION match_node_groups_to_subnets(tfdata):

    // Step 1: Find all node groups and subnets
    eks_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")

    // Step 2: For each node group, determine which subnets it uses
    FOR EACH node_group IN eks_node_groups:
        // Check metadata for subnet references
        subnet_ids = EMPTY LIST

        IF "subnet_ids" IN meta_data[node_group]:
            subnet_ids = meta_data[node_group]["subnet_ids"]

        // Step 3: Match numbered node groups to numbered subnets
        IF node_group contains "~":
            node_suffix = EXTRACT_SUFFIX(node_group)

            // Find matching subnets with same suffix
            FOR EACH subnet IN subnets:
                IF subnet contains "~":
                    subnet_suffix = EXTRACT_SUFFIX(subnet)

                    // Match by suffix
                    IF subnet_suffix == node_suffix:
                        // Add node group to this subnet
                        IF node_group NOT IN graphdict[subnet]:
                            ADD node_group TO graphdict[subnet]

                        // Remove node group from other subnets
                        FOR EACH other_subnet IN subnets:
                            IF other_subnet != subnet:
                                IF node_group IN graphdict[other_subnet]:
                                    REMOVE node_group FROM graphdict[other_subnet]

        ELSE:
            // Unnumbered node group - determine matching subnets
            matching_subnets = EMPTY LIST

            FOR EACH subnet IN subnets:
                subnet_id = meta_data[subnet]["id"] IF "id" IN meta_data[subnet] ELSE ""

                IF subnet_id IN subnet_ids OR EXTRACT_NAME(subnet) IN subnet_ids:
                    ADD subnet TO matching_subnets

            // Step 4: If node group spans multiple subnets, create numbered instances
            IF LENGTH(matching_subnets) > 1:
                // Create numbered node group instances
                FOR i FROM 1 TO LENGTH(matching_subnets):
                    numbered_node_group = node_group + "~" + i
                    subnet = matching_subnets[i - 1]

                    // Create numbered instance if doesn't exist
                    IF numbered_node_group NOT IN graphdict:
                        CREATE graphdict[numbered_node_group] = COPY(graphdict[node_group])
                        CREATE meta_data[numbered_node_group] = DEEP_COPY(meta_data[node_group])

                    // Add numbered node group to subnet
                    IF numbered_node_group NOT IN graphdict[subnet]:
                        ADD numbered_node_group TO graphdict[subnet]

                // Remove original unnumbered node group
                DELETE graphdict[node_group]
                DELETE meta_data[node_group]

            ELSE IF LENGTH(matching_subnets) == 1:
                // Single subnet - add node group directly
                subnet = matching_subnets[0]
                IF node_group NOT IN graphdict[subnet]:
                    ADD node_group TO graphdict[subnet]

    // Step 5: Link newly created numbered node groups to their control plane
    eks_clusters = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_cluster")
    all_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")

    FOR EACH cluster IN eks_clusters:
        cluster_name = EXTRACT_NAME(cluster)

        FOR EACH node_group IN all_node_groups:
            // Check if this node group belongs to this cluster
            IF node_group IN meta_data:
                cluster_ref = meta_data[node_group]["cluster_name"]
                IF cluster IN cluster_ref OR cluster_name IN cluster_ref:
                    // Add connection from cluster to node group if not present
                    IF node_group NOT IN graphdict[cluster]:
                        ADD node_group TO graphdict[cluster]

    RETURN tfdata
```

**Suffix Matching Logic**:
- Node group `workers~1` → Subnet `private~1`
- Node group `workers~2` → Subnet `private~2`
- Node group `workers~3` → Subnet `private~3`

This ensures each node group instance is placed in the correct AZ/subnet.

**Numbered Instance Creation**:

Numbered node group instances are created in two scenarios:

1. **Based on `desired_size`** (in `link_eks_control_plane_to_nodes`):
   - If `desired_size=3`, creates `workers~1`, `workers~2`, `workers~3`
   - Happens before subnet matching

2. **Based on `subnet_ids` count** (in `match_node_groups_to_subnets`):
   - If node group has `subnet_ids=[subnet1, subnet2, subnet3]` but no numbered instances yet
   - Creates `workers~1`, `workers~2`, `workers~3` to prevent Graphviz errors
   - Each instance is placed in exactly one subnet
   - Prevents the same node resource from appearing in multiple parent subnets

**Critical**: A single resource node cannot be added to multiple parent nodes in Graphviz. Creating numbered instances ensures each subnet gets its own dedicated node group instance.

---

### Implementation: Link Node Groups to Worker Nodes

```
FUNCTION link_node_groups_to_worker_nodes(tfdata):

    // Step 1: Find node groups and potential worker nodes
    eks_node_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_node_group")
    ec2_instances = FIND_RESOURCES_CONTAINING(graphdict, "aws_instance")
    auto_scaling_groups = FIND_RESOURCES_CONTAINING(graphdict, "aws_autoscaling_group")

    FOR EACH node_group IN eks_node_groups:
        // Step 2: Find worker nodes associated with this node group
        // Workers can be EC2 instances or ASG resources

        // Check for ASG-based node groups
        FOR EACH asg IN auto_scaling_groups:
            // Check if ASG name or tags reference this node group
            IF "tags" IN meta_data[asg]:
                tags = meta_data[asg]["tags"]
                node_group_name = EXTRACT_NAME(node_group)

                IF node_group_name IN tags OR "eks:nodegroup-name" IN tags:
                    // Link node group to ASG
                    IF asg NOT IN graphdict[node_group]:
                        ADD asg TO graphdict[node_group]

        // Check for EC2-based worker nodes
        FOR EACH instance IN ec2_instances:
            IF "tags" IN meta_data[instance]:
                tags = meta_data[instance]["tags"]
                node_group_name = EXTRACT_NAME(node_group)

                IF "eks:nodegroup-name" IN tags:
                    nodegroup_tag = tags["eks:nodegroup-name"]
                    IF node_group_name IN nodegroup_tag:
                        // Link node group to EC2 instance
                        IF instance NOT IN graphdict[node_group]:
                            ADD instance TO graphdict[node_group]

        // Step 3: If node group has no workers, create placeholder
        IF graphdict[node_group] is empty:
            // Node group manages workers externally, keep it visible
            meta_data[node_group]["note"] = "Manages worker nodes (count: " +
                                            meta_data[node_group]["desired_size"] + ")"

    RETURN tfdata
```

**Worker Node Detection**:
- Uses AWS tags (`eks:nodegroup-name`) to identify workers
- Links node groups to Auto Scaling Groups (common pattern)
- Links node groups to EC2 instances (direct worker nodes)
- Adds metadata note if workers are externally managed

---

## EKS Fargate Profiles

**Philosophy**: EKS Fargate profiles define serverless compute capacity for running Kubernetes pods without managing EC2 instances. When a Fargate profile spans multiple subnets (for high availability across AZs), it should be split into numbered instances - one per subnet - just like node groups. This clearly shows the distributed serverless architecture.

**Transformation**: Fargate profiles that reference multiple subnets are expanded into numbered instances, with the original unnumbered profile deleted (same behavior as node groups).

**Core Transformation**:
```
Before (Terraform's view):
aws_eks_fargate_profile.default
├── subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]
└── cluster_name = aws_eks_cluster.main

After (Architecture view):
EKS Control Plane
├── aws_eks_fargate_profile.default~1
└── aws_eks_fargate_profile.default~2

Subnet private_1
└── aws_eks_fargate_profile.default~1

Subnet private_2
└── aws_eks_fargate_profile.default~2
```

This reflects how Fargate works: serverless compute distributed across availability zones, with each instance tied to a specific subnet.

---

### What Happens

1. **Identify Fargate profiles**:
   - Find `aws_eks_fargate_profile` resources
   - Extract `subnet_ids` from metadata
   - Determine how many subnets the profile spans

2. **Create numbered instances**:
   - If profile spans multiple subnets (most common), create numbered instances
   - Pattern: `aws_eks_fargate_profile.default` → `default~1`, `default~2`, etc.
   - Each numbered instance is an independent resource

3. **Match to subnets**:
   - Place each numbered Fargate profile instance in exactly one subnet
   - Match by subnet name or ID from `subnet_ids` metadata
   - Use sorted order to ensure deterministic suffix assignment

4. **Link to control plane**:
   - Update EKS cluster connections to reference all numbered Fargate profiles
   - Remove references to the original unnumbered profile
   - Delete the original unnumbered profile from graph

**Hierarchy**:
```
aws_group.eks_service_main
└── aws_eks_cluster.main (Control Plane)
    ├── aws_eks_fargate_profile.default~1
    ├── aws_eks_fargate_profile.default~2
    ├── aws_eks_fargate_profile.kube_system~1
    └── aws_eks_fargate_profile.kube_system~2

VPC
├── AZ us-east-1a
│   └── Subnet private_1
│       ├── aws_eks_fargate_profile.default~1
│       └── aws_eks_fargate_profile.kube_system~1
└── AZ us-east-1b
    └── Subnet private_2
        ├── aws_eks_fargate_profile.default~2
        └── aws_eks_fargate_profile.kube_system~2
```

**Connections**:
- **Added**: Numbered Fargate profile instances (`profile~1`, `profile~2`)
- **Added**: Subnet → Numbered Fargate instances
- **Added**: EKS Cluster → All numbered Fargate profiles
- **Removed**: Original unnumbered Fargate profile (deleted from graph)

**Why**: Prevents Graphviz errors where a single resource appears in multiple parent containers. Each subnet needs its own dedicated Fargate profile instance to show the distributed serverless architecture.

---

### Implementation: Match Fargate Profiles to Subnets

```
FUNCTION match_fargate_profiles_to_subnets(tfdata):

    // Step 1: Find all Fargate profiles and subnets
    fargate_profiles = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_fargate_profile")
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")

    FOR EACH profile IN fargate_profiles:
        // Skip if already numbered (already processed)
        IF profile contains "~":
            CONTINUE

        // Step 2: Extract subnet references from metadata
        subnet_ids = EMPTY LIST

        IF profile IN meta_data:
            IF "subnet_ids" IN meta_data[profile]:
                subnet_ids = meta_data[profile]["subnet_ids"]

                // Convert string to list if needed
                IF subnet_ids is STRING:
                    subnet_ids = [subnet_ids]

        // Step 3: Find matching subnets by ID or name
        matching_subnets = EMPTY LIST

        FOR EACH subnet IN subnets:
            subnet_id = meta_data[subnet]["id"] IF "id" IN meta_data[subnet] ELSE ""
            subnet_name = EXTRACT_NAME(subnet)

            // Check if this subnet matches any of the profile's subnet_ids
            FOR EACH sid IN subnet_ids:
                IF subnet_id IN sid OR subnet_name IN sid:
                    ADD subnet TO matching_subnets
                    BREAK

        // Step 4: Create numbered Fargate instances if multiple subnets
        IF LENGTH(matching_subnets) > 1:
            // Sort subnets for deterministic suffix assignment
            SORT matching_subnets

            FOR i FROM 1 TO LENGTH(matching_subnets):
                numbered_profile = profile + "~" + i
                subnet = matching_subnets[i - 1]

                // Create numbered instance if doesn't exist
                IF numbered_profile NOT IN graphdict:
                    CREATE graphdict[numbered_profile] = COPY(graphdict[profile])
                    CREATE meta_data[numbered_profile] = DEEP_COPY(meta_data[profile])

                // Add numbered profile to this specific subnet
                IF numbered_profile NOT IN graphdict[subnet]:
                    ADD numbered_profile TO graphdict[subnet]

                // Remove unnumbered profile from subnet if present
                IF profile IN graphdict[subnet]:
                    REMOVE profile FROM graphdict[subnet]

            // Step 5: Update EKS cluster to reference numbered profiles
            eks_clusters = FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_cluster")

            FOR EACH cluster IN eks_clusters:
                // If cluster references unnumbered profile, replace with numbered ones
                IF profile IN graphdict[cluster]:
                    REMOVE profile FROM graphdict[cluster]

                    // Add all numbered profiles to cluster
                    FOR i FROM 1 TO LENGTH(matching_subnets):
                        numbered_profile = profile + "~" + i
                        IF numbered_profile NOT IN graphdict[cluster]:
                            ADD numbered_profile TO graphdict[cluster]

            // Step 6: Update other resources that reference the Fargate profile
            // (e.g., IAM roles for Fargate pod execution)
            FOR EACH resource IN graphdict:
                IF profile IN graphdict[resource]:
                    REMOVE profile FROM graphdict[resource]

                    // Add all numbered profiles
                    FOR i FROM 1 TO LENGTH(matching_subnets):
                        numbered_profile = profile + "~" + i
                        IF numbered_profile NOT IN graphdict[resource]:
                            ADD numbered_profile TO graphdict[resource]

            // Step 7: Delete original unnumbered profile
            IF profile IN graphdict:
                DELETE graphdict[profile]
            IF profile IN meta_data:
                DELETE meta_data[profile]

        ELSE IF LENGTH(matching_subnets) == 1:
            // Single subnet - keep profile as-is, just add to subnet
            subnet = matching_subnets[0]
            IF profile NOT IN graphdict[subnet]:
                ADD profile TO graphdict[subnet]

    RETURN tfdata
```

**Process Flow**:
1. Find all Fargate profiles that aren't already numbered
2. Extract `subnet_ids` from profile metadata
3. Match subnets by comparing IDs or names
4. Create numbered instances for each subnet (`profile~1`, `profile~2`)
5. Update cluster connections to reference numbered profiles
6. Update all other resources (IAM roles, etc.) to reference numbered profiles
7. Delete original unnumbered profile

---

### Example Transformation

**Terraform Code**:
```hcl
resource "aws_eks_fargate_profile" "default" {
  cluster_name = aws_eks_cluster.main.name
  fargate_profile_name = "default-profile"
  pod_execution_role_arn = aws_iam_role.fargate_pod.arn
  subnet_ids = [
    aws_subnet.private_1.id,
    aws_subnet.private_2.id
  ]

  selector {
    namespace = "default"
  }
}

resource "aws_eks_fargate_profile" "kube_system" {
  cluster_name = aws_eks_cluster.main.name
  fargate_profile_name = "kube-system-profile"
  pod_execution_role_arn = aws_iam_role.fargate_pod.arn
  subnet_ids = [
    aws_subnet.private_1.id,
    aws_subnet.private_2.id
  ]

  selector {
    namespace = "kube-system"
  }
}
```

**Before Transformation** (graphdict):
```json
{
  "aws_eks_fargate_profile.default": [],
  "aws_eks_fargate_profile.kube_system": [],
  "aws_subnet.private_1": [
    "aws_eks_fargate_profile.default",
    "aws_eks_fargate_profile.kube_system"
  ],
  "aws_subnet.private_2": [
    "aws_eks_fargate_profile.default",
    "aws_eks_fargate_profile.kube_system"
  ],
  "aws_eks_cluster.main": [
    "aws_eks_fargate_profile.default",
    "aws_eks_fargate_profile.kube_system"
  ],
  "aws_iam_role.fargate_pod": [
    "aws_eks_fargate_profile.default",
    "aws_eks_fargate_profile.kube_system"
  ]
}
```

**Problem**: Same Fargate profiles appear in two parent subnets - Graphviz error!

**After Transformation** (graphdict):
```json
{
  "aws_eks_fargate_profile.default~1": [],
  "aws_eks_fargate_profile.default~2": [],
  "aws_eks_fargate_profile.kube_system~1": [],
  "aws_eks_fargate_profile.kube_system~2": [],
  "aws_subnet.private_1": [
    "aws_eks_fargate_profile.default~1",
    "aws_eks_fargate_profile.kube_system~1"
  ],
  "aws_subnet.private_2": [
    "aws_eks_fargate_profile.default~2",
    "aws_eks_fargate_profile.kube_system~2"
  ],
  "aws_eks_cluster.main": [
    "aws_eks_fargate_profile.default~1",
    "aws_eks_fargate_profile.default~2",
    "aws_eks_fargate_profile.kube_system~1",
    "aws_eks_fargate_profile.kube_system~2"
  ],
  "aws_iam_role.fargate_pod": [
    "aws_eks_fargate_profile.default~1",
    "aws_eks_fargate_profile.default~2",
    "aws_eks_fargate_profile.kube_system~1",
    "aws_eks_fargate_profile.kube_system~2"
  ]
}
```

**Solution**: Each subnet gets its own numbered Fargate profile instance. Unnumbered profiles deleted.

---

### Fargate vs Node Groups - Identical Behavior

| Aspect | Node Groups | Fargate Profiles |
|--------|-------------|------------------|
| **Infrastructure** | EC2 instances (visible) | Serverless (no instances) |
| **Numbering trigger** | `desired_size` or `subnet_ids` | `subnet_ids` count |
| **Original resource** | **DELETED** after numbering | **DELETED** after numbering |
| **Cluster links to** | Numbered instances (`~1`, `~2`) | Numbered instances (`~1`, `~2`) |
| **Subnet links to** | Numbered instances (`~1`, `~2`) | Numbered instances (`~1`, `~2`) |
| **Child resources** | Links to ASG/EC2 instances | No child resources (leaf nodes) |
| **Numbering behavior** | **SAME** | **SAME** |

---

### Key Patterns

**Fargate Profile Metadata**:
```
meta_data["aws_eks_fargate_profile.default~1"] = {
    "cluster_name": "aws_eks_cluster.main",
    "fargate_profile_name": "default-profile",
    "subnet_ids": [
        "aws_subnet.private_1.id",
        "aws_subnet.private_2.id"
    ],
    "selector": {
        "namespace": "default"
    }
}
```

**Numbered Instance Naming**:
- Pattern: `{profile_name}~{subnet_index}`
- Example: `aws_eks_fargate_profile.default~1`
- Suffix matches subnet order (sorted alphabetically)

**Subnet Matching Logic**:
1. Extract subnet names from `subnet_ids`: `["private_1", "private_2"]`
2. Sort matching subnets alphabetically: `[private_1, private_2]`
3. Assign suffixes in order: `private_1` → `~1`, `private_2` → `~2`

---

### Special Cases

**Single Subnet Fargate Profile**:
```hcl
resource "aws_eks_fargate_profile" "single" {
  subnet_ids = [aws_subnet.private_1.id]
}
```
- No numbering needed (only one subnet)
- Profile remains unnumbered: `aws_eks_fargate_profile.single`
- Direct connection: `Subnet → Profile → Cluster`

**Multiple Fargate Profiles in Same Subnets**:
```
Subnet private_1
├── aws_eks_fargate_profile.default~1 (namespace: default)
└── aws_eks_fargate_profile.kube_system~1 (namespace: kube-system)

Subnet private_2
├── aws_eks_fargate_profile.default~2 (namespace: default)
└── aws_eks_fargate_profile.kube_system~2 (namespace: kube-system)
```
- Each profile is numbered independently
- Selectors differentiate which pods run on which profile (namespace filtering)

**Mixed EKS Deployment** (Node Groups + Fargate):
```
aws_group.eks_service_main
└── aws_eks_cluster.main
    ├── aws_eks_node_group.workers~1 (EC2-based)
    ├── aws_eks_node_group.workers~2 (EC2-based)
    ├── aws_eks_fargate_profile.default~1 (Serverless)
    ├── aws_eks_fargate_profile.default~2 (Serverless)
    ├── aws_eks_fargate_profile.kube_system~1 (Serverless)
    └── aws_eks_fargate_profile.kube_system~2 (Serverless)
```
- Both compute types coexist in the same cluster
- Both use identical numbering pattern (suffix matching)
- Node groups show EC2 instances, Fargate profiles remain leaf nodes

---

## Complete Processing Order

The EKS handlers should be executed in this sequence:

1. **`handle_eks_cluster_grouping`**: Create EKS service group, move control plane
2. **`link_eks_control_plane_to_nodes`**: Expand node groups, link to control plane
3. **`match_node_groups_to_subnets`**: Place node groups in correct subnets (suffix matching)
4. **`match_fargate_profiles_to_subnets`**: Split Fargate profiles across subnets (NEW)
5. **`link_node_groups_to_worker_nodes`**: Connect node groups to actual EC2/ASG workers

**Final Result**:
```
aws_group.eks_service_main
└── aws_eks_cluster.main (Control Plane)
    ├── aws_eks_node_group.workers~1
    ├── aws_eks_node_group.workers~2
    └── aws_eks_node_group.workers~3

VPC
├── AZ us-east-1a
│   └── Subnet private~1
│       └── aws_eks_node_group.workers~1
│           └── aws_autoscaling_group.eks_workers~1
│               └── EC2 Instances
├── AZ us-east-1b
│   └── Subnet private~2
│       └── aws_eks_node_group.workers~2
│           └── aws_autoscaling_group.eks_workers~2
│               └── EC2 Instances
└── AZ us-east-1c
    └── Subnet private~3
        └── aws_eks_node_group.workers~3
            └── aws_autoscaling_group.eks_workers~3
                └── EC2 Instances
```

---

## Key Patterns

### EKS-Specific Metadata

```
meta_data["aws_eks_cluster.main"] = {
    "name": "main",
    "version": "1.28",
    "endpoint": "https://xxxxx.eks.amazonaws.com",
    "vpc_config": {...}
}

meta_data["aws_eks_node_group.workers"] = {
    "cluster_name": "aws_eks_cluster.main",
    "desired_size": 3,
    "min_size": 1,
    "max_size": 5,
    "subnet_ids": ["subnet-xxx", "subnet-yyy", "subnet-zzz"],
    "instance_types": ["t3.medium"]
}
```

### Synthetic Group Naming

- Pattern: `aws_group.eks_service_{cluster_name}`
- Example: `aws_group.eks_service_main`
- Type: `eks_service` (for icon selection)

### Numbered Resource Propagation

When `desired_size = 3`:
- `aws_eks_node_group.workers` → `workers~1`, `workers~2`, `workers~3`
- Each instance matched to subnet by suffix
- Each instance can link to ASG or EC2 instances

---

## Helper Functions Used

```
FIND_RESOURCES_CONTAINING(graphdict, "aws_eks_cluster")
    // Find all EKS cluster resources

EXTRACT_NAME(resource)
    // "aws_eks_cluster.main" → "main"

EXTRACT_SUFFIX(resource)
    // "aws_eks_node_group.workers~2" → "2"

DEEP_COPY(metadata)
    // Create independent copy of metadata dict

GET_PARENTS(graphdict, resource)
    // Find all resources pointing to this resource
```

---

## Special Cases

### Multi-Cluster EKS

If multiple EKS clusters exist, each gets its own service group:
```
aws_group.eks_service_prod
└── aws_eks_cluster.prod

aws_group.eks_service_dev
└── aws_eks_cluster.dev
```

### Fargate Profiles

For EKS clusters using Fargate (serverless):
- Fargate profiles are handled identically to node groups (see [EKS Fargate Profiles](#eks-fargate-profiles))
- Profiles spanning multiple subnets are split into numbered instances
- Original unnumbered profile is deleted
- No EC2 instances or ASGs (leaf nodes in diagram)

### Cross-VPC EKS

If worker nodes are in a different VPC than expected:
- Keep the node groups in their actual subnets
- Control plane remains in EKS service group
- Cross-VPC connections maintained via peering/transit gateway

---

## Connections Summary

| From | To | Reason |
|------|-----|--------|
| `aws_group.eks_service` | `aws_eks_cluster` | Control plane is managed service |
| `aws_eks_cluster` | `aws_eks_node_group~N` | Control plane manages node groups (EC2) |
| `aws_eks_cluster` | `aws_eks_fargate_profile~N` | Control plane manages Fargate profiles (serverless) |
| `aws_eks_node_group~N` | `aws_autoscaling_group~N` | Node group provisions ASG |
| `aws_autoscaling_group~N` | `aws_instance` | ASG launches EC2 workers |
| `aws_subnet~N` | `aws_eks_node_group~N` | Node group deployed in subnet |
| `aws_subnet~N` | `aws_eks_fargate_profile~N` | Fargate profile deployed in subnet |
| `aws_iam_role.fargate_pod` | `aws_eks_fargate_profile~N` | IAM role for pod execution |

**Result**: Clear Kubernetes architecture showing control plane orchestrating both EC2-based node groups and serverless Fargate profiles across multiple AZs.
