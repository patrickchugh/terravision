---
title: Cloud Architecture Diagram Examples (AWS, Azure, Google Cloud)
description: Twelve example cloud architecture diagrams for AWS, Azure and Google Cloud with official icons, from three-tier web apps to EKS with Karpenter, event-driven serverless, data lakes, multi-region failover and hub-and-spoke networks. Each comes with the prompt, the source file and an editable version.
hide:
  - navigation
---

# Cloud architecture diagram examples

Example architecture diagrams for AWS, Azure and Google Cloud, drawn by TerraVision with each provider's official icons. Every example comes with a prompt you can give to Claude or ChatGPT to draw something similar, and the source file that reproduces it exactly. Use them as starting points: ask your assistant to change one, or download it and edit it in draw.io.

!!! note "Your results will vary"
    A diagram drawn from a prompt depends on the AI model behind your assistant. Larger, more capable models follow the prompt more closely and add more of the detail shown here; smaller models may leave services out or group them differently. Ask for what is missing in a follow-up message, or use the source file under each example to reproduce it exactly.

| Example | Cloud |
|---|---|
| [AWS three-tier web application architecture diagram](#aws-three-tier-web-application-architecture-diagram) | AWS |
| [Amazon EKS with Karpenter architecture diagram](#amazon-eks-karpenter-architecture-diagram) | AWS |
| [AWS serverless event-driven architecture diagram](#aws-serverless-event-driven-architecture-diagram) | AWS |
| [AWS data lake architecture diagram](#aws-data-lake-architecture-diagram) | AWS |
| [AWS multi-region failover architecture diagram](#aws-multi-region-failover-architecture-diagram) | AWS |
| [AWS multi-account network architecture diagram](#aws-multi-account-network-architecture-diagram) | AWS |
| [Azure three-tier web application architecture diagram](#azure-three-tier-web-application-architecture-diagram) | Azure |
| [Azure hub-and-spoke network architecture diagram](#azure-hub-and-spoke-architecture-diagram) | Azure |
| [Azure AKS microservices architecture diagram](#azure-aks-architecture-diagram) | Azure |
| [Google Cloud three-tier web application architecture diagram](#google-cloud-three-tier-web-application-architecture-diagram) | Google Cloud |
| [Google Cloud GKE microservices architecture diagram](#google-cloud-gke-architecture-diagram) | Google Cloud |
| [Google Cloud data pipeline architecture diagram](#google-cloud-data-pipeline-architecture-diagram) | Google Cloud |

!!! tip "The quickest way to make one of these your own"
    Install TerraVision in [Claude Desktop or the ChatGPT desktop app](ai-assistants.md), paste the prompt under any example, then keep talking: *"add a WAF"*, *"make it multi-region"*, *"show how a request flows through it"*, *"write the Terraform for this"*.

## AWS three-tier web application architecture diagram { #aws-three-tier-web-application-architecture-diagram }

A classic three-tier web application on AWS. CloudFront serves a static site from S3 and routes requests to Application Load Balancers in two availability zones. Each zone has a public subnet (load balancer and NAT gateway), a private subnet (EC2 application servers) and a data subnet (RDS primary and standby), with ElastiCache for sessions and an internet gateway.

![AWS three-tier web application architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/three-tier-web.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS three-tier web app: CloudFront in front of an S3 static site and an Application Load Balancer, EC2 app servers in private subnets across two availability zones, RDS with a standby in data subnets, ElastiCache, and NAT gateways in the public subnets.

**Or reproduce it exactly** from the source file [three-tier-web.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/three-tier-web.tvg.json):

```bash
terravision draw --source three-tier-web.tvg.json --format svg      # or png, pdf
terravision draw --source three-tier-web.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/three-tier-web.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/three-tier-web.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/three-tier-web.tvg.json)

## Amazon EKS with Karpenter architecture diagram { #amazon-eks-karpenter-architecture-diagram }

A Kubernetes platform on Amazon EKS that scales its nodes with Karpenter. The VPC spans three availability zones. In each zone, a public subnet holds an Application Load Balancer and a NAT gateway, and a private subnet holds the Karpenter controller and a Karpenter NodePool of On-Demand and Spot nodes. A data subnet holds an Aurora PostgreSQL instance. The EKS control plane sits in its own AWS-managed account. An EventBridge rule sends Spot interruption warnings to an SQS queue that Karpenter reads, so it can replace nodes before they are reclaimed. Route 53 sits in front, with ECR, logs, KMS and the Karpenter IAM role as shared services.

![Amazon EKS with Karpenter architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-eks-karpenter.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an EKS cluster that uses Karpenter for node autoscaling, across three availability zones: an ALB and NAT gateway in each public subnet, the Karpenter controller and a NodePool of On-Demand and Spot nodes in each private subnet, Aurora PostgreSQL in data subnets, Route 53 in front, and the EventBridge rule and SQS queue Karpenter uses for Spot interruptions.

**Or reproduce it exactly** from the source file [aws-eks-karpenter.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-eks-karpenter.tvg.json):

```bash
terravision draw --source aws-eks-karpenter.tvg.json --format svg      # or png, pdf
terravision draw --source aws-eks-karpenter.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-eks-karpenter.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-eks-karpenter.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-eks-karpenter.tvg.json)

## AWS serverless event-driven architecture diagram { #aws-serverless-event-driven-architecture-diagram }

A serverless order platform built around an Amazon EventBridge event bus. Customers call an HTTP API on API Gateway, authenticated with Cognito. The order Lambda writes to DynamoDB and publishes an event, and a nightly EventBridge Scheduler job reconciles orders the same way. The bus fans out to four independent consumers. A Step Functions workflow reserves stock, takes payment through an external provider and books a courier. An SQS queue with a dead-letter queue drives email and SMS notifications through SES and SNS. A Lambda function updates loyalty points. Firehose streams every event to an S3 data lake, catalogued by Glue and queried with Athena.

![AWS serverless event-driven architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-serverless-event-driven.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS serverless event-driven order system: API Gateway with Cognito invoking an order Lambda that writes to DynamoDB and publishes to an EventBridge bus. The bus fans out to a Step Functions fulfilment workflow (stock, payment, courier Lambdas), an SQS notifications queue with a DLQ feeding SES and SNS, a loyalty Lambda with its own table, and Firehose to an S3 data lake with Glue and Athena. Add a nightly EventBridge Scheduler reconciliation job.

**Or reproduce it exactly** from the source file [aws-serverless-event-driven.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-serverless-event-driven.tvg.json):

```bash
terravision draw --source aws-serverless-event-driven.tvg.json --format svg      # or png, pdf
terravision draw --source aws-serverless-event-driven.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-serverless-event-driven.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-serverless-event-driven.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-serverless-event-driven.tvg.json)

## AWS data lake architecture diagram { #aws-data-lake-architecture-diagram }

A data lake and analytics platform on AWS, drawn in layers. Ingestion brings in three kinds of data: database change data capture with DMS from Aurora MySQL, clickstream events through Kinesis Data Streams and Firehose, and partner files over SFTP with Transfer Family. The lake has raw and curated S3 zones, a Glue Data Catalog and Lake Formation permissions. Processing runs Glue and EMR Serverless Spark jobs orchestrated by Amazon MWAA (Airflow). Consumption is Athena for ad hoc queries, Redshift Serverless as the warehouse, SageMaker for data science and QuickSight for dashboards.

![AWS data lake architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-data-lake.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS data lake: DMS change data capture from Aurora MySQL, Kinesis Data Streams and Firehose for clickstream, and Transfer Family SFTP for partner files, all landing in a raw S3 zone. Glue jobs write a curated zone, EMR Serverless builds aggregates, MWAA orchestrates them, a Glue crawler fills the catalogue and Lake Formation governs access. Athena, Redshift Serverless, SageMaker and QuickSight consume the curated data.

**Or reproduce it exactly** from the source file [aws-data-lake.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-data-lake.tvg.json):

```bash
terravision draw --source aws-data-lake.tvg.json --format svg      # or png, pdf
terravision draw --source aws-data-lake.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-data-lake.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-data-lake.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-data-lake.tvg.json)

## AWS multi-region failover architecture diagram { #aws-multi-region-failover-architecture-diagram }

An active-passive multi-region design on AWS. Route 53 failover routing sends users to the primary region (us-east-1) and switches to the standby region (eu-west-1) when health checks fail. Each region has a VPC across two availability zones, with Application Load Balancers in public subnets, ECS on Fargate services in application subnets and Aurora PostgreSQL in data subnets. Aurora Global Database replicates from the primary to the standby, DynamoDB global tables replicate session data, and S3 cross-region replication copies assets.

![AWS multi-region failover architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-region.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS active-passive multi-region architecture: Route 53 failover between a primary region and a standby region, each with a VPC across two availability zones, ALBs in public subnets, ECS Fargate services in app subnets and Aurora PostgreSQL in data subnets. Show Aurora Global Database replication, DynamoDB global tables and S3 cross-region replication between the regions.

**Or reproduce it exactly** from the source file [aws-multi-region.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-multi-region.tvg.json):

```bash
terravision draw --source aws-multi-region.tvg.json --format svg      # or png, pdf
terravision draw --source aws-multi-region.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-region.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-region.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-region.tvg.json)

## AWS multi-account network architecture diagram { #aws-multi-account-network-architecture-diagram }

A hub-and-spoke network for an AWS organisation. A Transit Gateway in the network account connects a site-to-site VPN from the corporate data centre to production, development and shared services VPCs, each in its own account. All traffic between VPCs, and out to the internet, passes through AWS Network Firewall in a central inspection VPC across two availability zones. A central egress VPC holds the NAT gateways and the internet gateway. The shared services VPC holds interface VPC endpoints and the corporate Active Directory.

![AWS multi-account network architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-account-network.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS multi-account network: a Transit Gateway hub in a network account with a site-to-site VPN to the data centre, an inspection VPC with Network Firewall in two availability zones, a central egress VPC with NAT gateways, and spoke VPCs for production (ECS Fargate and RDS), development (EC2) and shared services (VPC endpoints and Directory Service), each attached through its own Transit Gateway subnet.

**Or reproduce it exactly** from the source file [aws-multi-account-network.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-multi-account-network.tvg.json):

```bash
terravision draw --source aws-multi-account-network.tvg.json --format svg      # or png, pdf
terravision draw --source aws-multi-account-network.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-account-network.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-account-network.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-multi-account-network.tvg.json)

## Azure three-tier web application architecture diagram { #azure-three-tier-web-application-architecture-diagram }

A three-tier web application on Azure. DNS and Front Door with WAF sit in front of a Static Web App and an Application Gateway in its own subnet. Container Apps run across two zones inside a virtual network, Azure SQL sits behind a private endpoint in the data subnet, and a NAT gateway provides outbound access. Key Vault, Log Analytics and the container registry are drawn as shared services.

![Azure three-tier web application architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-three-tier.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an Azure three-tier web app: Front Door with WAF, a Static Web App, Application Gateway in its own subnet, Container Apps across two zones, Azure SQL behind a private endpoint, a NAT gateway, and Key Vault, Log Analytics and a container registry as shared services.

**Or reproduce it exactly** from the source file [azure-three-tier.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/azure-three-tier.tvg.json):

```bash
terravision draw --source azure-three-tier.tvg.json --format svg      # or png, pdf
terravision draw --source azure-three-tier.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-three-tier.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-three-tier.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-three-tier.tvg.json)

## Azure hub-and-spoke network architecture diagram { #azure-hub-and-spoke-architecture-diagram }

An Azure hub-and-spoke landing zone. The hub virtual network, in a connectivity resource group, holds a VPN gateway to the head office, Azure Firewall with a central firewall policy, Azure Bastion for administration and a Private DNS Resolver. Two spoke virtual networks are peered to the hub. The web workload spoke has an Application Gateway in front of a virtual machine scale set across two zones, with Azure SQL behind a private endpoint. The internal apps spoke has a Windows virtual machine and PostgreSQL Flexible Server behind a private endpoint. Outbound traffic leaves through the firewall's public IP.

![Azure hub-and-spoke network architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-hub-spoke.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an Azure hub-and-spoke landing zone: a hub VNet with a VPN gateway to the head office, Azure Firewall with a firewall policy, Bastion and a Private DNS Resolver, peered to two spokes. One spoke runs a public web app (Application Gateway, a VM scale set across two zones, Azure SQL via private endpoint). The other runs an internal Windows VM with PostgreSQL Flexible Server via private endpoint. Send outbound traffic through the firewall.

**Or reproduce it exactly** from the source file [azure-hub-spoke.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/azure-hub-spoke.tvg.json):

```bash
terravision draw --source azure-hub-spoke.tvg.json --format svg      # or png, pdf
terravision draw --source azure-hub-spoke.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-hub-spoke.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-hub-spoke.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-hub-spoke.tvg.json)

## Azure AKS microservices architecture diagram { #azure-aks-architecture-diagram }

Microservices on Azure Kubernetes Service. Front Door with a WAF policy routes customers to an Application Gateway in its own subnet, which sends traffic to AKS node pools across three availability zones. The services reach Cosmos DB, Service Bus and Azure Cache for Redis only through private endpoints in a dedicated subnet. A NAT gateway handles outbound traffic. Container Registry, Key Vault, Log Analytics and Azure Monitor are shared services.

![Azure AKS microservices architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-aks.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AKS microservices platform on Azure: Front Door with WAF in front of an Application Gateway, an AKS cluster with node pools across three zones, Cosmos DB, Service Bus and Redis reached through private endpoints in their own subnet, a NAT gateway for egress, and ACR, Key Vault, Log Analytics and Azure Monitor as shared services.

**Or reproduce it exactly** from the source file [azure-aks.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/azure-aks.tvg.json):

```bash
terravision draw --source azure-aks.tvg.json --format svg      # or png, pdf
terravision draw --source azure-aks.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-aks.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-aks.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-aks.tvg.json)

## Google Cloud three-tier web application architecture diagram { #google-cloud-three-tier-web-application-architecture-diagram }

A three-tier web application on Google Cloud. A global HTTPS load balancer with Cloud Armor serves a React site from Cloud Storage and routes API traffic to a managed instance group across two zones in us-central1, with Cloud Router and Cloud NAT. Cloud SQL and Memorystore sit on the VPC network, alongside Secret Manager, logging and Artifact Registry.

![Google Cloud three-tier web application architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-three-tier.png){ loading=lazy }

**Ask your AI assistant:**

> Draw a GCP three-tier web app: a global HTTPS load balancer with Cloud Armor, a Cloud Storage bucket for the React site, a managed instance group across two zones, Cloud SQL, Memorystore, Cloud NAT, Secret Manager and Artifact Registry.

**Or reproduce it exactly** from the source file [gcp-three-tier.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/gcp-three-tier.tvg.json):

```bash
terravision draw --source gcp-three-tier.tvg.json --format svg      # or png, pdf
terravision draw --source gcp-three-tier.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-three-tier.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-three-tier.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-three-tier.tvg.json)

## Google Cloud GKE microservices architecture diagram { #google-cloud-gke-architecture-diagram }

Microservices on Google Kubernetes Engine. A global HTTPS load balancer with Cloud Armor routes customers to a regional GKE cluster in europe-west2, whose application node pool spans three zones. The services use Cloud SQL for orders and publish order events to Pub/Sub, which triggers a Cloud Run fulfilment service backed by Firestore and streams to BigQuery. Cloud Router and Cloud NAT provide egress, alongside Artifact Registry, Secret Manager and logging.

![Google Cloud GKE microservices architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-gke.png){ loading=lazy }

**Ask your AI assistant:**

> Draw a GKE microservices platform on Google Cloud: a global HTTPS load balancer with Cloud Armor, a regional GKE cluster with a node pool across three zones, Cloud SQL, Pub/Sub triggering a Cloud Run service that writes to Firestore, a BigQuery dataset for sales events, Cloud NAT, Artifact Registry and Secret Manager.

**Or reproduce it exactly** from the source file [gcp-gke.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/gcp-gke.tvg.json):

```bash
terravision draw --source gcp-gke.tvg.json --format svg      # or png, pdf
terravision draw --source gcp-gke.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-gke.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-gke.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-gke.tvg.json)

## Google Cloud data pipeline architecture diagram { #google-cloud-data-pipeline-architecture-diagram }

A streaming and batch data platform on Google Cloud, drawn in layers. Ingestion takes clickstream events through Pub/Sub, change data capture from Cloud SQL with Datastream, and partner files into a Cloud Storage landing bucket. Processing runs a streaming Dataflow job, a batch Dataflow load and a Dataproc Serverless Spark transform, orchestrated by Cloud Composer. BigQuery holds raw and curated datasets, Bigtable holds real-time features and Dataplex governs the lake. Serving is Looker dashboards, a Vertex AI model endpoint and a recommendations API on Cloud Run.

![Google Cloud data pipeline architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-data-pipeline.png){ loading=lazy }

**Ask your AI assistant:**

> Draw a Google Cloud data platform: Pub/Sub for clickstream, Datastream CDC from Cloud SQL and a Cloud Storage landing bucket for partner files; streaming and batch Dataflow jobs and a Dataproc Serverless Spark transform orchestrated by Cloud Composer; raw and curated BigQuery datasets, Bigtable for real-time features and Dataplex governance; Looker, a Vertex AI endpoint and a Cloud Run recommendations API serving the results.

**Or reproduce it exactly** from the source file [gcp-data-pipeline.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/gcp-data-pipeline.tvg.json):

```bash
terravision draw --source gcp-data-pipeline.tvg.json --format svg      # or png, pdf
terravision draw --source gcp-data-pipeline.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-data-pipeline.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-data-pipeline.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-data-pipeline.tvg.json)

## How were these diagrams made?

Each one is a short JSON file that lists the resources and what they connect to or sit inside, rendered by TerraVision. An AI assistant writes that file for you from a plain-English description, or TerraVision derives the diagram from Terraform code. A diagram drawn from a prompt will differ in detail from the example; the source file reproduces it exactly.

## Can I get logical groups like these from Terraform?

Yes. Groups such as "Fulfilment workflow" or "Ingestion" are part of the graph. Ask your assistant for them when you describe a design. Starting from Terraform, export the graph with `terravision graphdata --source ./infra --outfile architecture.tvg.json`, add the groups to the JSON (or ask your assistant to), and draw it with `terravision draw --source architecture.tvg.json`.

## Can I edit these diagrams?

Yes. Ask your assistant to change the design in plain words, or render the source file with `--format drawio` and open it in draw.io or Lucidchart to move, restyle or annotate anything by hand. SVG output opens in any vector editor.

## Can I get the Terraform for one of these architectures?

Yes. After drawing a design with your AI assistant, ask it to write the Terraform. See [diagram to Terraform](diagram-to-terraform.md).

## Related

- [AI cloud architecture diagram generator](ai-cloud-architecture-diagram-generator.md)
- [AWS](aws-architecture-diagram-generator.md), [Azure](azure-architecture-diagram-generator.md) and [Google Cloud](gcp-architecture-diagram-generator.md) diagram generators
- [Graph Format](graph-format.md): write or edit the source files yourself
