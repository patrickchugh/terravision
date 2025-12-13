# Load Balancing

## Table of Contents

1. [Load Balancer Type Detection](#load-balancer-type-detection)
2. [Load Balancer Count Propagation](#load-balancer-count-propagation)
3. [Load Balancer Placement](#load-balancer-placement)

---

## Load Balancer Type Detection

**Transformation**: Generic `aws_lb` resources are transformed into typed load balancers.

**What Happens**:

- The `load_balancer_type` attribute is read from metadata
- A new typed node is created: `aws_alb.elb`, `aws_nlb.elb`, `aws_clb.elb`, or `aws_gwlb.elb`
- All connections are moved from the generic LB to the typed LB

**Example**:

```
Before:
aws_lb.main (type=application)

After:
aws_alb.elb
```

**Connections**:

- **Removed**: All connections from `aws_lb.main`
- **Added**: Same connections to `aws_alb.elb`
- **Added**: `aws_lb.main` now points to `aws_alb.elb` (shows transformation)

---

## Load Balancer Count Propagation

**What Happens**: Load balancers inherit the maximum count from their backend resources.

**Logic**:

- If an ALB connects to an ECS service with `desired_count=3`
- And the ALB currently has `count=1`
- The ALB's count is updated to `3`

**Why**: This ensures the diagram shows the correct number of load balancer instances needed to serve the backend across each subnet

**Count Propagation**:

- The count propagates up to the load balancer's parents (subnets, AZs)
- This ensures the entire network stack reflects the scaling

---

## Load Balancer Placement

**What Happens**: Load balancers are positioned within their subnets.

**Hierarchy**:

```
Subnet
└── Application Load Balancer
    ├── Target Group
    └── Backend Services (ECS, EC2, Lambda)
```

**Connections**:

- **Removed**: Load balancer from VPC level
- **Added**: Load balancer to subnet level
- **Maintained**: Connections to backend services

## Implementation

```
FUNCTION handle_load_balancer_variants(tfdata):

    // Step 1: Find all generic load balancers
    found_lbs = FIND_RESOURCES_CONTAINING(graphdict, "aws_lb")

    FOR EACH lb IN found_lbs:

        // Step 2: Determine LB type from metadata
        lb_type = GET_VARIANT(lb, meta_data[lb])  // Returns "aws_alb", "aws_nlb", etc.
        renamed_node = lb_type + ".elb"

        // Step 3: Initialize renamed node
        IF renamed_node NOT IN meta_data:
            meta_data[renamed_node] = DEEP_COPY(meta_data[lb])

        // Step 4: Move connections from generic LB to typed LB
        FOR EACH connection IN graphdict[lb]:
            connection_type = EXTRACT_TYPE(connection)

            IF connection_type NOT IN SHARED_SERVICES:
                // Add to typed LB
                IF renamed_node NOT IN graphdict:
                    CREATE graphdict[renamed_node] = EMPTY LIST
                ADD connection TO graphdict[renamed_node]
                REMOVE connection FROM graphdict[lb]

                // Step 5: Propagate count from backends
                IF connection has "count" or "desired_count" in metadata:
                    backend_count = connection.metadata["count"]
                    IF backend_count > renamed_node.metadata["count"]:
                        SET renamed_node.metadata["count"] = backend_count

                        // Propagate to parents (subnets, AZs)
                        parents = GET_PARENTS(graphdict, renamed_node)
                        FOR EACH parent IN parents:
                            SET parent.metadata["count"] = backend_count

        // Step 6: Update parent references to use typed LB
        parents = GET_PARENTS(graphdict, lb)
        FOR EACH parent IN parents:
            parent_type = EXTRACT_TYPE(parent)
            IF parent_type IN GROUP_NODES
               AND parent_type NOT IN SHARED_SERVICES
               AND parent_type != "aws_vpc":
                ADD renamed_node TO graphdict[parent]
                REMOVE lb FROM graphdict[parent]

        // Step 7: Link original LB to typed LB
        graphdict[lb] = [renamed_node]

    RETURN tfdata
```

**Variant Mapping**:

- `load_balancer_type: "application"` → `aws_alb.elb`
- `load_balancer_type: "network"` → `aws_nlb.elb`
- `load_balancer_type: "gateway"` → `aws_gwlb.elb`
- Default → `aws_clb.elb`
