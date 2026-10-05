# Example graphs

Each `.tvg.json` file is a [TerraVision Graph Format](../../docs/graph-format.md) file; the `.png` and `.svg` beside it were produced with `terravision draw --source <file>.tvg.json`. Copy the closest one and edit.

| File | Provider | What it shows |
|---|---|---|
| `three-tier-web.tvg.json` | AWS | CloudFront, S3, two availability zones each with a public subnet (ALB, NAT), a private subnet (EC2 in an Auto Scaling group, Secrets Manager interface endpoint) and a data subnet (Aurora PostgreSQL, ElastiCache), S3 gateway endpoint, IGW; a CloudWatch alarm driving the group's scaling |
| `aws-event-driven.tvg.json` | AWS | API Gateway, Lambda, SQS, SNS with DLQ, DynamoDB, Firehose, S3, Glue, Athena |
| `azure-three-tier.tvg.json` | Azure | DNS and Front Door with WAF, Static Web App, a resource group with a virtual network: Application Gateway in its own subnet, Container Apps across two zones, a NAT gateway with a public IP to the internet, Azure SQL behind a private endpoint in the data subnet; Key Vault, Log Analytics and the registry as shared services |
| `azure-web-app.tvg.json` | Azure | Front Door, App Service, Function App, Azure SQL, Service Bus, Storage, Key Vault in one resource group |
| `gcp-three-tier.tvg.json` | GCP | Global HTTPS load balancer with Cloud Armor and a Cloud Storage backend for the React site, a VPC with us-central1: a managed instance group across two zones with zonal instance groups, autoscaling on Cloud Monitoring CPU, Cloud Router and Cloud NAT; Cloud SQL and Memorystore on the network; Secret Manager, logging and Artifact Registry |
| `gcp-serverless-api.tvg.json` | GCP | HTTPS LB, Cloud Run, Cloud SQL, Secret Manager, Pub/Sub, Cloud Function, BigQuery, Cloud Storage |
| `aws-eks-karpenter.tvg.json` | AWS | EKS control plane, three availability zones each with an ALB and NAT gateway, the Karpenter controller, a NodePool of On-Demand and Spot nodes and ECR/EC2/SQS interface endpoints, Aurora PostgreSQL; S3 gateway endpoint; EventBridge and SQS for Spot interruptions; Route 53 |
| `aws-serverless-event-driven.tvg.json` | AWS | Lambdas in a VPC across two AZs, DynamoDB gateway endpoint, EventBridge/SNS/Secrets Manager interface endpoints, NAT only for the payment provider; API Gateway with Cognito, EventBridge bus to Step Functions, SQS with DLQ, Firehose to an S3 lake with Glue and Athena |
| `aws-data-lake.tvg.json` | AWS | DMS, Glue, EMR Serverless, MWAA and Redshift Serverless in a VPC across two AZs with an S3 gateway endpoint and Glue/Secrets Manager interface endpoints; Kinesis, Firehose and Transfer Family ingestion; raw and curated S3 zones, Lake Formation, Athena, QuickSight |
| `aws-multi-region.tvg.json` | AWS | Route 53 failover across two regions, each a VPC over two AZs with ALB, ECS Fargate, Aurora and a DynamoDB gateway endpoint; Aurora Global Database, DynamoDB global tables and S3 replication |
| `aws-multi-account-network.tvg.json` | AWS | Transit Gateway hub with site-to-site VPN, Network Firewall inspection VPC, central egress VPC, production, development and shared services spoke VPCs |
| `azure-hub-spoke.tvg.json` | Azure | Hub VNet with VPN gateway, Azure Firewall, Bastion and Private DNS Resolver, peered to a web spoke (Application Gateway, VM scale set across zones with an autoscale setting, SQL via private endpoint) and an internal spoke (Windows VM, PostgreSQL via private endpoint) |
| `azure-aks.tvg.json` | Azure | Front Door with WAF, Application Gateway, AKS node pools across three zones, Cosmos DB, Service Bus and Redis via private endpoints, NAT gateway |
| `gcp-gke.tvg.json` | GCP | HTTPS load balancer with Cloud Armor, regional GKE node pool across three zones, Private Service Connect endpoints for Cloud SQL and Google APIs, Pub/Sub to Cloud Run and Firestore, BigQuery, Cloud NAT |
| `gcp-data-pipeline.tvg.json` | GCP | Dataflow, Dataproc and Composer in VPC subnets with a Private Service Connect endpoint for Google APIs, Cloud SQL on a private IP with Datastream; Pub/Sub and Cloud Storage ingestion; BigQuery, Bigtable, Dataplex; Looker, Vertex AI and Cloud Run serving |

Each gallery graph has a `<name>.annotations.yml` beside it that sets its title, the CIDR ranges of its networks and subnets, labels on key arrows, and numbered flow steps with a legend; render with `terravision draw --source <name>.tvg.json --annotate <name>.annotations.yml`.

Check a file before rendering with `python skills/terravision-cloud-diagrams/scripts/validate_graph.py <file>`.

After adding or re-rendering an example, run `python scripts/make_gallery_images.py` to refresh the web-sized copies in `docs/assets/gallery/` that the docs gallery page shows, and commit them with the PNG.
