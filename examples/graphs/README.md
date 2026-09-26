# Example graphs

Each `.tvg.json` file is a [TerraVision Graph Format](../../docs/graph-format.md) file; the `.png` and `.svg` beside it were produced with `terravision draw --source <file>.tvg.json`. Copy the closest one and edit.

| File | Provider | What it shows |
|---|---|---|
| `three-tier-web.tvg.json` | AWS | CloudFront, S3, two availability zones each with a public subnet (ALB, NAT), a private subnet (EC2) and a data subnet (RDS primary / standby), ElastiCache, IGW |
| `aws-event-driven.tvg.json` | AWS | API Gateway, Lambda, SQS, SNS with DLQ, DynamoDB, Firehose, S3, Glue, Athena |
| `azure-three-tier.tvg.json` | Azure | DNS and Front Door with WAF, Static Web App, a resource group with a virtual network: Application Gateway in its own subnet, Container Apps across two zones, a NAT gateway with a public IP to the internet, Azure SQL behind a private endpoint in the data subnet; Key Vault, Log Analytics and the registry as shared services |
| `azure-web-app.tvg.json` | Azure | Front Door, App Service, Function App, Azure SQL, Service Bus, Storage, Key Vault in one resource group |
| `gcp-three-tier.tvg.json` | GCP | Global HTTPS load balancer with Cloud Armor and a Cloud Storage backend for the React site, a VPC with us-central1: a managed instance group across two zones, Cloud Router and Cloud NAT; Cloud SQL and Memorystore on the network; Secret Manager, logging and Artifact Registry |
| `gcp-serverless-api.tvg.json` | GCP | HTTPS LB, Cloud Run, Cloud SQL, Secret Manager, Pub/Sub, Cloud Function, BigQuery, Cloud Storage |

Check a file before rendering with `python skills/terravision-cloud-diagrams/scripts/validate_graph.py <file>`.
