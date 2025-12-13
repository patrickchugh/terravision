# Autoscaling

## Application Auto Scaling

**Transformation**: Auto scaling targets are linked to their subnets and inherit count from them.

**What Happens**:
1. **Find auto scaling targets and their services**:
   - Locate `aws_appautoscaling_target` resources
   - Find the services they're scaling (ECS, DynamoDB, etc.)

2. **Link to subnets**:
   - If the scaled service is in a subnet, link the autoscaling target to that subnet

3. **Propagate count**:
   - The autoscaling target inherits the subnet's count
   - The scaled service also inherits the count
   - This shows the scaling dimension

4. **Replace direct references**:
   - Subnets that reference the autoscaling target are updated to reference the scaling target itself

**Hierarchy**:
```
Subnet
└── Autoscaling Target
    └── ECS Service
```

**Connections**:
- **Added**: Subnet → Autoscaling Target
- **Removed**: Subnet → Scaled Service (direct)
- **Count**: Subnet count → Autoscaling Target count
- **Count**: Subnet count → Scaled Service count

## Implementation

```
FUNCTION handle_autoscaling(tfdata):

    // Step 1: Find autoscaling resources
    asg_resources = FIND_RESOURCES_CONTAINING(graphdict, "aws_appautoscaling_target")

    // Note: This implementation uses try/except in actual code due to complex structure
    TRY:
        // Find first autoscaling target and its connections
        IF asg_resources exists:
            scaler_links = graphdict[asg_resources[0]]

            // Step 2: Find subnets containing the scaled services
            FOR EACH check_service IN scaler_links:
                subnets = FIND_RESOURCES_CONTAINING(graphdict, "aws_subnet")

                FOR EACH subnet IN subnets:
                    IF check_service IN graphdict[subnet]:
                        // Step 3: Propagate count from subnet to ASG and service
                        subnet_count = meta_data[subnet]["count"]

                        FOR EACH asg IN asg_resources:
                            meta_data[asg]["count"] = subnet_count
                            meta_data[check_service]["count"] = subnet_count

        // Step 4: Replace service references with ASG
        FOR EACH asg IN asg_resources:
            FOR EACH connection IN graphdict[asg]:
                asg_target_parents = GET_PARENTS(graphdict, connection)
                subnets_to_change = FILTER asg_target_parents
                                    WHERE resource starts with "aws_subnet"

                FOR EACH subnet IN subnets_to_change:
                    IF asg NOT IN graphdict[subnet]:
                        ADD asg TO graphdict[subnet]
                    REMOVE connection FROM graphdict[subnet]

    CATCH any errors:
        // Silently continue if structure is unexpected

    RETURN tfdata
```
