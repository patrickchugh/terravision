# AWS Resource Handler Specifications

This summary document describes how TerraVision processes AWS Terraform resources to create accurate architecture diagrams. Written for cloud architects and DevOps engineers to understand the resource relationship transformations.

## Handler Architecture

TerraVision uses a **hybrid configuration-driven approach** for resource handlers:

- **Pure config-driven** (7 handlers): Simple operations using transformation building blocks
- **Hybrid** (3 handlers): Mix of config transformations and custom functions
- **Pure function** (6 handlers): Complex logic requiring custom Python code

See `docs/HANDLER_ARCHITECTURE.md` for complete overview.

## Table of Contents

1. [Overview](#overview)
2. [Architectural Principles](#architectural-principles)
3. [Network Topology](./network-topology.md) - VPC, Subnet, AZ handlers (pure function)
4. [Security Groups](./security-groups.md) - Security group handler (pure function)
5. [Load Balancing](./load-balancing.md) - ALB/NLB handlers (pure function)
6. [Storage & File Systems](./storage-file-systems.md) - EFS handler (pure function)
7. [Content Delivery](./content-delivery.md) - CloudFront handler (pure function)
8. [Container Orchestration](./container-orchestration.md) - ECS/EKS handlers (pure function)
9. [Shared Services](./shared-services.md) - Shared services grouping (pure config)

**Note**: Simple config-driven handlers (VPC endpoints, DB subnet groups, autoscaling groups, EKS node groups, EKS Fargate profiles, random strings) are documented in `HANDLER_CONFIG_GUIDE.md` and don't require detailed specifications.

---

## Overview

### Processing Philosophy

TerraVision transforms the flat Terraform resource graph output into a hierarchical JSON depicting an architecture diagram, that reflects AWS best practices:

- **VPCs** become top-level network containers, with an overall AWS Cloud group boundary
- **Availability Zones** are created as synthetic regional groupings within VPCs
- **Subnets** are placed within their respective AZs
- **Security Groups** wrap the resources they protect
- **Resources** are positioned based on their network placement

### Special Cases

**Disconnected Services**: Certain AWS resources have all their connections removed because they clutter diagrams without adding value:

- Random string generators
- Null resources
- Resources in the disconnect list configuration that the user specified

**Transitive Connections**: Some AWS resources connect through policies or intermediate resources. TerraVision resolves these to show direct connections:

- **SQS Queue Policies**: Resources that reference a queue policy are connected directly to the SQS queue
- **IAM Instance Profiles**: EC2 instances are connected directly to IAM roles, skipping the instance profile
- **Security Group Rules**: Resources are connected through security groups, not individual rules

---

## Architectural Principles

### Hierarchy over Flatness

TerraVision transforms Terraform's flat resource graph into AWS's architectural hierarchy:

```
VPC
└── Availability Zone
    └── Subnet
        └── Security Group
            └── EC2 Instance
```

This matches how cloud architects mentally model infrastructure.

### Containers over Associations

Resources that **protect** or **group** others become **containers** (group type nodes in the final diagram:

- Security Groups contain the resources they protect
- Load Balancers contain their backend services
- Shared Services group contains cross-cutting resources that would clutter the diagram if linked to all the services consuming them e.g. Cloudwatch or KMS

### Origins over Destinations

For CDN and caching layers, show the **flow** from edge to origin:

- CloudFront → Load Balancer
- CloudFront → S3 Bucket

### Direct over Indirect

Intermediate resources are bypassed to show direct relationships:

- Skip instance profiles, show IAM Role → EC2
- Skip queue policies, show Lambda → SQS Queue
- Skip SG rules, show Security Group → Resource

---

  
