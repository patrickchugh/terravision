# Feature Specification: Complete Azure Cloud Provider Support

**Feature Branch**: `001-azure-provider`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "review docs/AZURE_RESOURCE_HANDLERS.MD and the source code in modules/resource_handlers_azure.py and determine what features are required to implement azure cloud provider support to cover most common services and patterns"

## Clarifications

### Session 2025-12-26

- Q: Which Azure services should have dedicated handler functions and icon coverage to be considered "complete Azure provider support"? → A: Top 30 Azure services matching AWS icon count (~30 handlers)
- Q: Which specific Azure services should be in the "top 30" for handler implementation priority? → A: Network (VNet, Subnet, NSG, LB, AppGW, Firewall, VPN, DNS) + Compute (VM, VMSS, AKS) + Storage (Blob, Files, Disks) + Database (SQL, Cosmos, MySQL, PostgreSQL) + PaaS (App Service, Functions, Logic Apps, API Mgmt, Service Bus, Event Hub, Redis, Front Door, CDN)
- Q: What architectural patterns should the 20 sample Azure Terraform projects cover for validation? → A: Core patterns exercising all 30 handlers (hub-spoke networks, 3-tier apps, serverless, container orchestration, hybrid cloud, data workloads, API backends, event-driven, caching, CDN/global distribution)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Azure Architecture Diagrams (Priority: P1)

Users can point TerraVision at Azure Terraform code and receive accurate architecture diagrams that reflect Azure's organizational model (Resource Groups > VNets > Subnets > Resources). The diagrams correctly show resource relationships, network topology, and security boundaries for common Azure services.

**Why this priority**: This is the core value proposition - users with Azure infrastructure need diagrams. Without this working correctly, Azure support is unusable. This delivers immediate value for the most common 80% of Azure architectures.

**Independent Test**: Can be fully tested by running TerraVision on sample Azure Terraform code containing VMs, VNets, subnets, NSGs, storage accounts, and SQL databases, then verifying the generated diagram shows correct hierarchy and connections.

**Acceptance Scenarios**:

1. **Given** Azure Terraform code with Resource Groups, VNets, and Subnets, **When** user runs terravision draw, **Then** diagram shows correct containment hierarchy (RG > VNet > Subnet)

2. **Given** Azure Terraform with VMs attached to subnets via NICs, **When** diagram is generated, **Then** VMs appear in correct subnets with NICs as implementation details

3. **Given** Azure Terraform with NSGs associated to subnets, **When** diagram is generated, **Then** NSGs appear as security boundaries wrapping subnet resources

4. **Given** Azure Terraform with shared services (Key Vault, ACR, Monitor), **When** diagram is generated, **Then** these appear in separate shared services group outside network topology

---

### User Story 2 - Azure Load Balancing and Scaling (Priority: P2)

Users can generate diagrams for Azure architectures using load balancers, application gateways, and VM scale sets. The diagrams correctly show load balancer-to-backend relationships, scale set network placement, and gateway subnet isolation.

**Why this priority**: Load balancing and auto-scaling are critical patterns for production Azure workloads. After basic networking (P1), this is the next most common architectural pattern users need documented.

**Independent Test**: Run TerraVision on Azure Terraform containing Application Gateway, Azure Load Balancer, and VMSS, verify diagram shows AG in gateway subnet connecting to backend VMs, and LB connecting to VMSS.

**Acceptance Scenarios**:

1. **Given** Azure Terraform with Application Gateway and backend VMs, **When** diagram is generated, **Then** Application Gateway appears in its dedicated subnet with connections to backend VM pool

2. **Given** Azure Terraform with VMSS and Load Balancer, **When** diagram is generated, **Then** Load Balancer shows connection to VMSS via backend pool association

3. **Given** Azure Terraform with VMSS configured with multiple instances, **When** diagram is generated, **Then** VMSS appears in correct subnet based on network profile configuration

---

### User Story 3 - Multi-Environment Azure Diagrams (Priority: P3)

Users can generate variant diagrams for different Azure environments (dev, staging, production) from the same Terraform code using different variable files. Diagrams correctly expand count/for_each resources into numbered instances with matched relationships.

**Why this priority**: Organizations deploy the same architecture pattern across multiple environments with different scales. This enables "Docs as Code" workflows where diagrams update automatically for each environment in CI/CD.

