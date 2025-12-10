# Quickstart Guide: Multi-Cloud Provider Support

**Feature**: Multi-Cloud Provider Support (Azure & GCP)
**Audience**: TerraVision users and developers
**Date**: 2025-12-07

## Overview

TerraVision now supports generating architecture diagrams for Azure and GCP Terraform projects in addition to AWS. This guide shows how to use the new multi-cloud capabilities.

---

## What's New

### Supported Cloud Providers

| Provider | Status | Resource Types | Notes |
|----------|--------|----------------|-------|
| **AWS** | ✅ Full Support | 200+ services | Existing functionality unchanged |
| **Azure** | ✅ Supported | 50+ core services | azurerm, azuread, azurestack providers |
| **GCP** | ✅ Supported | 50+ core services | google provider |
| **On-Premises** | ✅ Supported | Generic infra | Existing functionality |

### Key Features

- **Automatic Provider Detection**: TerraVision detects which cloud provider(s) your Terraform uses
- **Provider-Specific Diagrams**: Each cloud follows its own architectural conventions (Azure Resource Groups, GCP Projects, AWS VPCs)
- **Multi-Cloud Projects**: Generate separate diagrams per provider automatically
- **Backward Compatible**: Existing AWS projects work exactly as before

---

## Quick Start

### Generating Azure Diagrams

```bash
# Basic Azure diagram generation
terravision draw --source ~/my-azure-terraform

# With variable file
terravision draw --source ~/my-azure-terraform --varfile prod.tfvars

# Generate SVG format
terravision draw --source ~/my-azure-terraform --format svg

# Show diagram after generation
terravision draw --source ~/my-azure-terraform --show
```

**What TerraVision Does**:
1. Detects Azure resources (azurerm_* prefixes)
2. Loads Azure-specific configuration
3. Groups resources by Resource Group (Azure convention)
4. Applies Azure icon library and styling
5. Generates `architecture.png` with Azure diagram

**Expected Output**:
```
  TerraVision v0.9

  Detected provider: azure
  Processing 23 Azure resources...
  Generating Azure architecture diagram...

  Output file: architecture.png

  Architecture diagram generated successfully!
```

---

### Generating GCP Diagrams

```bash
# Basic GCP diagram generation
terravision draw --source ~/my-gcp-terraform

# With workspace
terravision draw --source ~/my-gcp-terraform --workspace production

# Generate PDF format
terravision draw --source ~/my-gcp-terraform --format pdf
```

**What TerraVision Does**:
1. Detects GCP resources (google_* prefixes)
2. Loads GCP-specific configuration
3. Groups resources by Project (GCP convention)
4. Applies GCP icon library and styling
5. Generates `architecture.png` with GCP diagram

**Expected Output**:
```
  TerraVision v0.9

  Detected provider: gcp
  Processing 15 GCP resources...
  Generating GCP architecture diagram...

  Output file: architecture.png

  Architecture diagram generated successfully!
```

---

### Multi-Cloud Projects

For projects with multiple cloud providers (rare but supported):

```bash
terravision draw --source ~/my-hybrid-terraform
```

**What TerraVision Does**:
1. Detects multiple providers (e.g., AWS + Azure)
2. Generates **separate diagrams per provider**
3. Names output files with provider suffix

**Expected Output**:
```
  TerraVision v0.9

  Detected 2 providers: aws, azure

  Generating AWS diagram...
  Output file: architecture-aws.png

  Generating Azure diagram...
  Output file: architecture-azure.png

  Architecture diagrams generated successfully!
```

**Output Files**:
- `architecture-aws.png` - Contains only AWS resources
- `architecture-azure.png` - Contains only Azure resources

---

## Provider-Specific Features

### Azure Architectural Conventions

**Resource Grouping**:
```
Resource Group
├── Virtual Network
│   ├── Subnet 1
│   │   └── Virtual Machine
│   └── Subnet 2
│       └── Database
└── Storage Account
```

**Supported Azure Resources** (50+ core services):
- **Compute**: Virtual Machines, VM Scale Sets, App Service, Functions, AKS
- **Storage**: Storage Accounts, Disks, File Shares
- **Networking**: VNets, Subnets, NSGs, Load Balancers, Application Gateways
- **Databases**: SQL Database, Cosmos DB, MySQL, PostgreSQL
- **Identity**: Active Directory, Key Vault
- **Management**: Resource Groups, Subscriptions, Monitor
- **Integration**: Service Bus, Event Grid, Logic Apps

---

### GCP Architectural Conventions

**Resource Grouping**:
```
Project
├── VPC (Global)
│   ├── Subnet (Regional)
│   │   └── Compute Instance
│   └── Firewall Rules
└── Cloud Storage Bucket
```

**Supported GCP Resources** (50+ core services):
- **Compute**: Compute Engine, GKE, Cloud Functions, App Engine
- **Storage**: Cloud Storage, Persistent Disks
- **Networking**: VPC, Subnets, Firewall Rules, Load Balancers
- **Databases**: Cloud SQL, Cloud Spanner, Firestore, Bigtable
- **Analytics**: BigQuery, Dataflow, Pub/Sub
- **Security**: IAM, Secret Manager, Cloud KMS
- **Operations**: Monitoring, Logging, Cloud Build

