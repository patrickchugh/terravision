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
```

Only Graphviz and Git are required for this mode, the same minimum as every TerraVision command. Terraform is not invoked and does not need to be installed.

## File extension

Save TVG files with the `.tvg.json` extension, for example `architecture.tvg.json`. It is still a JSON file, so every editor and JSON tool handles it, and the `.tvg` part marks it as a TerraVision Graph. TerraVision also accepts any other file ending in `.json`. `terravision graphdata` and the MCP `render_graph` tool both write `.tvg.json` files.

## Rules

1. **Node address** = `<type>.<name>`. The type picks the icon. See [node-types.md](node-types.md) for the full list; unknown types get a generic icon for their provider. Pick the specific type where Terraform has a generic one: use `aws_alb` (Application Load Balancer) or `aws_nlb` (Network Load Balancer) rather than `aws_lb`, which draws the generic Elastic Load Balancing icon because a graph file carries no `load_balancer_type`.
2. **Connections vs containment.** If the source node is a container (VPC, subnet, security group, resource group, virtual network, region, zone, `aws_group`, `aws_az`), its targets are drawn *inside* it. Otherwise an arrow is drawn from source to target.
3. **Leaf nodes** that only appear as targets may be omitted as keys. Include them with `[]` if you want to be explicit.
4. **Numbered copies.** Append `~1`, `~2`, ... to make distinct instances that share a name, typically one per availability zone.
5. **External actors.** Use pseudo-types: `tv_aws_users`, `tv_aws_internet`, `tv_aws_mobile_client`, `tv_aws_onprem`, `tv_azurerm_users`, `tv_azurerm_internet`, `tv_azure_onprem`, `tv_gcp_users_icon`. For GCP, `tv_gcp_users`, `tv_gcp_onprem` and `tv_gcp_external_saas` are group boxes that contain other nodes (like a VPC), not single icons, and there is no GCP internet icon yet.
6. **Regions and zones.** `tv_aws_region.<name>`, `aws_az.<name>`, `tv_azurerm_zone.<name>`, `tv_gcp_region.<name>`, `tv_gcp_zone.<name>` are containers.
7. **Modules.** Prefix an address with `module.<modname>.` to group nodes under a module boundary.
8. **Provider.** The diagram's cloud frame (AWS Cloud, Azure, Google Cloud) is detected from the resource type prefixes. Multi-cloud graphs are allowed.
9. **Labels.** Names are prettified automatically (`aws_db_instance.postgres~1` becomes "DB Instance Postgres"). Pass `--use-tf-names` to label with the raw address instead.

## Full examples

| Example | Provider | File |
|---|---|---|
| Three-tier web app: CloudFront, ALB, EC2 across two AZs, RDS, ElastiCache | AWS | [three-tier-web.tvg.json](../examples/three-tier-web.tvg.json) |
| Event-driven order pipeline: API Gateway, Lambda, SQS, SNS, DynamoDB, Firehose, Glue, Athena | AWS | [aws-event-driven.tvg.json](../examples/aws-event-driven.tvg.json) |
| Web app with Front Door, App Service, Functions, SQL, Service Bus, Key Vault | Azure | [azure-web-app.tvg.json](../examples/azure-web-app.tvg.json) |
| Serverless API: HTTPS LB, Cloud Run, Cloud SQL, Pub/Sub, Cloud Functions, BigQuery | GCP | [gcp-serverless-api.tvg.json](../examples/gcp-serverless-api.tvg.json) |

## Why not Mermaid?

Mermaid draws boxes and arrows. It has no notion of the AWS, Azure or GCP icon sets, of VPC and subnet nesting, or of the layout conventions cloud architects expect. TerraVision produces the diagram a cloud architect would draw by hand, from a JSON file an LLM can emit in one shot.

## Getting the graph from real infrastructure instead

If you have Terraform, `terravision graphdata --source ./tf --outfile architecture.tvg.json` exports the real graph in exactly this format, so the same tooling works for diagrams of what is actually deployed.