**Independent Test**: Run TerraVision with prod.tfvars (count=3) and dev.tfvars (count=1) against same Terraform code, verify diagrams show correct number of instances with proper suffix matching.

**Acceptance Scenarios**:

1. **Given** Azure Terraform with count-based resources and prod.tfvars setting count=3, **When** diagram is generated, **Then** resources appear as resource~1, resource~2, resource~3 with matched connections

2. **Given** Azure Terraform with numbered subnets and NSGs, **When** diagram is generated, **Then** subnet~1 connects to nsg~1, subnet~2 connects to nsg~2 (suffix matching)

3. **Given** Azure Terraform using workspaces for environments, **When** user specifies --workspace production, **Then** diagram reflects production-specific variable values

---

### Edge Cases

- What happens when Azure Terraform references remote modules from Git URLs? System must download modules to ~/.terravision and parse them.
- How does system handle malformed or incomplete Azure resource definitions? Should generate partial diagrams with warnings for missing metadata.
- What happens when NSG associations reference non-existent subnets/NICs? Should skip invalid associations and log warnings.
- How does system handle Azure resources without explicit Resource Group assignment? Should warn and attempt to infer from provider configuration.
- What happens when same resource appears in multiple counted instances with conflicting metadata? Should process each instance independently based on suffix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST process Azure Resource Groups as top-level organizational containers and place all Azure resources within their assigned Resource Group

- **FR-002**: System MUST process Azure Virtual Networks (VNets) as network boundary containers within Resource Groups

- **FR-003**: System MUST process Azure Subnets as network segments within VNets and position resources based on subnet placement

- **FR-004**: System MUST process Azure Network Security Groups (NSGs) as security boundaries that wrap the resources they protect

- **FR-005**: System MUST remove Azure association resources (azurerm_subnet_network_security_group_association, azurerm_network_interface_security_group_association) after creating direct connections

- **FR-006**: System MUST process Azure VM types (azurerm_virtual_machine, azurerm_linux_virtual_machine, azurerm_windows_virtual_machine) and position them in subnets based on NIC placement

- **FR-007**: System MUST process Azure Network Interfaces and link them to subnets based on ip_configuration.subnet_id references

- **FR-008**: System MUST de-emphasize NICs in diagrams by making VMs direct children of subnets while maintaining NIC connectivity information

- **FR-009**: System MUST process Azure Application Gateway and link it to gateway subnet and backend resources

- **FR-010**: System MUST process Azure Load Balancer and link it to backend resources (VMSS, VMs) via backend pool associations

- **FR-011**: System MUST process Azure VM Scale Sets and position them in subnets based on network_profile configuration

- **FR-012**: System MUST group shared Azure services (Key Vault, ACR, Monitor, Log Analytics Workspace, Application Insights) into a separate shared services section

- **FR-013**: System MUST support count/for_each expansion with suffix matching (subnet~1 → nsg~1, subnet~2 → nsg~2)

- **FR-014**: System MUST remove empty group nodes (Resource Groups, VNets, Subnets, NSGs with no children) from final diagrams

- **FR-015**: System MUST support Azure-specific auto-annotations (DNS zones → users, VPN gateway → on-premises, public IPs → internet)

- **FR-016**: System MUST match NICs to VMs based on network_interface_ids metadata references

- **FR-017**: System MUST handle flexible Azure resource ID matching (full Azure resource ID paths and short Terraform names)

- **FR-018**: System MUST expand Azure resource handlers from 13 to at least 30 handlers covering the top 30 most-used Azure services prioritized as: Network services (VNet, Subnet, NSG, Load Balancer, Application Gateway, Firewall, VPN Gateway, DNS), Compute services (VM, VMSS, AKS, ACR), Storage services (Blob Storage, File Storage, Managed Disks), Database services (SQL Database, Cosmos DB, MySQL, PostgreSQL), and PaaS services (App Service, Functions, Logic Apps, API Management, Service Bus, Event Hub, Redis Cache, Front Door, CDN)

- **FR-019**: System MUST process Azure Kubernetes Service (AKS) clusters and show connections to ACR, VNets, subnets

