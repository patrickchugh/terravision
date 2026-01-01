# Annotations Guide

## Overview

Annotations allow you to customize automatically generated diagrams by:
- Adding custom titles and labels
- Creating new connections
- Removing unwanted connections
- Adding external resources not in Terraform
- Modifying existing resources

---

## Quick Start

Create a `terravision.yml` file in your Terraform directory:

```yaml
format: 0.1
title: My Production Architecture

connect:
  aws_lambda_function.api:
    - aws_rds_cluster.database: Database queries

disconnect:
  aws_cloudwatch_log_group.logs:
    - aws_lambda_function.api
```

Run TerraVision:
```bash
terravision draw --source ./terraform
# Annotations are automatically loaded from terravision.yml
```

---

## Annotation File Format

### Basic Structure

```yaml
format: 0.1  # Required: annotation format version

title: "Diagram Title"  # Optional: main diagram heading

connect:
  # Add new connections

disconnect:
  # Remove connections

add:
  # Add new resources

remove:
  # Delete resources

update:
  # Modify existing resources
```

### File Location

**Option 1: Auto-load** (recommended)
- Name the file `terravision.yml`
- Place it in your Terraform source directory
- TerraVision will automatically load it

**Option 2: Specify path**
```bash
terravision draw --source ./terraform --annotate /path/to/annotations.yml
```

---

## Annotation Operations

### 1. Add Title

```yaml
title: "Production Environment - US East"
```

### 2. Connect Resources

Add new connections between resources.

**Basic connection:**
```yaml
connect:
  aws_lambda_function.api:
    - aws_rds_cluster.database
```

**Connection with label:**
```yaml
connect:
  aws_lambda_function.api:
    - aws_rds_cluster.database: "SQL queries"
    - aws_s3_bucket.uploads: "Store files"
```

**Multiple sources:**
```yaml
connect:
  aws_lambda_function.api:
    - aws_rds_cluster.database: "Read/Write"
  aws_ecs_service.web:
    - aws_rds_cluster.database: "Read only"
```

### 3. Disconnect Resources

Remove existing connections.

**Basic disconnect:**
```yaml
disconnect:
  aws_cloudwatch_log_group.logs:
    - aws_lambda_function.api
    - aws_ecs_service.web
```

**Using wildcards:**
```yaml
disconnect:
  aws_cloudwatch*.logs:  # Matches any CloudWatch log group
    - aws_ecs_service.this
    - aws_ecs_cluster.this
```

### 4. Add Resources

Add resources that don't exist in Terraform (external systems, on-prem resources).

**Basic add:**
```yaml
add:
  aws_subnet.external_subnet:
    cidr_block: "10.0.5.0/24"
    availability_zone: "us-east-1a"
```

**Add with connections:**
```yaml
add:
  external_api.payment_gateway:
    endpoint: "https://api.payment.com"
    
connect:
  aws_lambda_function.checkout:
    - external_api.payment_gateway: "Process payments"
```

### 5. Remove Resources

Delete resources from the diagram.

**Basic remove:**
```yaml
remove:
  - aws_iam_role.task_execution_role
  - aws_cloudwatch_log_group.debug_logs
```

**Using wildcards:**
```yaml
remove:
  - aws_iam_role.*  # Remove all IAM roles
```

### 6. Update Resources

Modify attributes of existing resources.

**Add edge labels:**
```yaml
update:
  aws_ecs_service.web:
    edge_labels:
      - aws_rds_cluster.database: "Database queries"
      - aws_elasticache_cluster.cache: "Session storage"
```

**Custom resource label:**
```yaml
update:
  aws_lambda_function.api:
    label: "API Gateway Handler"
```

**Update with wildcards:**
```yaml
update:
  aws_cloudfront*:
    edge_labels:
      - aws_acm_certificate.this: "SSL Certificate"
```

---

## Complete Example

```yaml
format: 0.1

# Main diagram title
title: "E-Commerce Platform - Production"

# Add connections not apparent from Terraform
connect:
  aws_lambda_function.order_processor:
    - aws_rds_cluster.orders_db: "Insert orders"
    - aws_sqs_queue.notifications: "Send notifications"
  
  aws_ecs_service.web:
    - aws_elasticache_cluster.sessions: "Session cache"

# Remove noisy connections
disconnect:
  aws_cloudwatch_log_group.*:
    - aws_lambda_function.*
    - aws_ecs_service.*

# Add external systems
add:
  external_api.payment_gateway:
    provider: "Stripe"
    endpoint: "https://api.stripe.com"
  
  external_api.shipping_service:
    provider: "FedEx"
    endpoint: "https://api.fedex.com"

# Remove internal resources from diagram
remove:
  - aws_iam_role.lambda_execution
  - aws_iam_policy.cloudwatch_logs

# Add custom labels
update:
  aws_lambda_function.order_processor:
    label: "Order Processing Engine"
    edge_labels:
      - external_api.payment_gateway: "Process payment"
      - external_api.shipping_service: "Create shipment"
  
  aws_ecs_service.web:
    label: "Web Application (3 tasks)"
    edge_labels:
      - aws_alb.main: "HTTP/HTTPS traffic"
  
  aws_cloudfront_distribution.cdn:
    edge_labels:
      - aws_s3_bucket.static_assets: "Static content"
      - aws_alb.main: "Dynamic content"
```

