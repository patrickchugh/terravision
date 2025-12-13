# Shared Services

## Shared Services Grouping

**Philosophy**: Certain AWS services are shared/global and shouldn't clutter the network topology.

**Services Grouped**:
- IAM roles and policies
- KMS keys
- CloudWatch logs and metrics
- SSM parameters
- Secrets Manager secrets
- SNS topics
- SQS queues (sometimes)

**Transformation**:
- A synthetic group node `aws_group.shared_services` is created
- All shared services are moved into this group
- The group appears as a separate section in the diagram

**Connections**:
- **Removed**: Shared services from VPC/subnet hierarchy
- **Added**: Shared services to shared services group
- **Maintained**: Connections from resources to shared services

**Consolidated Names**: If a shared service has a consolidated name (e.g., multiple IAM roles consolidated to `aws_iam_role`), the consolidated name is used in the group.

## Implementation

```
FUNCTION group_shared_services(tfdata):

    // Step 1: Find all shared services and group them
    FOR EACH node IN graphdict:
        // Check if node matches any shared service pattern
        FOR EACH pattern IN SHARED_SERVICES:
            IF pattern IN node:
                // Create shared services group if needed
                IF "aws_group.shared_services" NOT IN graphdict:
                    CREATE graphdict["aws_group.shared_services"] = EMPTY LIST
                    CREATE meta_data["aws_group.shared_services"] = EMPTY DICT

                // Add node to shared services group
                IF node NOT IN graphdict["aws_group.shared_services"]:
                    ADD node TO graphdict["aws_group.shared_services"]

    // Step 2: Replace with consolidated names if applicable
    IF "aws_group.shared_services" IN graphdict:
        services = COPY(graphdict["aws_group.shared_services"])

        FOR EACH service IN services:
            consolidated = CHECK_CONSOLIDATED(service)
            IF consolidated exists AND "cluster" NOT IN service:
                // Replace all occurrences with consolidated name
                graphdict["aws_group.shared_services"] =
                    MAP(lambda x: REPLACE(x, service, consolidated),
                        graphdict["aws_group.shared_services"])

    RETURN tfdata
```

**SHARED_SERVICES Patterns**:
- `aws_iam_` - IAM roles, policies, users
- `aws_kms_` - KMS keys
- `aws_cloudwatch_` - CloudWatch logs, alarms
- `aws_ssm_` - Systems Manager parameters
- `aws_secretsmanager_` - Secrets
- `aws_sns_` - SNS topics
- `aws_sqs_` - SQS queues (sometimes)