---

### AWS (Unchanged)

All existing AWS functionality works exactly as before:
```bash
terravision draw --source ~/my-aws-terraform
```

**AWS Architectural Conventions** (unchanged):
```
VPC
├── Availability Zone 1
│   ├── Subnet
│   │   └── EC2 Instance
│   └── Security Group
└── S3 Bucket (Regional)
```

---

## Advanced Usage

### Using AI Refinement with Azure/GCP

```bash
# Azure diagram with Bedrock AI refinement
terravision draw --source ~/azure-terraform --aibackend bedrock

# GCP diagram with Ollama AI refinement
terravision draw --source ~/gcp-terraform --aibackend ollama
```

**What Changes**:
- Azure diagrams use Azure-specific AI prompts (Resource Group best practices)
- GCP diagrams use GCP-specific AI prompts (Project/VPC best practices)
- AI understands provider-specific architectural patterns

---

### Annotations with Azure/GCP

Annotations work identically across all providers:

```yaml
# terravision.yml
format: 0.1
title: My Azure Architecture

connect:
  azurerm_application_gateway.frontend:
    - azurerm_virtual_machine.backend: HTTP Backend Pool

update:
  azurerm_resource_group.main:
    label: "Production Resource Group"
```

```bash
terravision draw --source ~/azure-terraform --annotate terravision.yml
```

**Annotation Support**:
- ✅ AWS resources: `aws_instance.web`
- ✅ Azure resources: `azurerm_virtual_machine.app`
- ✅ GCP resources: `google_compute_instance.vm`

---

### Exporting Graph Data (JSON)

```bash
# Export Azure project graph
terravision graphdata --source ~/azure-terraform --outfile azure-graph.json

# Export GCP project graph
terravision graphdata --source ~/gcp-terraform --outfile gcp-graph.json
```

**Output** (`azure-graph.json`):
```json
{
  "provider_detection": {
    "providers": ["azure"],
    "primary_provider": "azure",
    "resource_counts": {"azure": 23}
  },
  "graphdict": {
    "azurerm_resource_group.main": ["azurerm_virtual_network.vnet1"],
    "azurerm_virtual_network.vnet1": ["azurerm_subnet.subnet1"],
    ...
  }
}
```

---

### Using Pre-Generated JSON

```bash
# Generate graph data once
terravision graphdata --source ~/azure-terraform --outfile azure-graph.json

# Reuse for multiple diagram formats (faster)
terravision draw --source azure-graph.json --format png
terravision draw --source azure-graph.json --format svg
terravision draw --source azure-graph.json --format pdf
```

**Performance Benefit**: Skips `terraform init` and `terraform plan` (saves 30-60 seconds per run)

---

## Troubleshooting

### Provider Not Detected

**Problem**: TerraVision defaults to AWS when it should use Azure/GCP

**Symptoms**:
```
Detected provider: aws
Warning: No AWS resources found
```

**Causes**:
1. Resource names don't have standard prefixes
2. Using provider aliases
3. Custom Terraform providers

**Solutions**:
```bash
# Check your resources have correct prefixes:
# Azure: azurerm_*, azuread_*, azurestack_*
# GCP: google_*

# Verify with Terraform:
terraform state list

# Check provider blocks:
cat main.tf | grep "provider"
```

---

### Missing Icons

**Problem**: Some resources show generic icons instead of provider-specific icons

**Symptoms**:
```
Warning: No icon found for azurerm_container_registry, using generic Compute icon
```

**Explanation**: Not all Azure/GCP resources have dedicated icons yet (50-100 core services supported initially)

**Solutions**:
- Use generic icons (automatic fallback)
- Request specific icon support: https://github.com/patrickchugh/terravision/issues
- Contribute icon mappings: See contributing guide

---

### Multi-Cloud Output Confusion

**Problem**: Expected single diagram but got multiple files

**Explanation**: Your Terraform project uses multiple providers (AWS + Azure, etc.)

**Example**:
```terraform
# main.tf contains both:
provider "aws" { ... }
provider "azurerm" { ... }

resource "aws_instance" "web" { ... }
resource "azurerm_virtual_machine" "app" { ... }
```

**Solution**: This is intentional! Multi-cloud projects generate separate diagrams:
- `architecture-aws.png` - AWS resources only
- `architecture-azure.png` - Azure resources only

**To generate unified diagram** (future feature):
```bash
# Not yet supported, coming soon
terravision draw --source ~/hybrid-terraform --unified
```

---

### Performance Issues

**Problem**: Azure/GCP diagram generation slower than AWS

**Check**:
```bash
# Run with debug to see timing
terravision draw --source ~/azure-terraform --debug
```

**Typical Causes**:
1. First-time module downloads (Azure/GCP Terraform providers)
2. Large number of resources (>100)
3. Complex resource relationships