---

## Wildcard Patterns

Use wildcards to match multiple resources:

| Pattern | Matches | Example |
|---------|---------|---------|
| `aws_lambda*` | All Lambda functions | `aws_lambda_function.api`, `aws_lambda_function.worker` |
| `*.logs` | All resources ending with .logs | `aws_cloudwatch_log_group.api_logs` |
| `aws_ecs_*` | All ECS resources | `aws_ecs_service.web`, `aws_ecs_cluster.main` |

**Examples:**

```yaml
# Disconnect all CloudWatch logs from all Lambda functions
disconnect:
  aws_cloudwatch*.logs:
    - aws_lambda*

# Add edge labels to all CloudFront distributions
update:
  aws_cloudfront*:
    edge_labels:
      - aws_acm_certificate.this: "SSL Cert"

# Remove all IAM roles
remove:
  - aws_iam_role.*
```

---

## Resource Naming Convention

Resource names follow Terraform conventions:

```
<resource_type>.<resource_name>
```

**Examples:**
- `aws_lambda_function.api`
- `aws_rds_cluster.database`
- `aws_s3_bucket.uploads`

**Find resource names:**
```bash
# Export graph data to see all resource names
terravision graphdata --source ./terraform --outfile resources.json

# View the JSON file
cat resources.json | jq 'keys'
```

---

## Best Practices

### 1. Start Simple
Begin with just a title and a few connections:
```yaml
format: 0.1
title: "My Architecture"

connect:
  aws_lambda_function.api:
    - aws_rds_cluster.db: "Queries"
```

### 2. Use Wildcards Sparingly
Wildcards are powerful but can have unintended effects. Test incrementally.

### 3. Add Labels for Clarity
Always add labels to custom connections:
```yaml
connect:
  aws_lambda_function.api:
    - aws_rds_cluster.db: "Read/Write queries"  # Good
    # - aws_rds_cluster.db  # Less clear
```

### 4. Document External Systems
When adding external resources, include descriptive attributes:
```yaml
add:
  external_api.payment:
    provider: "Stripe"
    endpoint: "https://api.stripe.com"
    purpose: "Payment processing"
```

### 5. Version Control Annotations
Keep annotation files in Git alongside Terraform code:
```
terraform/
├── main.tf
├── variables.tf
└── terravision.yml  # Annotations
```

### 6. Test Incrementally
Add annotations gradually and regenerate diagrams to verify:
```bash
# After each change
terravision draw --source ./terraform --show
```

---

## Common Use Cases

### Add On-Premises Connectivity

```yaml
add:
  on_prem.datacenter:
    location: "Corporate HQ"
    network: "10.0.0.0/8"

connect:
  aws_vpn_gateway.main:
    - on_prem.datacenter: "Site-to-Site VPN"
```

### Show Third-Party Services

```yaml
add:
  external_api.auth0:
    service: "Auth0"
    purpose: "Authentication"

connect:
  aws_lambda_function.auth:
    - external_api.auth0: "Verify tokens"
```

### Simplify Complex Diagrams

```yaml
# Remove noisy IAM and logging resources
remove:
  - aws_iam_role.*
  - aws_iam_policy.*
  - aws_cloudwatch_log_group.*

# Remove internal connections
disconnect:
  aws_security_group.*:
    - aws_subnet.*
```

### Add Business Context

```yaml
title: "Customer Portal - Production (us-east-1)"

update:
  aws_ecs_service.web:
    label: "Customer Portal (10 tasks)"
  
  aws_rds_cluster.main:
    label: "Customer Database (Multi-AZ)"
  
  aws_elasticache_cluster.sessions:
    label: "Session Store (Redis 6.x)"
```

---

## Troubleshooting

### Annotations Not Applied

1. **Check file name**: Must be `terravision.yml` or specified with `--annotate`
2. **Check YAML syntax**: Use a YAML validator
3. **Check resource names**: Use `terravision graphdata` to see exact names
4. **Enable debug mode**: `terravision draw --debug` to see processing details

### Wildcards Not Matching

```bash
# List all resources to verify patterns
terravision graphdata --source ./terraform --show_services
```

### Connections Not Showing

1. **Verify resource names exist** in the Terraform code
2. **Check for typos** in resource names
3. **Use debug mode** to see connection processing

---

## Next Steps

- **[Usage Guide](USAGE_GUIDE.md)** - Learn more TerraVision commands
- **[CI/CD Integration](CICD_INTEGRATION.md)** - Automate with annotations
- **[Examples Repository](https://github.com/patrickchugh/terravision-examples)** - See more annotation examples
