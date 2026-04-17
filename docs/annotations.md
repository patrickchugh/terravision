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
format: 0.2
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
terravision draw --source ./path-to-your-terraform
# Annotations are automatically loaded from terravision.yml
```

---

## Two-File Model

TerraVision supports two annotation files that are automatically discovered and merged:

| File | Purpose | Created By |
|------|---------|------------|
| `terravision.yml` | User-authored annotations | You (manually) |
| `terravision.ai.yml` | AI-generated annotations | TerraVision with `--ai-annotate <backend>` |

Both files use the same YAML schema. When both are present, they are merged according to precedence rules (see below). You never need to edit `terravision.ai.yml` by hand -- it is regenerated on each AI-enabled run.

### Precedence Rules

When annotations come from multiple sources, the highest-precedence source wins on conflicts:

```
Precedence (highest to lowest):
1. --annotate <path>    (CLI flag)
2. terravision.yml      (user file)
3. terravision.ai.yml   (AI-generated file)
```

**Merge behaviour by section:**

| Section | Merge Rule |
|---------|------------|
| `title` | Scalar: highest-precedence source wins |
| `add` / `remove` | List union (deduplicated) |
| `connect` / `disconnect` | Dict merge by resource key, then list merge per resource; label conflicts use highest-precedence value |
| `update` | Dict merge by resource key; per-attribute highest-precedence wins |
| `flows` | Dict merge by flow name; if the same flow name appears in both files, the user file entirely replaces the AI version |
| `remove` vs `add` | `remove` wins: a resource listed in `remove` by any source is removed even if another source adds it |

**Example:** If the AI file sets `title: "Serverless API"` and your user file sets `title: "Payment Service"`, the diagram will use "Payment Service" because the user file has higher precedence.

---

## Annotation File Format

### Basic Structure

```yaml
format: 0.2  # Required: annotation format version (0.1 or 0.2)

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

flows:
  # Numbered flow sequences (new in format 0.2)
```

### Format Versions

- **0.1**: Original format supporting `title`, `connect`, `disconnect`, `add`, `remove`, `update`. Still fully supported.
- **0.2**: Adds the `flows` section for numbered flow badges and the `generated_by` metadata block (used in AI-generated files). All 0.1 files parse unchanged.

### File Location

**Option 1: Auto-load** (recommended)
- Name the file `terravision.yml`
- Place it in your Terraform source directory
- TerraVision will automatically load it

**Option 2: Specify path**
```bash
terravision draw --source ./path-to-your-terraform --annotate /path/to/annotations.yml
```

**Option 3: AI-generated** (automatic)
- Run with `--ai-annotate <backend>` and TerraVision writes `terravision.ai.yml` in the source directory
- This file is automatically discovered and merged with any existing `terravision.yml`

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

### 7. Define Flows (Format 0.2)

Flows define numbered step sequences that render as badges on diagram nodes/edges and a legend table. Each flow has a name, description, and ordered list of steps.

**Basic flow:**
```yaml
flows:
  auth-flow:
    description: "User Authentication"
    steps:
      - resource: aws_cloudfront_distribution.cdn
        xlabel: "Login request"
        detail: "User submits credentials via CloudFront"
      - resource: aws_lambda_function.auth
        xlabel: "Validate"
        detail: "Lambda validates credentials against Cognito"
      - resource: aws_dynamodb_table.sessions
        xlabel: "Create session"
        detail: "Session token stored in DynamoDB"
```

**Flow step fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `resource` | Yes | A graphdict node name (e.g., `aws_lambda_function.api`) or an edge in `source -> target` format |
| `xlabel` | Yes | Short label displayed in the badge near the node/edge |
| `detail` | Yes | Full description shown in the legend |

**Step numbering** is automatic and continuous: if flow A has 4 steps and flow B has 3 steps, the badges are numbered 1-4 and 5-7 respectively. When a node appears in multiple flows, its badge shows all step numbers (e.g., "1, 5").

**Edge-level flow steps** target a connection instead of a node:
```yaml
flows:
  data-flow:
    description: "Data Ingestion"
    steps:
      - resource: "aws_lambda_function.api -> aws_dynamodb_table.orders"
        xlabel: "Write order"
        detail: "Lambda writes order record to DynamoDB"
```

**Multiple flows example:**
```yaml
flows:
  auth-flow:
    description: "Authentication Flow"
    steps:
      - resource: aws_api_gateway_rest_api.main
        xlabel: "Login"
        detail: "User sends login request"
      - resource: aws_lambda_function.auth
        xlabel: "Verify"
        detail: "Verify credentials with Cognito"
      - resource: aws_dynamodb_table.sessions
        xlabel: "Store token"
        detail: "Persist session token"
      - resource: aws_api_gateway_rest_api.main
        xlabel: "Return JWT"
        detail: "Return signed JWT to client"

  order-flow:
    description: "Order Processing"
    steps:
      - resource: aws_api_gateway_rest_api.main
        xlabel: "Submit order"
        detail: "Client submits order via API"
      - resource: aws_lambda_function.order_processor
        xlabel: "Process"
        detail: "Validate and process order"
      - resource: aws_sqs_queue.notifications
        xlabel: "Notify"
        detail: "Queue notification for fulfilment"
