# Database Resources

## RDS Database Subnet Groups

**Transformation**: DB subnet groups are moved from subnet level to VPC level.

**What Happens**:
1. **Navigation up the hierarchy**:
   - Start at the subnet containing the DB subnet group
   - Navigate: Subnet → Availability Zone → VPC

2. **Move to VPC level**:
   - Remove DB subnet group from subnet
   - Add DB subnet group to VPC

3. **Security group override**:
   - If the RDS instance has a security group, use that instead
   - Remove DB subnet group from VPC
   - Add security group to VPC instead

**Hierarchy**:
```
Before:
Subnet → DB Subnet Group → RDS Instance

After (without SG):
VPC → DB Subnet Group → RDS Instance

After (with SG):
VPC → Security Group → RDS Instance
```

**Why**: DB subnet groups span multiple subnets, so they belong at VPC level. Security groups provide better visualization of network boundaries.

**Connections**:
- **Removed**: DB subnet group from subnets
- **Added**: DB subnet group to VPC (or security group if present)

## Implementation

```
FUNCTION handle_db_subnet_groups(tfdata):

    // Step 1: Find all DB subnet groups
    db_subnet_list = FIND_RESOURCES_CONTAINING(graphdict, "aws_db_subnet_group")

    FOR EACH dbsubnet IN db_subnet_list:
        // Step 2: Find which subnets contain this DB subnet group
        db_grouping = GET_PARENTS(graphdict, dbsubnet)

        IF db_grouping exists:
            FOR EACH subnet IN db_grouping:
                IF subnet starts with "aws_subnet":
                    // Step 3: Navigate up to VPC
                    // Hierarchy: Subnet → AZ → VPC
                    az = GET_PARENTS(graphdict, subnet)[0]
                    vpc = GET_PARENTS(graphdict, az)[0]

                    // Remove from subnet
                    REMOVE dbsubnet FROM graphdict[subnet]

                    // Add to VPC
                    IF dbsubnet NOT IN graphdict[vpc]:
                        ADD dbsubnet TO graphdict[vpc]

            // Step 4: Check if RDS has security group (override)
            FOR EACH rds IN graphdict[dbsubnet]:
                rds_references = GET_PARENTS(graphdict, rds)

                FOR EACH check_sg IN rds_references:
                    IF check_sg starts with "aws_security_group":
                        // Use SG instead of DB subnet group
                        REMOVE dbsubnet FROM graphdict[vpc]
                        ADD check_sg TO graphdict[vpc]
                        BREAK

    RETURN tfdata
```
