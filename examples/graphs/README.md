# Example graphs

Each `.tvg.json` file is a [TerraVision Graph Format](../../docs/graph-format.md) file; the `.png` and `.svg` beside it were produced with `terravision draw --source <file>.tvg.json`. Copy the closest one and edit.

| File | Provider | What it shows |
|---|---|---|
| `three-tier-web.tvg.json` | AWS | CloudFront, S3, two availability zones each with a public subnet (ALB, NAT), a private subnet (EC2) and a data subnet (RDS primary / standby), ElastiCache, IGW |
| `aws-event-driven.tvg.json` | AWS | API Gateway, Lambda, SQS, SNS with DLQ, DynamoDB, Firehose, S3, Glue, Athena |
| `azure-web-app.tvg.json` | Azure | Front Door, App Service, Function App, Azure SQL, Service Bus, Storage, Key Vault in one resource group |
| `gcp-serverless-api.tvg.json` | GCP | HTTPS LB, Cloud Run, Cloud SQL, Secret Manager, Pub/Sub, Cloud Function, BigQuery, Cloud Storage |

Check a file before rendering with `python skills/terravision-cloud-diagrams/scripts/validate_graph.py <file>`.