```

In this example, the auth-flow badges are numbered 1-4 and the order-flow badges are numbered 5-7. The `aws_api_gateway_rest_api.main` node appears in both flows so its badge shows "1, 4, 5".

### The `generated_by` Metadata Block

The `generated_by` block appears only in AI-generated files (`terravision.ai.yml`). It is informational and is never applied to the graph.

```yaml
generated_by:
  backend: ollama          # AI backend used ("ollama" or "bedrock")
  model: llama3:latest     # Model identifier
  timestamp: "2026-04-12T10:30:00Z"  # ISO 8601 UTC timestamp
```

This block is preserved during merging but has no effect on the diagram. It exists so you can audit which model and backend produced the AI annotations.

---

## Complete Example

```yaml
format: 0.2

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

# Define numbered flow sequences (format 0.2)
flows:
  checkout-flow:
    description: "Checkout Flow"
    steps:
      - resource: aws_cloudfront_distribution.cdn
        xlabel: "Browse"
        detail: "Customer browses product catalogue"
      - resource: aws_ecs_service.web
        xlabel: "Add to cart"
        detail: "Items added to shopping cart"
      - resource: aws_lambda_function.order_processor
        xlabel: "Place order"
        detail: "Order submitted for processing"
      - resource: "aws_lambda_function.order_processor -> aws_sqs_queue.notifications"
        xlabel: "Queue"
        detail: "Fulfilment notification queued"
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
terravision graphdata --source ./path-to-your-terraform --outfile resources.json

# View the JSON file
cat resources.json | jq 'keys'
```

### Helper Nodes (`tv_*`) — External Actors and Icons

In addition to your real Terraform resources, TerraVision ships with **helper icons** you can drop into any diagram to represent things that aren't in your `.tf` code — users, the public internet, on-prem datacenters, mobile clients, external SaaS, etc. They live in a reserved `tv_*` namespace and are referenced in annotations just like any other resource.

Some helpers are added **automatically** via built-in auto-annotations — for example, a `tv_aws_users.users` icon is wired to any `aws_route53_record` or `aws_cloudfront_distribution` in your plan, so a "users" actor appears on the diagram without you doing anything. Others you add **manually** in your `terravision.yml` when you want to show an external interaction.

**Common AWS helpers** (equivalent `tv_azure_*` and `tv_gcp_*` exist):

| Helper                            | Represents                                  |
| --------------------------------- | ------------------------------------------- |
| `tv_aws_users.<name>`             | External end users / clients                |
| `tv_aws_internet.<name>`          | The public internet                         |
| `tv_aws_onprem.<name>`            | On-premises datacenter                      |
| `tv_aws_mobile_client.<name>`     | Mobile app / device                         |
| `tv_aws_device.<name>`            | IoT / physical device                       |
| `tv_aws_cgw.<name>`               | Customer gateway (VPN peer)                 |

**Example 1 — add an explicit "corporate users" actor hitting an ALB:**

```yaml
format: 0.2
connect:
  tv_aws_users.corporate:
    - aws_lb.app: "HTTPS 443"
```

**Example 2 — an on-prem datacenter flowing into a Transit Gateway via VPN:**

```yaml
format: 0.2
connect:
  tv_aws_onprem.corporate_datacenter:
    - aws_cgw.vpn: "IPsec tunnel"
    - aws_ec2_transit_gateway.tgw: "BGP peering"
```

**Example 3 — mobile app calling API Gateway + Cognito:**

```yaml
format: 0.2
connect:
  tv_aws_mobile_client.ios_app:
    - aws_cognito_user_pool.auth: "Sign in"
    - aws_api_gateway_rest_api.backend: "Authenticated requests"
```

!!! tip "Naming the instance"
    The part after the dot (`corporate`, `corporate_datacenter`, `ios_app` above) is arbitrary — choose whatever reads well on the diagram. You can have multiple instances of the same helper (e.g. `tv_aws_users.employees` and `tv_aws_users.customers`) to distinguish different actor groups.

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
├── terravision.yml      # User annotations (commit this)
└── terravision.ai.yml   # AI annotations (optional, regenerated)
```

Consider adding `terravision.ai.yml` to `.gitignore` if you regenerate it on every run, or commit it if you want to track AI suggestions over time.

### 6. Test Incrementally
Add annotations gradually and regenerate diagrams to verify:
```bash
# After each change
terravision draw --source ./path-to-your-terraform --show
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
terravision graphdata --source ./path-to-your-terraform --show_services
```

### Connections Not Showing

1. **Verify resource names exist** in the Terraform code
2. **Check for typos** in resource names
3. **Use debug mode** to see connection processing

---

## Next Steps

- **[Usage Guide](usage-guide.md)** - Learn more TerraVision commands
- **[CI/CD Integration](cicd-integration.md)** - Automate with annotations
- **[Examples Repository](https://github.com/patrickchugh/terravision-examples)** - See more annotation examples