- **FR-020**: System MUST process Azure App Services and show relationships to App Service Plans, databases, and storage

- **FR-021**: System MUST process Azure SQL Database resources and position them appropriately with connections to compute resources

- **FR-022**: System MUST process Azure Storage Account resources and show connections from services that use them

- **FR-023**: System MUST support Azure variant icons based on resource metadata (Linux VM vs Windows VM, Basic SQL vs Standard SQL)

- **FR-024**: System MUST handle Azure-specific resource naming conventions and apply appropriate label replacements

### Key Entities

- **Azure Resource Group**: Top-level mandatory container for all Azure resources, serves as organizational boundary in diagrams

- **Azure Virtual Network (VNet)**: Regional network isolation boundary containing subnets, exists within Resource Groups

- **Azure Subnet**: Network segment within VNet, contains NICs and resources

- **Network Security Group (NSG)**: Security boundary that can be associated with subnets or NICs, rendered as container wrapping protected resources

- **Network Interface (NIC)**: Network attachment for VMs, de-emphasized in diagrams as implementation detail

- **Virtual Machine**: Compute resource positioned in subnet based on NIC placement

- **VM Scale Set (VMSS)**: Auto-scaling compute group positioned in subnet based on network profile

- **Application Gateway**: Layer 7 load balancer positioned in dedicated gateway subnet

- **Load Balancer**: Layer 4 load balancer connected to backend pools (VMSS, VMs)

- **Association Resource**: Terraform linking resource (subnet-NSG, NIC-NSG) that is removed after processing direct connections

### Assumptions

- Azure Terraform code follows Azure best practices (Resource Groups exist, VNets contain subnets, etc.)
- Azure resource IDs in references can be matched using either full Azure resource ID paths or short Terraform resource names
- Application Gateways follow Azure best practice of being deployed in dedicated gateway subnets
- Users want NICs de-emphasized in diagrams (architectural view) rather than detailed network plumbing view
- Shared services (Key Vault, ACR, Monitor) are cross-cutting concerns that benefit from being grouped separately
- Empty containers (Resource Groups with no resources) add no architectural value and should be removed
- Target is top 30 most-used Azure services prioritizing Network, Compute, Storage, Database, and PaaS categories for handler and icon coverage

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can generate accurate Azure architecture diagrams from Terraform code in under 5 minutes for projects with up to 500 resources

- **SC-002**: Generated Azure diagrams correctly show Resource Group > VNet > Subnet > Resource hierarchy in 100% of test cases

- **SC-003**: NSG security boundaries correctly wrap protected resources in 100% of association scenarios

- **SC-004**: Load balancer and Application Gateway connections to backend resources are accurately represented in 100% of test cases

- **SC-005**: Shared services appear in separate group outside network topology in 100% of diagrams containing Key Vault, ACR, or Monitor

- **SC-006**: VMs appear in correct subnets based on NIC placement in 100% of test cases

- **SC-007**: Association resources (subnet-NSG, NIC-NSG) are removed from diagrams in 100% of cases while maintaining correct connections

- **SC-008**: Empty Resource Groups, VNets, Subnets, and NSGs are removed from final diagrams in 100% of cases

- **SC-009**: Counted/for_each resources with suffixes (~1, ~2, ~3) correctly match to corresponding NSGs/subnets in 100% of cases

- **SC-010**: Azure handler count increases from 13 to at least 30 handlers with complete coverage of priority services: Network (VNet, Subnet, NSG, LB, AppGW, Firewall, VPN, DNS), Compute (VM, VMSS, AKS, ACR), Storage (Blob, Files, Disks), Database (SQL, Cosmos, MySQL, PostgreSQL), PaaS (App Service, Functions, Logic Apps, API Mgmt, Service Bus, Event Hub, Redis, Front Door, CDN)

- **SC-011**: Azure diagram generation completes without errors for at least 20 different sample Azure Terraform projects covering core architectural patterns that exercise all 30 handlers: hub-spoke network topologies, 3-tier web applications, serverless architectures, container orchestration platforms, hybrid cloud connectivity, data processing workloads, API backend services, event-driven systems, distributed caching layers, and global CDN distributions

- **SC-012**: CI/CD pipeline can generate Azure diagrams for dev/staging/prod environments using different variable files with 100% success rate
