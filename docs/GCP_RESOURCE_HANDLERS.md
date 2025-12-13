# GCP Resource Handler Specifications

This document describes how TerraVision processes Google Cloud Platform Terraform resources to create accurate architecture diagrams. Written for cloud architects to understand the resource relationship transformations.

**Status**: GCP support is currently **partial**. This specification describes both implemented features and planned transformations for full GCP support.

## Table of Contents

1. [Overview](#overview)
2. [Implementation Status](#implementation-status)
3. [Resource Hierarchy](#resource-hierarchy)
4. [Network Topology](#network-topology)
5. [Network Security](#network-security)
6. [Compute Resources](#compute-resources)
7. [Load Balancing](#load-balancing)
8. [Shared Services](#shared-services)
9. [GCP-Specific Concepts](#gcp-specific-concepts)

---

## Overview

### Processing Philosophy

TerraVision will transform GCP Terraform resources into a hierarchical architecture diagram that reflects Google Cloud's organizational model:

- **Projects** are the top-level organizational container
- **VPCs** are global networks within projects
- **Subnets** are regional subdivisions of VPCs
- **Firewall Rules** apply at the VPC level
- **Resources** are placed based on their regional/zonal location and network placement

### GCP-Specific Hierarchy

GCP uses a unique organizational model different from AWS and Azure:

```
Project (mandatory top-level container)
└── VPC (global network)
    └── Subnet (regional, can span zones)
        └── Resources (zonal or regional)
```

**Key Differences from AWS/Azure**:
- **Projects are mandatory**: Every resource belongs to a project
- **VPCs are global**: Unlike AWS VPCs which are regional
- **Subnets are regional**: They can span multiple zones within a region
- **Firewall rules are VPC-level**: Not subnet-level like AWS

---

## Implementation Status

### Currently Implemented ✅

1. **Special Cases Handling**: Disconnect services in the disconnect list
2. **Shared Services Grouping**: Groups shared GCP services (GCS, KMS, Logging, Monitoring)
3. **Random String Removal**: Removes random_string utility resources

### Planned Implementation 📋

The following features are planned for full GCP support:

1. **Project Handling**: Group resources by project
2. **VPC Handling**: Link VPCs to projects, group subnets
3. **Subnet Handling**: Link subnets to VPCs, group resources
4. **Firewall Rules**: Associate firewall rules with VPCs
5. **GKE Clusters**: Link Kubernetes clusters to subnets
6. **Instance Groups**: Handle autoscaling and managed instance groups
7. **Load Balancers**: Link backend services, health checks, forwarding rules
8. **Resource Matching**: GCP-specific suffix matching and relationship inference

---

## Resource Hierarchy

### Projects

**Status**: 📋 Planned

**Philosophy**: In GCP, all resources must belong to a Project. Projects are the fundamental organizational and billing boundary.

**Planned Transformation**:

Projects will become the top-level container in diagrams.

**What Should Happen**:
1. **Find all Projects** in the Terraform configuration
   - `google_project` resources
   - Project references in resource metadata

2. **Group resources by project**:
   - Check each resource's `project` attribute
   - Match resources to their project
   - Add resources as children of the project

3. **Create hierarchy**:
   ```
   Project "my-production-project"
   ├── VPC "vpc-prod"
   ├── Cloud Storage Bucket "bucket-prod"
   ├── Cloud SQL Instance "db-prod"
   └── (other project resources)
   ```

**Connections to Add**:
- **Project → VPC**: VPCs belong to projects
- **Project → Global Resources**: Storage, databases, managed services
- **VPC → Regional Resources**: Compute instances, GKE clusters

**Why**: Projects are the billing and organizational boundary in GCP. Showing this hierarchy clarifies ownership and cost allocation.

---

### Virtual Private Clouds (VPCs)

**Status**: 📋 Planned

**Philosophy**: GCP VPCs are **global** resources, unlike AWS VPCs which are regional. A single VPC can span all regions.

**Planned Transformation**:

VPCs will organize subnets and become the network boundary within projects.

**What Should Happen**:
1. **Find all VPCs**: `google_compute_network` resources

2. **Link VPCs to Projects**:
   - Read `project` attribute
   - Place VPC under its project

3. **Link Subnets to VPCs**:
   - Check each subnet's `network` attribute
   - Match subnets to their VPC
   - Add subnets as children of the VPC

4. **Handle auto-created subnets**:
   - GCP can auto-create subnets (auto mode VPC)
   - These should be shown if they contain resources

**Hierarchy**:
```
Project
└── VPC (global)
    ├── Subnet us-central1 (regional)
    ├── Subnet europe-west1 (regional)
    └── Subnet asia-east1 (regional)
```

**Connections to Add**:
- **Project → VPC**: Ownership relationship
- **VPC → Subnet**: Network subdivision
- **VPC → Firewall Rules**: Security policies

**Key Difference from AWS**:
- AWS VPC: Regional (one per region)
- GCP VPC: Global (spans all regions)

This affects how the diagram should be organized—GCP VPCs are higher in the hierarchy.

---

### Subnets

**Status**: 📋 Planned

**Philosophy**: GCP subnets are **regional** resources that can span multiple availability zones. This is different from AWS where subnets are zonal.

**Planned Transformation**:

Subnets will organize resources and show regional placement.

**What Should Happen**:
1. **Find all Subnets**: `google_compute_subnetwork` resources

2. **Link Subnets to VPCs**:
   - Read `network` attribute
   - Match subnet to its VPC
   - Add subnet under VPC

3. **Group Resources by Subnet**:
   - Compute instances reference subnets via `network_interface`
   - GKE clusters reference subnets
   - Find all resources in the subnet and group them

4. **Show Regional Placement**:
   - Subnet's `region` attribute should be visible
   - Resources within subnet inherit the region

**Hierarchy**:
```
VPC
└── Subnet "subnet-us-central1" (region: us-central1)
    ├── Compute Instance "vm-web-01"
    ├── Compute Instance "vm-web-02"
    └── GKE Cluster "cluster-prod"
```

**Connections to Add**:
- **VPC → Subnet**: Network structure
- **Subnet → Instances**: Resource placement
- **Subnet → GKE Clusters**: Kubernetes network placement

**Secondary IP Ranges**: Subnets can have secondary IP ranges for Kubernetes pods and services. These should be shown as subnet attributes.

---

## Network Security

### Firewall Rules

**Status**: 📋 Planned

**Philosophy**: GCP Firewall Rules apply at the **VPC level**, not the subnet level like AWS Security Groups.

**Planned Transformation**:

Firewall rules will be associated with VPCs and show which resources they affect.

**What Should Happen**:
1. **Find all Firewall Rules**: `google_compute_firewall` resources

2. **Link to VPC**:
   - Read `network` attribute
   - Associate firewall rule with its VPC

3. **Determine Target Resources**:
   - **Target Tags**: Rules can target resources with specific network tags
   - **Target Service Accounts**: Rules can target resources using specific service accounts
   - **Source/Dest Ranges**: IP-based filtering

4. **Show Firewall Associations**:
   - If a firewall rule targets specific tags, show it connected to those resources
   - If a firewall rule is VPC-wide, show it at VPC level

**Hierarchy**:
```
VPC
├── Firewall Rule "allow-http" (target tag: web)
│   └── Affects: Instances with tag "web"
├── Firewall Rule "allow-ssh" (target tag: all)
└── Subnets...
```

**Connections to Add**:
- **VPC → Firewall Rule**: Rule belongs to VPC
- **Firewall Rule → Tagged Resources**: Shows which resources the rule affects

**Key Difference from AWS**:
- AWS: Security Groups attach to instances/NICs
- GCP: Firewall Rules apply based on tags, service accounts, or IP ranges

**Target Tag Matching**: Resources with matching `tags` attribute should be visually linked to the firewall rule.

---

## Compute Resources

### Compute Instances

**Status**: 📋 Planned (partial - basic display works)

**Philosophy**: GCP Compute Instances are zonal resources within subnets.

**Planned Transformation**:

Instances should show their subnet placement and firewall associations.

**What Should Happen**:
1. **Find all Compute Instances**: `google_compute_instance` resources

2. **Link to Subnet**:
   - Read `network_interface.subnetwork` attribute
   - Match instance to its subnet
   - Place instance under the subnet

3. **Link to Firewall Rules**:
   - Read instance's `tags` attribute
   - Find firewall rules targeting those tags
   - Create visual association (instance → firewall rule)

4. **Show Zone Placement**:
   - Read `zone` attribute
   - Display zone as instance metadata

**Hierarchy**:
```
Subnet
└── Compute Instance "vm-web-01"
    ├── Zone: us-central1-a
    ├── Machine Type: n1-standard-1
    └── Tags: [web, production]
```

**Connections to Add**:
- **Subnet → Instance**: Network placement
- **Instance → Firewall Rule**: Security policy (via tags)

---

### Instance Groups

**Status**: 📋 Planned

**Philosophy**: GCP Instance Groups are collections of VM instances, used for autoscaling and load balancing.

**Types**:
- **Managed Instance Groups (MIG)**: Autoscaling, health checking
- **Unmanaged Instance Groups**: Manual instance management

**Planned Transformation**:

Instance groups should show autoscaling behavior and load balancer connections.

**What Should Happen**:
1. **Find Instance Groups**:
   - `google_compute_instance_group_manager` (MIG)
   - `google_compute_instance_group` (unmanaged)

2. **Link to Zone/Region**:
   - MIGs can be regional or zonal
   - Show appropriate placement

3. **Link to Autoscaling**:
   - `google_compute_autoscaler` resources
   - Show autoscaling policy connection

4. **Link to Load Balancers**:
   - Backend services reference instance groups
   - Create connection: Backend Service → Instance Group

**Hierarchy**:
```
Subnet
└── Managed Instance Group "mig-web"
    ├── Autoscaler (min: 2, max: 10)
    ├── Instance Template
    └── Health Check
```

**Connections to Add**:
- **Subnet → Instance Group**: Network placement
- **Autoscaler → Instance Group**: Scaling policy
- **Backend Service → Instance Group**: Load balancing

---

### Google Kubernetes Engine (GKE)

**Status**: 📋 Planned

**Philosophy**: GKE clusters are regional or zonal Kubernetes environments that span subnets.

**Planned Transformation**:

GKE clusters should show network placement, node pools, and connections to other services.

**What Should Happen**:
1. **Find GKE Clusters**: `google_container_cluster` resources

2. **Link to Subnet**:
   - Read `network` and `subnetwork` attributes
   - Place cluster under the subnet

3. **Show Node Pools**:
   - `google_container_node_pool` resources
   - Display as children of the cluster

4. **Link to Services**:
   - Container Registry (GCR) for images
   - Cloud SQL for databases
   - Cloud Storage for persistent volumes

**Hierarchy**:
```
Subnet
└── GKE Cluster "cluster-prod"
    ├── Node Pool "default-pool"
    ├── Node Pool "highmem-pool"
    └── Connections:
        ├── Container Registry
        ├── Cloud SQL
        └── Cloud Storage
```

**Connections to Add**:
- **Subnet → GKE Cluster**: Network placement
- **GKE Cluster → Node Pools**: Compute resources
- **GKE Cluster → GCR**: Container images
- **GKE Cluster → Services**: Database, storage dependencies

**Secondary IP Ranges**: GKE uses secondary IP ranges for pods and services. These should be shown as cluster attributes.

---

## Load Balancing

**Status**: 📋 Planned

**Philosophy**: GCP load balancing is complex with multiple types and components:
- **Global HTTP(S) Load Balancer**: Layer 7, global
- **Regional Network Load Balancer**: Layer 4, regional
- **Internal Load Balancer**: Private, regional

**Components**:
- **Forwarding Rules**: Entry point (IP/port)
- **Target Proxies**: HTTP(S) proxies
- **Backend Services**: Route traffic to backends
- **Backend Buckets**: Serve static content from GCS
- **Health Checks**: Monitor backend health

### Backend Services

**Status**: 📋 Planned

**Planned Transformation**:

Backend services connect forwarding rules to instance groups or backends.

**What Should Happen**:
1. **Find Backend Services**: `google_compute_backend_service` resources

2. **Link to Instance Groups**:
   - Read `backend.group` attributes
   - Connect to instance groups or NEGs (Network Endpoint Groups)

3. **Link to Health Checks**:
   - Read `health_checks` attribute
   - Show health check association

4. **Link to Forwarding Rules**:
   - Find forwarding rules referencing this backend service
   - Create connection: Forwarding Rule → Backend Service

**Hierarchy**:
```
Global HTTP(S) Load Balancer
├── Forwarding Rule
├── Target HTTP Proxy
└── Backend Service
    ├── Instance Group "mig-web"
    ├── Health Check "http-health"
    └── Cloud CDN (optional)
```

**Connections to Add**:
- **Forwarding Rule → Target Proxy → Backend Service**: Traffic flow
- **Backend Service → Instance Groups**: Backend targets
- **Backend Service → Health Check**: Monitoring

---

### Forwarding Rules

**Status**: 📋 Planned

**Planned Transformation**:

Forwarding rules are the entry points for load balancers.

**What Should Happen**:
1. **Find Forwarding Rules**: `google_compute_forwarding_rule` resources

2. **Determine Load Balancer Type**:
   - Global vs Regional
   - HTTP(S) vs TCP/UDP

3. **Link to Target**:
   - Target HTTP(S) Proxy
   - Target TCP Proxy
   - Target Pool
   - Backend Service (for internal LB)

**Connections to Add**:
- **Internet → Forwarding Rule**: Entry point
- **Forwarding Rule → Target**: Routing

---

## Shared Services

### Shared Services Grouping

**Status**: ✅ Implemented

**Philosophy**: Certain GCP services are shared/global and shouldn't clutter the network topology.

**Services Grouped**:
- **Cloud Storage (GCS)**: Object storage buckets
- **Cloud KMS**: Key management
- **Cloud Logging**: Centralized logging
- **Cloud Monitoring**: Metrics and monitoring
- **Container Registry (GCR)**: Container images
- **Secret Manager**: Secrets storage

**Transformation**:

A synthetic group node `google_group.shared_services` is created and all shared services are moved into it.

**What Happens**:
1. For each resource, check if it matches a shared service pattern
2. Create the shared services group if needed
3. Add the resource to the shared services group
4. Use consolidated names if applicable

**Hierarchy**:
```
Project
└── VPC
    └── Subnets...

Shared Services Group
├── Cloud Storage Bucket
├── Container Registry
├── Cloud KMS Key
└── Secret Manager Secret
```

**Connections**:
- **Removed**: Shared services from project/VPC hierarchy
- **Added**: Shared services to shared services group
- **Maintained**: Connections from resources to shared services

**Why**: Keeps the network diagram clean while showing cross-cutting platform services.

#### Implementation (Currently Implemented)

```
FUNCTION group_shared_services(tfdata):

    // Step 1: Find all shared services
    FOR EACH resource IN graphdict:
        // Check if resource matches any shared service pattern
        FOR EACH pattern IN SHARED_SERVICES:
            IF pattern IN resource_name:
                // Create shared services group if doesn't exist
                IF "google_group.shared_services" NOT IN graphdict:
                    CREATE graphdict["google_group.shared_services"] = empty list
                    CREATE meta_data["google_group.shared_services"] = empty dict

                // Add resource to shared services group
                IF resource NOT IN graphdict["google_group.shared_services"]:
                    ADD resource TO graphdict["google_group.shared_services"]

    // Step 2: Replace with consolidated names if applicable
    IF "google_group.shared_services" IN graphdict:
        services = COPY(graphdict["google_group.shared_services"])
        FOR EACH service IN services:
            // Check if this should be consolidated
            consolidated_name = CHECK_CONSOLIDATED(service)
            IF consolidated_name exists:
                // Replace all occurrences with consolidated name
                FOR EACH item IN graphdict["google_group.shared_services"]:
                    IF item == service:
                        REPLACE item WITH consolidated_name

    RETURN tfdata
```

**SHARED_SERVICES Constant** (from cloud_config_gcp.py):
```
SHARED_SERVICES = [
    "google_storage_bucket",     // Cloud Storage (GCS)
    "google_kms",                // Key Management Service
    "google_logging",            // Cloud Logging
    "google_monitoring",         // Cloud Monitoring
    "google_container_registry", // Container Registry (GCR)
    "google_secret_manager",     // Secret Manager
]
```

---

## GCP-Specific Concepts

### Regions and Zones

**Philosophy**: GCP has a three-tier geographic hierarchy:
- **Multi-region**: Global (e.g., US, EU, Asia)
- **Region**: Geographic area (e.g., us-central1, europe-west1)
- **Zone**: Specific data center (e.g., us-central1-a, us-central1-b)

**Planned Handling**:
- **Subnets are regional**: Show subnet's region prominently
- **Instances are zonal**: Show instance's zone as metadata
- **VPCs are global**: Span all regions

**Unlike AWS**:
- AWS has explicit AZ nodes in the diagram
- GCP should show region at subnet level, zone at instance level
- Don't create synthetic zone nodes (not architecturally significant in GCP)

---

### Network Tags

**Philosophy**: Network tags are labels applied to instances that firewall rules can target.

**Planned Handling**:
- Show tags as instance attributes
- Link instances to firewall rules via tag matching
- Visual indicator when instance is affected by a firewall rule

**Example**:
```
Instance "vm-web" [tags: web, production]
  ↓ (affected by)
Firewall Rule "allow-http" [target tags: web]
```

---

### Service Accounts

**Philosophy**: Service accounts provide identity for resources and can be targets for firewall rules.

**Planned Handling**:
- Show service account as instance attribute
- Link instances to firewall rules via service account matching
- Show IAM relationships for service accounts

---

### VPC Peering

**Status**: 📋 Planned

**Philosophy**: VPC Peering connects two VPCs to allow private communication.

**Planned Handling**:
- `google_compute_network_peering` resources
- Show as bidirectional connection between VPCs
- Display peering status and constraints

**Visual**:
```
VPC "vpc-prod" <--peering--> VPC "vpc-shared"
```

---

### Cloud Interconnect / Cloud VPN

**Status**: 📋 Planned

**Philosophy**: Connections between GCP and on-premises networks.

**Planned Handling**:
- Show VPN tunnels or interconnect attachments
- Connect to VPC
- Indicate on-premises connectivity

---

## Resource Matching

### Planned Matching Operations

1. **Firewall Rules to Instances** (via tags)
2. **Backend Services to Instance Groups**
3. **GKE Clusters to Subnets**
4. **Health Checks to Backend Services**
5. **Forwarding Rules to Backend Services**

---

## Architectural Principles

### Project as Top Container

```
Project (billing and organization boundary)
└── All resources belong to the project
```

### Global VPC Model

```
VPC (global network)
├── Subnet region-1
├── Subnet region-2
└── Subnet region-3
```

Unlike AWS where you create VPCs per region.

### Regional Subnets

```
Subnet (regional, spans zones)
├── Instance zone-a
├── Instance zone-b
└── GKE Cluster (regional)
```

### VPC-Level Firewall Rules

```
VPC
├── Firewall Rule (applies to tagged instances)
└── Subnets
    └── Instances (affected by VPC firewall)
```

Unlike AWS where security groups attach to instances.

### Flat Load Balancer Hierarchy

```
Forwarding Rule → Backend Service → Instance Group
```

Not nested within network hierarchy.

---

## GCP vs AWS/Azure Differences

### Organizational Model

**GCP**: Project → VPC (global) → Subnet (regional) → Resources
**AWS**: VPC (regional) → AZ → Subnet → Resources
**Azure**: Resource Group → VNet (regional) → Subnet → Resources

### VPC Scope

**GCP**: Global (one VPC spans all regions)
**AWS**: Regional (separate VPC per region)
**Azure**: Regional (VNet per region)

### Subnets

**GCP**: Regional (spans zones in a region)
**AWS**: Zonal (one subnet per AZ)
**Azure**: Regional (within a VNet)

### Firewall/Security

**GCP**: VPC-level firewall rules (tag-based targeting)
**AWS**: Security Groups (attach to instances/ENIs)
**Azure**: NSGs (attach to subnets or NICs)

### Load Balancing

**GCP**: Complex multi-component (forwarding rules, target proxies, backend services)
**AWS**: Simpler (ALB/NLB/CLB as single resource)
**Azure**: Application Gateway or Load Balancer (single resource)

---

## Implementation Priority

For full GCP support, implement in this order:

1. **Project Handling** ← Fundamental organizational unit
2. **VPC and Subnet Handling** ← Network topology
3. **Firewall Rules** ← Security
4. **Compute Instances** ← Basic resources
5. **GKE Clusters** ← Kubernetes support
6. **Instance Groups and Autoscaling** ← Scaling
7. **Load Balancing** ← Traffic distribution
8. **Resource Matching** ← Clean up relationships

---

## Implementation Examples

### Example: VPC Handling (Planned)

```
FUNCTION link_vpcs_and_subnets(tfdata):

    // Step 1: Find all VPCs (global networks in GCP)
    vpcs = FIND_RESOURCES_CONTAINING(graphdict, "google_compute_network")
    IF vpcs is empty:
        RETURN tfdata

    // Step 2: Find all projects
    projects = FIND_RESOURCES_CONTAINING(graphdict, "google_project")

    // Step 3: Link VPCs to their projects
    FOR EACH vpc IN vpcs:
        vpc_project = vpc.metadata["project"]

        FOR EACH project IN projects:
            project_name = EXTRACT_NAME(project)
            // Flexible matching: full name or short name
            IF project IN vpc_project OR project_name IN vpc_project:
                IF vpc NOT IN graphdict[project]:
                    ADD vpc TO graphdict[project]

    // Step 4: Find all subnets (regional resources in GCP)
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "google_compute_subnetwork")

    // Step 5: Link subnets to their VPCs
    FOR EACH subnet IN subnets:
        subnet_network = subnet.metadata["network"]

        FOR EACH vpc IN vpcs:
            vpc_name = EXTRACT_NAME(vpc)
            // Flexible matching: full name or short name
            IF vpc IN subnet_network OR vpc_name IN subnet_network:
                IF subnet NOT IN graphdict[vpc]:
                    ADD subnet TO graphdict[vpc]

    RETURN tfdata
```

**GCP Hierarchy**: `Project → VPC (global) → Subnet (regional)`

### Example: Firewall Rule Tag Matching (Planned)

```
FUNCTION link_firewall_rules(tfdata):

    // Step 1: Find all firewall rules
    firewall_rules = FIND_RESOURCES_CONTAINING(graphdict, "google_compute_firewall")

    FOR EACH rule IN firewall_rules:

        // Step 2: Link firewall rule to its VPC
        rule_network = rule.metadata["network"]
        vpcs = FIND_RESOURCES_CONTAINING(graphdict, "google_compute_network")

        FOR EACH vpc IN vpcs:
            vpc_name = EXTRACT_NAME(vpc)
            // Flexible matching
            IF vpc IN rule_network OR vpc_name IN rule_network:
                IF rule NOT IN graphdict[vpc]:
                    ADD rule TO graphdict[vpc]

        // Step 3: Find resources affected by this firewall rule (tag-based)
        target_tags = rule.metadata["target_tags"]  // e.g., ["web", "production"]

        IF target_tags is not empty:
            // Find all compute instances
            instances = FIND_RESOURCES_CONTAINING(graphdict, "google_compute_instance")

            FOR EACH instance IN instances:
                instance_tags = instance.metadata["tags"]  // e.g., ["web", "frontend"]

                // Check if any firewall target tag matches instance tags
                IF ANY tag IN target_tags ALSO IN instance_tags:
                    // Store firewall rule association in instance metadata
                    IF "firewall_rules" NOT IN instance.metadata:
                        CREATE instance.metadata["firewall_rules"] = empty list
                    ADD rule TO instance.metadata["firewall_rules"]

    RETURN tfdata
```

**GCP Tag-Based Targeting**: Firewall rules use tags to identify which resources they apply to, not direct attachments like AWS Security Groups.

### Helper Functions Reference

```
// Same core helpers as AWS and Azure

FUNCTION FIND_RESOURCES_CONTAINING(graphdict, pattern):
    // Find all resource names containing pattern
    // See AWS/Azure specs for implementation

FUNCTION GET_PARENTS(graphdict, resource):
    // Find all resources pointing to given resource
    // See AWS/Azure specs for implementation

FUNCTION STRIP_MODULE_PREFIX(resource_name):
    // Remove module prefix from resource name
    // See AWS/Azure specs for implementation

FUNCTION EXTRACT_NAME(resource):
    // Get last part after dot
    // Example: "google_compute_instance.web" → "web"

FUNCTION EXTRACT_TYPE(resource):
    // Get first part before dot
    // Example: "google_compute_instance.web" → "google_compute_instance"
```

### GCP-Specific Patterns

**Tag-Based Matching**:
```
// GCP uses tags for firewall rule targeting
target_tags = firewall_rule.metadata["target_tags"]  // ["web", "production"]
instance_tags = instance.metadata["tags"]            // ["web", "frontend"]

// Check if any tags match
IF ANY tag IN target_tags ALSO IN instance_tags:
    // Firewall rule applies to this instance
```

**Service Account Matching**:
```
// Firewall rules can target service accounts instead of tags
target_service_accounts = firewall_rule.metadata["target_service_accounts"]
instance_service_account = instance.metadata["service_account"]["email"]

IF instance_service_account IN target_service_accounts:
    // Firewall rule applies to this instance
```

**Global vs Regional/Zonal Resources**:
```
// VPCs are GLOBAL (span all regions)
IF resource is "google_compute_network":
    // No region attribute - global resource
    // One VPC can contain subnets in any region

// Subnets are REGIONAL (within one region, span zones)
IF resource is "google_compute_subnetwork":
    region = resource.metadata["region"]  // e.g., "us-central1"
    // Use region for diagram placement

// Instances are ZONAL (within one zone)
IF resource is "google_compute_instance":
    zone = resource.metadata["zone"]  // e.g., "us-central1-a"
    region = EXTRACT_REGION_FROM_ZONE(zone)  // "us-central1"
    // Use zone for detailed placement
```

---

This specification describes the **planned architectural transformation** TerraVision will apply to GCP resources to create diagrams that reflect Google Cloud's organizational model and architectural best practices.
