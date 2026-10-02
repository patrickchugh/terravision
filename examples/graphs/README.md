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
| `aws-eks-karpenter.tvg.json` | AWS | EKS control plane, three availability zones each with an ALB and NAT gateway, the Karpenter controller and a NodePool of On-Demand and Spot nodes, Aurora PostgreSQL; EventBridge and SQS for Spot interruptions; Route 53 |
| `aws-serverless-event-driven.tvg.json` | AWS | API Gateway with Cognito, order Lambda, DynamoDB, EventBridge bus fanning out to a Step Functions workflow, SQS notifications with DLQ, SES and SNS, a loyalty Lambda, Firehose to an S3 lake with Glue and Athena; EventBridge Scheduler; logical groups |
| `aws-data-lake.tvg.json` | AWS | DMS, Kinesis, Firehose and Transfer Family ingestion; raw and curated S3 zones, Glue catalogue and Lake Formation; Glue, EMR Serverless and MWAA processing; Athena, Redshift Serverless, SageMaker and QuickSight; logical groups |
| `aws-multi-region.tvg.json` | AWS | Route 53 failover across two regions, each a VPC over two AZs with ALB, ECS Fargate and Aurora; Aurora Global Database, DynamoDB global tables and S3 replication |
| `aws-multi-account-network.tvg.json` | AWS | Transit Gateway hub with site-to-site VPN, Network Firewall inspection VPC, central egress VPC, production, development and shared services spoke VPCs |
| `azure-hub-spoke.tvg.json` | Azure | Hub VNet with VPN gateway, Azure Firewall, Bastion and Private DNS Resolver, peered to a web spoke (Application Gateway, VM scale set across zones, SQL via private endpoint) and an internal spoke (Windows VM, PostgreSQL via private endpoint) |
| `azure-aks.tvg.json` | Azure | Front Door with WAF, Application Gateway, AKS node pools across three zones, Cosmos DB, Service Bus and Redis via private endpoints, NAT gateway |
| `gcp-gke.tvg.json` | GCP | HTTPS load balancer with Cloud Armor, regional GKE cluster with a node pool across three zones, Cloud SQL, Pub/Sub to Cloud Run and Firestore, BigQuery, Cloud NAT |
| `gcp-data-pipeline.tvg.json` | GCP | Pub/Sub, Datastream and Cloud Storage ingestion; Dataflow, Dataproc and Composer processing; BigQuery, Bigtable and Dataplex; Looker, Vertex AI and Cloud Run serving; logical groups |

Check a file before rendering with `python skills/terravision-cloud-diagrams/scripts/validate_graph.py <file>`.
