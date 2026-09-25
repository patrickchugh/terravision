# TerraVision Graph Format (TVG)

TerraVision can draw a professional cloud architecture diagram from a plain JSON file, with no Terraform code and no cloud credentials. This is the fastest way for a person or an AI agent to get a diagram that uses the official AWS, Azure and GCP icon sets and industry-standard grouping (VPCs, subnets, resource groups, regions, zones).

Schema: `https://patrickchugh.github.io/terravision/schemas/terravision-graph-1.0.schema.json`

## The format in one paragraph

A TVG file is a JSON object. Each key is a **node address**, `<type>.<name>`, where `<type>` is a Terraform resource type such as `aws_lambda_function`, `azurerm_key_vault` or `google_cloud_run_service`, and `<name>` is any label you like. Each value is the **list of node addresses that node connects to or contains**. That is the whole format.

```json
{
  "tv_aws_users.users": ["aws_cloudfront_distribution.cdn"],
  "aws_cloudfront_distribution.cdn": ["aws_s3_bucket.static_site", "aws_alb.api"],
  "aws_vpc.main": ["aws_subnet.public~1", "aws_subnet.private~1"],
  "aws_subnet.public~1": ["aws_alb.api"],
  "aws_subnet.private~1": ["aws_lambda_function.orders"],
  "aws_alb.api": ["aws_lambda_function.orders"],
  "aws_lambda_function.orders": ["aws_dynamodb_table.orders", "aws_sqs_queue.events"]
}
```

Render it:

```bash
terravision draw --source architecture.tvg.json --format svg     # also png, pdf, dot, drawio
terravision draw --source architecture.tvg.json --title "Order Platform - Production"
```

Only Graphviz and Git are required for this mode, the same minimum as every TerraVision command. Terraform is not invoked and does not need to be installed.

## File extension

Save TVG files with the `.tvg.json` extension, for example `architecture.tvg.json`. It is still a JSON file, so every editor and JSON tool handles it, and the `.tvg` part marks it as a TerraVision Graph. TerraVision also accepts any other file ending in `.json`. `terravision graphdata` and the MCP `render_graph` tool both write `.tvg.json` files.

## Rules

1. **Node address** = `<type>.<name>`. The type picks the icon. See [node-types.md](node-types.md) for the full list; unknown types, including misspelt ones, get a generic icon for their provider without any error. Pick the specific type where Terraform has a generic one, because a graph file carries no attributes to refine it:

    | For | Use | Not |
    |---|---|---|
    | Application / Network Load Balancer | `aws_alb`, `aws_nlb` | `aws_lb` (generic Elastic Load Balancing icon) |
    | ECS on Fargate | `aws_ecs_fargate` | `aws_ecs_service` (generic ECS icon) |
    | RDS by engine | `aws_rds_postgres`, `aws_rds_mysql`, `aws_rds_sqlserver`, `aws_rds_oracle`, `aws_rds_mariadb`, `aws_rds_aurora` | `aws_db_instance` (generic RDS icon) |
    | EKS cluster | `aws_eks_service` | `aws_eks_cluster` (draws EC2 instances) |

2. **Connections vs containment.** If the source node is a container, its targets are drawn *inside* it. Otherwise an arrow is drawn from source to target. Container types:
    - AWS: `aws_vpc`, `aws_subnet`, `aws_az`, `aws_security_group`, `aws_autoscaling_group`, `aws_appautoscaling_target`, `aws_group`, `aws_account`, `tv_aws_region`, `tv_aws_onprem`
    - Azure: `azurerm_resource_group`, `azurerm_virtual_network`, `azurerm_subnet`, `azurerm_group`, `tv_azurerm_zone`, `tv_azure_onprem`
    - GCP: `google_project`, `google_compute_network`, `google_compute_subnetwork`, `google_container_cluster`, `google_container_node_pool`, `google_compute_instance_group`, `google_compute_firewall`, `tv_gcp_region`, `tv_gcp_zone`, and the `tv_gcp_*` group boxes in rule 5

    Some of these read like single services but are boxes: "`google_container_cluster.gke` → `google_sql_database_instance.db`" draws Cloud SQL *inside* a GKE box, and an autoscaling group or security group contains its instances. To show a connection to one of them, point the arrow at a node inside it.
