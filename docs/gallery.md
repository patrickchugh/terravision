---
title: Cloud Architecture Diagram Examples (AWS, Azure, Google Cloud)
description: Example cloud architecture diagrams for AWS, Azure and Google Cloud with official icons: three-tier web apps, serverless and event-driven designs. Each comes with the prompt, the source file and an editable version.
hide:
  - navigation
---

# Cloud architecture diagram examples

Example architecture diagrams for AWS, Azure and Google Cloud, drawn by TerraVision with each provider's official icons. Every example comes with a prompt you can give to Claude or ChatGPT to draw something similar, and the source file that reproduces it exactly. Use them as starting points: ask your assistant to change one, or download it and edit it in draw.io.

| Example | Cloud |
|---|---|
| [AWS three-tier web application architecture diagram](#aws-three-tier-web-application-architecture-diagram) | AWS |
| [AWS event-driven serverless architecture diagram](#aws-event-driven-serverless-architecture-diagram) | AWS |
| [Azure three-tier web application architecture diagram](#azure-three-tier-web-application-architecture-diagram) | Azure |
| [Azure App Service web app architecture diagram](#azure-app-service-web-app-architecture-diagram) | Azure |
| [Google Cloud three-tier web application architecture diagram](#google-cloud-three-tier-web-application-architecture-diagram) | Google Cloud |
| [Google Cloud serverless API architecture diagram](#google-cloud-serverless-api-architecture-diagram) | Google Cloud |

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

## AWS event-driven serverless architecture diagram { #aws-event-driven-serverless-architecture-diagram }

An event-driven order pipeline on AWS. API Gateway invokes Lambda, which publishes to SQS and SNS with a dead-letter queue and stores orders in DynamoDB. Kinesis Data Firehose delivers events to S3, where Glue and Athena provide analytics.

![AWS event-driven serverless architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-event-driven.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an AWS event-driven order pipeline: API Gateway to Lambda, SQS and SNS with a dead-letter queue, DynamoDB for orders, and Firehose to S3 with Glue and Athena for analytics.

**Or reproduce it exactly** from the source file [aws-event-driven.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/aws-event-driven.tvg.json):

```bash
terravision draw --source aws-event-driven.tvg.json --format svg      # or png, pdf
terravision draw --source aws-event-driven.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-event-driven.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-event-driven.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/aws-event-driven.tvg.json)

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

## Azure App Service web app architecture diagram { #azure-app-service-web-app-architecture-diagram }

A platform-as-a-service web application on Azure in a single resource group: Front Door, App Service, a Function App, Azure SQL, Service Bus, Storage and Key Vault.

![Azure App Service web app architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-web-app.png){ loading=lazy }

**Ask your AI assistant:**

> Draw an Azure web app in one resource group: Front Door, App Service, a Function App, Azure SQL, Service Bus, a Storage account and Key Vault.

**Or reproduce it exactly** from the source file [azure-web-app.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/azure-web-app.tvg.json):

```bash
terravision draw --source azure-web-app.tvg.json --format svg      # or png, pdf
terravision draw --source azure-web-app.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-web-app.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-web-app.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/azure-web-app.tvg.json)

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

## Google Cloud serverless API architecture diagram { #google-cloud-serverless-api-architecture-diagram }

A serverless API on Google Cloud: an HTTPS load balancer in front of Cloud Run, Cloud SQL with credentials in Secret Manager, Pub/Sub feeding a Cloud Function, and BigQuery and Cloud Storage for analytics and raw events.

![Google Cloud serverless API architecture diagram](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-serverless-api.png){ loading=lazy }

**Ask your AI assistant:**

> Draw a GCP serverless API: an HTTPS load balancer in front of Cloud Run, Cloud SQL, Secret Manager, Pub/Sub triggering a Cloud Function, BigQuery and Cloud Storage.

**Or reproduce it exactly** from the source file [gcp-serverless-api.tvg.json](https://github.com/patrickchugh/terravision/blob/main/examples/graphs/gcp-serverless-api.tvg.json):

```bash
terravision draw --source gcp-serverless-api.tvg.json --format svg      # or png, pdf
terravision draw --source gcp-serverless-api.tvg.json --format drawio   # editable in draw.io or Lucidchart
```

Download: [PNG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-serverless-api.png) · [SVG](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-serverless-api.svg) · [source graph](https://raw.githubusercontent.com/patrickchugh/terravision/main/examples/graphs/gcp-serverless-api.tvg.json)

## How were these diagrams made?

Each one is a short JSON file that lists the resources and what they connect to or sit inside, rendered by TerraVision. An AI assistant writes that file for you from a plain-English description, or TerraVision derives the diagram from Terraform code. A diagram drawn from a prompt will differ in detail from the example; the source file reproduces it exactly.

## Can I edit these diagrams?

Yes. Ask your assistant to change the design in plain words, or render the source file with `--format drawio` and open it in draw.io or Lucidchart to move, restyle or annotate anything by hand. SVG output opens in any vector editor.

## Can I get the Terraform for one of these architectures?

Yes. After drawing a design with your AI assistant, ask it to write the Terraform. See [diagram to Terraform](diagram-to-terraform.md).

## Related

- [AI cloud architecture diagram generator](ai-cloud-architecture-diagram-generator.md)
- [AWS](aws-architecture-diagram-generator.md), [Azure](azure-architecture-diagram-generator.md) and [Google Cloud](gcp-architecture-diagram-generator.md) diagram generators
- [Graph Format](graph-format.md): write or edit the source files yourself