**Solutions**:
```bash
# Use simplified mode for large projects
terravision draw --source ~/azure-terraform --simplified

# Cache provider data
terravision graphdata --source ~/azure-terraform --outfile cache.json
terravision draw --source cache.json --format png
```

---

## Migration Guide

### Updating Existing Workflows

**If you have AWS-only projects**: No changes needed! Existing commands work exactly as before.

**If you're adding Azure/GCP**: Just point TerraVision at your new Terraform directory:

```bash
# Before (AWS only)
terravision draw --source ~/aws-terraform

# After (works with any provider)
terravision draw --source ~/azure-terraform
terravision draw --source ~/gcp-terraform
terravision draw --source ~/aws-terraform  # Still works!
```

---

### CI/CD Pipeline Updates

**Before** (AWS-only):
```yaml
- name: Generate Architecture Diagram
  run: terravision draw --source ./terraform --format svg
```

**After** (Multi-cloud aware):
```yaml
- name: Generate Architecture Diagrams
  run: |
    terravision draw --source ./terraform --format svg
    # Automatically handles AWS, Azure, GCP
    # Generates separate diagrams if multi-cloud project
```

**No changes required** - TerraVision detects providers automatically!

---

### Annotation File Updates

If you have existing AWS annotation files, they continue working. To support multi-cloud:

**Before** (AWS-specific):
```yaml
connect:
  aws_instance.web:
    - aws_rds_cluster.db: Database Connection
```

**After** (Multi-cloud):
```yaml
connect:
  # AWS resources
  aws_instance.web:
    - aws_rds_cluster.db: Database Connection

  # Azure resources
  azurerm_virtual_machine.app:
    - azurerm_sql_database.db: Database Connection

  # GCP resources
  google_compute_instance.vm:
    - google_sql_database_instance.db: Database Connection
```

---

## Examples

### Example 1: Simple Azure Web App

**Terraform** (`main.tf`):
```hcl
resource "azurerm_resource_group" "main" {
  name     = "my-app-rg"
  location = "East US"
}

resource "azurerm_app_service_plan" "main" {
  name                = "my-app-plan"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku {
    tier = "Standard"
    size = "S1"
  }
}

resource "azurerm_app_service" "main" {
  name                = "my-web-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  app_service_plan_id = azurerm_app_service_plan.main.id
}
```

**Generate Diagram**:
```bash
terravision draw --source . --show
```

**Result**: Diagram shows Resource Group containing App Service Plan and App Service with proper Azure styling.

---

### Example 2: GCP Kubernetes Cluster

**Terraform** (`main.tf`):
```hcl
resource "google_container_cluster" "primary" {
  name     = "my-gke-cluster"
  location = "us-central1"

  initial_node_count = 3
}

resource "google_compute_firewall" "allow-ingress" {
  name    = "allow-ingress"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}
```

**Generate Diagram**:
```bash
terravision draw --source . --format svg
```

**Result**: Diagram shows GKE cluster with firewall rules at VPC level with proper GCP styling.

---

### Example 3: Multi-Cloud Hybrid

**Terraform** (AWS + Azure):
```hcl
# AWS resources
provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}

# Azure resources
provider "azurerm" {
  features {}
}

resource "azurerm_virtual_machine" "app" {
  name                  = "app-vm"
  location              = "East US"
  resource_group_name   = azurerm_resource_group.main.name
  vm_size               = "Standard_B1s"
}
```

**Generate Diagrams**:
```bash
terravision draw --source .
```

**Result**: Generates two files:
- `architecture-aws.png` - Shows AWS EC2 instance
- `architecture-azure.png` - Shows Azure VM in Resource Group

---

## FAQ

**Q: Do I need to specify the cloud provider?**
A: No, TerraVision auto-detects providers from your Terraform resources.

**Q: Can I generate a single unified diagram for multi-cloud projects?**
A: Not in v0.9. Separate diagrams are generated per provider. Unified diagrams planned for future release.

**Q: Are all Azure/GCP resources supported?**
A: Core 50-100 services are supported initially. Unsupported resources fallback to generic icons with a warning.

**Q: Will this break my existing AWS workflows?**
A: No, AWS functionality is 100% backward compatible.

**Q: How do I request support for a specific resource?**
A: File an issue at: https://github.com/patrickchugh/terravision/issues

**Q: Can I contribute icon mappings?**
A: Yes! See CONTRIBUTING.md for adding Azure/GCP resource support.

**Q: Does AI refinement work with Azure/GCP?**
A: Yes, with provider-specific prompts understanding Azure/GCP architectural patterns.

---

## Getting Help

- **Documentation**: https://github.com/patrickchugh/terravision/blob/main/README.md
- **Issues**: https://github.com/patrickchugh/terravision/issues
- **Discussions**: https://github.com/patrickchugh/terravision/discussions

---

## Next Steps

1. **Try it out**: Generate your first Azure or GCP diagram
2. **Provide feedback**: Report any issues or missing resources
3. **Contribute**: Help expand Azure/GCP resource coverage

**Happy Diagramming!** 🎨