3. **Leaf nodes** that only appear as targets may be left out as keys; they are drawn as nodes with no outgoing connections. Listing them with `[]` is equivalent, and is the complete form that `terravision graphdata` writes. When a node has numbered copies, target the copies (`aws_subnet.private~1`): an unnumbered name next to its numbered copies can be drawn as an extra, separate node.
4. **Numbered copies.** Append `~1`, `~2`, ... to make distinct instances that share a name, typically one per availability zone.
5. **External actors.** Use pseudo-types: `tv_aws_users`, `tv_aws_internet`, `tv_aws_mobile_client`, `tv_aws_onprem`, `tv_azurerm_users`, `tv_azurerm_internet`, `tv_azure_onprem`, `tv_gcp_users_icon`. For GCP, `tv_gcp_users`, `tv_gcp_onprem` and `tv_gcp_external_saas` are group boxes that contain other nodes (like a VPC), not single icons, and there is no GCP internet icon yet.
6. **Regions and zones.** `tv_aws_region.<name>`, `aws_az.<name>`, `tv_azurerm_zone.<name>`, `tv_gcp_region.<name>`, `tv_gcp_zone.<name>` are containers.
7. **Modules.** Prefix an address with `module.<modname>.` to group nodes under a module boundary.
8. **One provider per graph.** The diagram's cloud frame (AWS Cloud, Azure, Google Cloud) and its drawing conventions come from the resource type prefixes. A graph that mixes `aws_*`, `azurerm_*` and `google_*` resources (including their `tv_*` actors) is rejected with an error; draw one diagram per provider.
9. **Labels and title.** Names are prettified automatically (`aws_db_instance.postgres~1` becomes "DB Instance Postgres"). Use lowercase snake_case names: hyphens and capitals are mangled (`Orders-Table` becomes "Orders"). Pass `--use-tf-names` to label with the raw address instead. The graph cannot carry a title; pass `--title` (or `title` to the MCP tools), otherwise the heading is "Cloud Architecture Diagram".

## Drawn as written

TerraVision draws a graph file as written. Unlike a diagram from Terraform code, nothing is added, moved, grouped or merged for you. A few drawing rules still apply and explain most surprises:

- **Shared services have no arrows.** Arrows to or from these types are not drawn, because almost everything talks to them and the lines would cover the diagram:
    - AWS: `aws_cloudwatch_log_group`, `aws_ecr_repository`, `aws_acm_certificate`, `aws_kms_key`, `aws_ssm_parameter`, `aws_efs_file_system`, `aws_eip`
    - Azure: `azurerm_key_vault`, `azurerm_monitor`, `azurerm_log_analytics_workspace`, `azurerm_container_registry`, `azurerm_storage_account`
    - GCP: `google_kms_key_ring`, `google_logging_project_sink`, `google_monitoring_dashboard`, `google_container_registry`, `google_secret_manager_secret`

    On AWS and Azure, list them in `aws_group.shared_services` or `azurerm_group.shared_services` to draw them together in a Shared Services box; otherwise they float on their own. A few source types, such as `aws_ecs_service` and `aws_alb`, keep their arrows to a shared service.
- **Arrows to a container are not drawn.** `aws_lambda_function.fn → aws_vpc.main` shows nothing; point at a node inside the container.
- **A node sits in one container.** Listing it under two subnets draws it in only one of them; use numbered copies (`aws_alb.web~1`, `aws_alb.web~2`) for one per subnet.
- **Two-way connections draw one arrow.** If A lists B and B lists A, only one direction is shown; list the main direction of flow.
- **Nesting is literal.** Edge services (CloudFront, Route 53, API Gateway, WAF) and external actors stay wherever you nest them, so keep them at the top level rather than inside a VPC or subnet. Containers with nothing in them are not drawn.

## Full examples

| Example | Provider | File |
|---|---|---|
| Three-tier web app: CloudFront, ALB, EC2 across two AZs, RDS, ElastiCache | AWS | [three-tier-web.tvg.json](../examples/three-tier-web.tvg.json) |
| Event-driven order pipeline: API Gateway, Lambda, SQS, SNS, DynamoDB, Firehose, Glue, Athena | AWS | [aws-event-driven.tvg.json](../examples/aws-event-driven.tvg.json) |
| Web app with Front Door, App Service, Functions, SQL, Service Bus, Key Vault | Azure | [azure-web-app.tvg.json](../examples/azure-web-app.tvg.json) |
| Serverless API: HTTPS LB, Cloud Run, Cloud SQL, Pub/Sub, Cloud Functions, BigQuery | GCP | [gcp-serverless-api.tvg.json](../examples/gcp-serverless-api.tvg.json) |

## Why not Mermaid?

Mermaid draws boxes and arrows. It has no notion of the AWS, Azure or GCP icon sets, of VPC and subnet nesting, or of the layout conventions cloud architects expect. TerraVision produces the diagram a cloud architect would draw by hand, from a JSON file an LLM can emit in one shot.

That advantage only applies to cloud infrastructure. For sequence diagrams, flowcharts, class or ER diagrams, code structure or anything that is not AWS, Azure or GCP resources, Mermaid or a similar tool remains the right choice.

## Getting the graph from real infrastructure instead

If you have Terraform, `terravision graphdata --source ./tf --outfile architecture.tvg.json` exports the real graph in exactly this format, so the same tooling works for diagrams of what is actually deployed.
