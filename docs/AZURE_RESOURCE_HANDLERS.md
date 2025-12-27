# Azure Resource Handler Specifications

This document describes how TerraVision processes Azure Terraform resources to create accurate architecture diagrams. Written for cloud architects to understand the resource relationship transformations.

## Table of Contents

1. [Overview](#overview)
2. [Resource Hierarchy](#resource-hierarchy)
3. [Network Topology](#network-topology)
4. [Network Security](#network-security)
5. [Compute Resources](#compute-resources)
6. [Load Balancing](#load-balancing)
7. [Shared Services](#shared-services)
8. [Resource Matching](#resource-matching)

---

## Overview

### Handler Architecture

TerraVision uses a **hybrid configuration-driven approach** for implementing Azure resource handlers. Following the project constitution (CO-006 through CO-012), all handlers MUST prioritize declarative configuration over imperative Python code.

**Three Handler Types** (in order of preference):

1. **Pure Config-Driven** ✅ PREFERRED
   - Use only transformation building blocks from `resource_transformers.py`
   - Defined entirely in `modules/config/resource_handler_configs_azure.py`
   - 70% code reduction, easiest to maintain
   - **Example**: VPC endpoints, DB subnet groups, autoscaling groups

2. **Hybrid** ⚠️ USE WHEN NEEDED
   - Use config transformations + custom Python function
   - Generic operations handled by transformers, unique logic in custom function
   - Best of both worlds
   - **Example**: Subnet (metadata prep + insert_intermediate_node transformer)

3. **Pure Function** ❌ LAST RESORT
   - Use only when logic is too complex for declarative approach
   - Requires documentation explaining why config-driven was insufficient
   - **Example**: Security groups (complex reverse relationships)

**Implementation Workflow**:
1. Attempt Pure Config-Driven using existing transformers
2. If pattern is reusable, create new generic transformer
3. If unique logic needed, use Hybrid approach
4. Only use Pure Function for complex conditional logic that cannot be expressed declaratively

See `docs/HANDLER_CONFIG_GUIDE.md` for comprehensive implementation guide.

### Processing Philosophy

TerraVision transforms Azure Terraform resources into a hierarchical architecture diagram that reflects Azure's organizational model:

- **Resource Groups** become top-level organizational containers
- **Virtual Networks (VNets)** are placed within Resource Groups
- **Subnets** are placed within their VNets
- **Network Security Groups (NSGs)** wrap the resources they protect
- **Resources** are positioned based on their network and security placement

### Azure-Specific Hierarchy

Azure uses a different organizational model than AWS:

```
Resource Group (mandatory top-level container)
└── Virtual Network (network boundary)
    └── Subnet (network segment)
        └── Network Security Group (security boundary)
            └── Resources (VMs, NICs, etc.)
```

### Special Cases

**Association Resources**: Azure uses explicit association resources to link NSGs to subnets or NICs. These are intermediate resources that shouldn't appear in diagrams:
- `azurerm_subnet_network_security_group_association`
- `azurerm_network_interface_security_group_association`

TerraVision removes these and creates direct connections.

**Disconnected Services**: Resources in the disconnect list have all connections removed to keep diagrams clean.

---

## Resource Hierarchy

### Resource Groups

**Philosophy**: In Azure, all resources must belong to a Resource Group. Resource Groups are logical containers for organizing related resources.

**Transformation**: Resource Groups become the top-level boundary in diagrams.

**What Happens**:
1. **Find all Resource Groups** in the Terraform configuration

2. **Link resources to their Resource Group**:
   - Check each resource's `resource_group_name` attribute
   - Match the resource to its Resource Group
   - Add the resource as a child of that Resource Group

3. **Special handling for VNets**:
   - Virtual Networks are placed **directly** under Resource Groups
   - VNets are the primary network container

4. **Other resources**:
   - Resources not yet in a network hierarchy (VNet/Subnet) are placed under their Resource Group
   - Resources already placed in subnets are **not** duplicated at RG level

**Hierarchy Created**:
```
Resource Group "rg-production"
├── Virtual Network "vnet-prod"
├── Storage Account "stprod001"
├── Key Vault "kv-prod"
└── (other resources not in VNets)
```

**Connections**:
- **Added**: Resource Group → VNet
- **Added**: Resource Group → resources without network placement
- **Not Added**: Resources already in subnet hierarchy (to avoid duplication)

**Logic**:
```
For each resource:
  If resource references this Resource Group:
    If resource is VNet:
      Add to Resource Group
    Else if resource is not in GROUP_NODES:
      Check if resource is already in network hierarchy
      If not in hierarchy:
        Add to Resource Group
```

#### Implementation

> **Note**: The pseudocode below describes the current implementation logic. Following constitution guidelines (CO-006 through CO-012), these handlers SHOULD be migrated to config-driven approach where possible. New Azure handlers MUST use the config-first approach defined in `resource_handler_configs_azure.py`.

```
FUNCTION handle_resource_groups(tfdata):

    // Step 1: Find all Resource Groups
    resource_groups = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_resource_group")
    IF resource_groups is empty:
        RETURN tfdata

    // Step 2: Link resources to their Resource Group
    FOR EACH rg IN resource_groups:
        rg_name = EXTRACT_NAME(rg)

        FOR EACH resource IN graphdict:
            IF resource == rg:
                CONTINUE  // Skip the RG itself

            resource_type = EXTRACT_TYPE(resource)

            // Skip if already a child of this RG
            IF resource IN graphdict[rg]:
                CONTINUE

            // Skip non-VNet group nodes
            IF resource_type IN GROUP_NODES AND resource_type != "azurerm_virtual_network":
                CONTINUE

            // Check if resource references this RG
            IF meta_data[resource] exists:
                rg_ref = meta_data[resource]["resource_group_name"]

                IF rg IN rg_ref OR rg_name IN rg_ref:
                    // VNets go directly under RG
                    IF resource_type == "azurerm_virtual_network":
                        IF resource NOT IN graphdict[rg]:
                            ADD resource TO graphdict[rg]

                    // Other non-group resources
                    ELIF resource_type NOT IN GROUP_NODES:
                        // Check if already in network hierarchy
                        parent_list = GET_PARENTS(graphdict, resource)
                        in_hierarchy = ANY parent type IN GROUP_NODES FOR parent IN parent_list

                        IF NOT in_hierarchy:
                            IF resource NOT IN graphdict[rg]:
                                ADD resource TO graphdict[rg]

    RETURN tfdata
```

---

### Virtual Networks (VNets)

**Philosophy**: VNets are the network boundary in Azure, similar to VPCs in AWS but with key differences:
- VNets are regional (not global like GCP)
- VNets exist within Resource Groups
- Subnets are mandatory subdivisions of VNets

**Transformation**: VNets organize subnets and become network containers.

**What Happens**:
1. **Find all VNets** in the Terraform configuration

2. **Link subnets to VNets**:
   - Check each subnet's `virtual_network_name` attribute
   - Match the subnet to its VNet
   - Add the subnet as a child of the VNet

3. **Remove subnets from incorrect parents**:
   - If a subnet is connected to a non-VNet parent, remove that connection
   - Ensures subnets are only shown within their VNet

**Hierarchy Created**:
```
Resource Group
└── Virtual Network
    ├── Subnet "subnet-web"
    ├── Subnet "subnet-app"
    └── Subnet "subnet-data"
```

**Connections**:
- **Added**: VNet → Subnet (based on virtual_network_name)
- **Removed**: Subnet from non-VNet parents
- **Maintained**: Subnet connections to resources

**Why**: Ensures subnets appear only within their VNet boundary, not scattered across the diagram.

#### Implementation

```
FUNCTION link_subnets_to_vnets(tfdata):

    // Step 1: Find all VNets
    vnets = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_virtual_network")
    IF vnets is empty:
        RETURN tfdata  // No VNets found

    // Step 2: Find all subnets
    subnets = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_subnet")

    // Step 3: Link each subnet to its VNet
    FOR EACH vnet IN vnets:
        vnet_name = EXTRACT_NAME(vnet)  // e.g., "prod" from "azurerm_virtual_network.prod"

        FOR EACH subnet IN subnets:
            // Skip association resources
            IF subnet contains "association":
                CONTINUE

            // Check subnet's metadata for VNet reference
            IF subnet has metadata:
                vnet_reference = subnet.metadata["virtual_network_name"]

                // Flexible matching: check if VNet is referenced
                // Handles: full resource name OR just the name part
                IF vnet IN vnet_reference OR vnet_name IN vnet_reference:

                    // Add subnet to VNet
                    IF subnet NOT IN graphdict[vnet]:
                        ADD subnet TO graphdict[vnet]

                    // Remove subnet from incorrect parents
                    parents = GET_PARENTS(graphdict, subnet)
                    FOR EACH parent IN parents:
                        parent_type = EXTRACT_TYPE(parent)

                        // Keep only in VNet, remove from others
                        IF parent != vnet AND parent_type != "azurerm_virtual_network":
                            IF subnet IN graphdict[parent]:
                                REMOVE subnet FROM graphdict[parent]

    RETURN tfdata
```

**Key Operations**:
- `FIND_RESOURCES_CONTAINING(graphdict, pattern)`: Find resources by name pattern
- `EXTRACT_NAME(resource)`: Get last part after dot (e.g., "prod" from "azurerm_virtual_network.prod")
- **Flexible Matching**: Check both full resource name and short name in reference string

---

### Subnets

**Philosophy**: Subnets are network segments within VNets. In Azure, resources like VMs and NICs are placed within subnets.

**Transformation**: Subnets organize resources and NICs based on network placement.

**What Happens**:

1. **Link Network Interfaces to Subnets**:
   - Check each NIC's `ip_configuration.subnet_id` attribute
   - Match the NIC to its subnet
   - Add the NIC as a child of the subnet

2. **Link Virtual Machines to Subnets** (through NICs):
   - Find VMs that reference NICs (via `network_interface_ids`)
   - If the NIC is in this subnet, place the VM in the subnet too
   - Remove the VM from the NIC's children (VM is now direct child of subnet)

**Hierarchy Created**:
```
Subnet "subnet-web"
├── Network Interface "nic-web-01"
├── Virtual Machine "vm-web-01"
└── Virtual Machine "vm-web-02"
```

**VM Types Handled**:
- `azurerm_virtual_machine` (legacy)
- `azurerm_linux_virtual_machine`
- `azurerm_windows_virtual_machine`

**Connections**:
- **Added**: Subnet → NIC (based on ip_configuration)
- **Added**: Subnet → VM (based on NIC placement)
- **Removed**: VM from NIC's children (moved up to subnet)

**Why**: VMs are the primary resource, NICs are implementation details. Showing VMs at subnet level clarifies network placement.

#### Implementation

```
FUNCTION handle_subnet_resources(tfdata):

    // Step 1: Find subnets (excluding associations)
    subnets = FILTER FIND_RESOURCES_CONTAINING(graphdict, "azurerm_subnet")
              WHERE "association" NOT IN resource_name

    IF subnets is empty:
        RETURN tfdata

    // Step 2: Find NICs
    nics = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_network_interface")

    FOR EACH subnet IN subnets:
        subnet_name = EXTRACT_NAME(subnet)

        // Step 3: Link NICs to subnets
        FOR EACH nic IN nics:
            IF meta_data[nic] exists:
                ip_config = meta_data[nic]["ip_configuration"]
                IF subnet IN ip_config OR subnet_name IN ip_config:
                    IF nic NOT IN graphdict[subnet]:
                        ADD nic TO graphdict[subnet]

        // Step 4: Find VMs
        vms = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_virtual_machine")
        vms += FIND_RESOURCES_CONTAINING(graphdict, "azurerm_linux_virtual_machine")
        vms += FIND_RESOURCES_CONTAINING(graphdict, "azurerm_windows_virtual_machine")

        // Step 5: Link VMs to subnets through NICs
        FOR EACH vm IN vms:
            vm_nic_refs = meta_data[vm]["network_interface_ids"]

            FOR EACH nic IN nics:
                nic_name = EXTRACT_NAME(nic)
                IF nic IN vm_nic_refs OR nic_name IN vm_nic_refs:
                    // If this NIC is in our subnet, put VM here too
                    IF nic IN graphdict[subnet]:
                        IF vm NOT IN graphdict[subnet]:
                            ADD vm TO graphdict[subnet]
                        // Remove VM from NIC (move up to subnet)
                        IF vm IN graphdict[nic]:
                            REMOVE vm FROM graphdict[nic]

    RETURN tfdata
```

---

## Network Security

### Network Security Groups (NSGs)

**Philosophy**: NSGs in Azure function like Security Groups in AWS—they control inbound and outbound traffic. The diagram should show NSGs as **protective boundaries** around resources.

**Key Behavior**: NSGs become **containers** that wrap the resources they protect.

---

### NSG Association Processing

Azure uses association resources to link NSGs to subnets or NICs. TerraVision resolves these associations.

#### Subnet-NSG Associations

**What Happens**:
1. **Find association resources**: `azurerm_subnet_network_security_group_association`

2. **Extract the association**:
   - Read `subnet_id` attribute → identifies the subnet
   - Read `network_security_group_id` attribute → identifies the NSG

3. **Create the connection**:
   - Add the NSG to the subnet
   - Move resources from subnet to NSG
   - Remove the association resource from the graph

**Hierarchy Created**:
```
Before:
Subnet → Virtual Machine
Subnet → Association → NSG

After:
Subnet → NSG → Virtual Machine
```

**Transformation Details**:
- Get all resources currently in the subnet
- Add NSG to the subnet
- Move non-group resources from subnet into NSG
- NSG becomes a security boundary within the subnet

**Connections**:
- **Removed**: Association resource (intermediate)
- **Added**: Subnet → NSG
- **Moved**: Resources from Subnet to NSG
- **Removed**: Direct Subnet → Resource connections (now go through NSG)

**Why**: NSG acts as a firewall boundary. Showing resources inside the NSG visualizes the security perimeter.

#### Implementation

```
FUNCTION process_nsg_associations(tfdata):

    // Step 1: Find NSGs (excluding association resources)
    all_nsgs = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_network_security_group")
    nsgs = FILTER all_nsgs WHERE "association" NOT IN resource_name

    IF nsgs is empty:
        RETURN tfdata  // No NSGs found

    // Step 2: Find subnet-NSG association resources
    associations = FIND_RESOURCES_CONTAINING(
        graphdict,
        "azurerm_subnet_network_security_group_association"
    )

    // Step 3: Process each association
    FOR EACH assoc IN associations:
        IF assoc does not have metadata:
            CONTINUE

        // Extract references from association metadata
        subnet_id = assoc.metadata["subnet_id"]
        nsg_id = assoc.metadata["network_security_group_id"]

        // Find the actual subnet resource (flexible matching)
        target_subnet = null
        all_subnets = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_subnet")
        FOR EACH subnet IN all_subnets:
            IF "association" IN subnet:
                CONTINUE
            subnet_name = EXTRACT_NAME(subnet)
            // Match by full name OR short name
            IF subnet IN subnet_id OR subnet_name IN subnet_id:
                target_subnet = subnet
                BREAK

        // Find the actual NSG resource (flexible matching)
        target_nsg = null
        FOR EACH nsg IN nsgs:
            nsg_name = EXTRACT_NAME(nsg)
            // Match by full name OR short name
            IF nsg IN nsg_id OR nsg_name IN nsg_id:
                target_nsg = nsg
                BREAK

        // Create the connection
        IF target_subnet AND target_nsg exist:

            // Get current subnet resources (copy for safe iteration)
            subnet_resources = COPY(graphdict[target_subnet])

            // Add NSG to subnet
            IF target_nsg NOT IN graphdict[target_subnet]:
                ADD target_nsg TO graphdict[target_subnet]

            // Move non-group resources from subnet into NSG
            FOR EACH resource IN subnet_resources:
                resource_type = EXTRACT_TYPE(resource)

                IF resource_type NOT IN GROUP_NODES AND resource != target_nsg:
                    // Move resource from subnet to NSG
                    IF resource NOT IN graphdict[target_nsg]:
                        ADD resource TO graphdict[target_nsg]
                    IF resource IN graphdict[target_subnet]:
                        REMOVE resource FROM graphdict[target_subnet]

        // Remove the association resource from graph
        DELETE graphdict[assoc]

    RETURN tfdata
```

**Azure Association Pattern**:
1. **Find association resources** (intermediate linking resources)
2. **Extract IDs** from association metadata (subnet_id, nsg_id)
3. **Find actual resources** using flexible matching
4. **Create direct connection** (bypass association)
5. **Remove association** from graph

**Flexible Matching**: Azure resource IDs can be full paths or short names. Check both:
- Full: `azurerm_subnet.main` in `"/subscriptions/.../subnets/main"`
- Short: `main` in `"/subscriptions/.../subnets/main"`

---

#### NIC-NSG Associations

**What Happens**:
1. **Find association resources**: `azurerm_network_interface_security_group_association`

2. **Extract the association**:
   - Read `network_interface_id` attribute → identifies the NIC
   - Read `network_security_group_id` attribute → identifies the NSG

3. **Create the connection**:
   - Add the NIC to the NSG
   - Remove the association resource

**Hierarchy Created**:
```
NSG → Network Interface → Virtual Machine
```

**Connections**:
- **Removed**: Association resource
- **Added**: NSG → NIC

**Why**: NIC-level NSGs provide finer-grained security. The diagram shows this by connecting the NSG directly to the NIC.

---

### NSG to Subnet Matching

**Purpose**: When subnets are numbered (count > 1), NSGs must be matched to subnets with corresponding suffixes.

**What Happens**:
- Extract numeric suffix from subnet name (`~1`, `~2`, `~3`)
- Extract numeric suffix from NSG name
- Add NSG to subnet only if suffixes match

**Example**:
```
Subnets:
- subnet-web~1
- subnet-web~2

NSGs:
- nsg-web~1
- nsg-web~2

Result:
subnet-web~1 → nsg-web~1
subnet-web~2 → nsg-web~2
```

**Why**: Ensures one-to-one mapping between subnet instances and their security groups.

---

## Compute Resources

### Virtual Machines

**Transformation**: VMs are positioned within their subnets based on NIC placement.

**What Happens** (described in Subnets section):
1. Find the VM's NICs (via `network_interface_ids`)
2. Find which subnet contains those NICs
3. Place the VM directly in the subnet
4. Remove the VM from the NIC's children

**Hierarchy**:
```
Subnet
├── Network Interface (implementation detail)
└── Virtual Machine (primary resource)
```

**Why**: The VM is what architects care about. NICs are networking implementation details.

---

### Virtual Machine Scale Sets (VMSS)

**Philosophy**: VMSS are auto-scaling groups of VMs. They need to show network placement and load balancer connections.

**Transformation**: VMSS are linked to subnets and load balancers.

**What Happens**:

1. **Link VMSS to Subnet**:
   - Check `network_profile` attribute in VMSS metadata
   - Find subnet references in the network profile
   - Add VMSS to that subnet

2. **Link VMSS to Load Balancer**:
   - Check `load_balancer_backend_address_pool_ids` attribute
   - Find load balancer references
   - Create connection: Load Balancer → VMSS

**Hierarchy Created**:
```
Subnet
└── Virtual Machine Scale Set

Load Balancer
└── Virtual Machine Scale Set
```

**Connections**:
- **Added**: Subnet → VMSS (based on network_profile)
- **Added**: Load Balancer → VMSS (based on backend pool)

**Why**: Shows both network placement and load balancing relationships for the scale set.

---

## Load Balancing

### Application Gateway

**Philosophy**: Application Gateway is Azure's layer 7 (HTTP/HTTPS) load balancer, similar to AWS ALB.

**Transformation**: Application Gateways are linked to their subnets and backend resources.

**What Happens**:

1. **Link to Subnet**:
   - Check `gateway_ip_configuration` attribute
   - Find subnet references
   - Add Application Gateway to that subnet

2. **Link to Backend VMs**:
   - Check `backend_address_pool` attribute
   - Find VM or VMSS references in backend pool
   - Create connections: Application Gateway → VM/VMSS

**Hierarchy Created**:
```
Subnet (Application Gateway subnet)
└── Application Gateway
    ├── Virtual Machine (backend)
    └── Virtual Machine Scale Set (backend)
```

**Connections**:
- **Added**: Subnet → Application Gateway (based on gateway_ip_configuration)
- **Added**: Application Gateway → Backend VMs (based on backend_address_pool)

**Why**: Shows that Application Gateway sits in its own subnet (Azure best practice) and routes traffic to backend VMs.

---

### Load Balancer (Azure LB)

**Philosophy**: Azure Load Balancer is a layer 4 (TCP/UDP) load balancer, similar to AWS NLB.

**Transformation**: Load Balancers are linked to VMSS through backend pool associations.

**What Happens** (in VMSS processing):
- VMSS references the load balancer's backend pool
- Connection is created: Load Balancer → VMSS

**Hierarchy**:
```
Load Balancer
└── Virtual Machine Scale Set
```

**Connections**:
- **Added**: Load Balancer → VMSS (via backend pool reference)

---

## Shared Services

### Shared Services Grouping

**Philosophy**: Certain Azure services are shared/global and shouldn't clutter the network topology.

**Services Grouped**:
- **Key Vault**: Secrets and key management
- **Azure Container Registry (ACR)**: Container images
- **Log Analytics Workspace**: Centralized logging
- **Application Insights**: Application monitoring
- **Azure Monitor**: Metrics and alerts

**Transformation**:
- A synthetic group node `azurerm_group.shared_services` is created
- All shared services are moved into this group
- The group appears as a separate section in the diagram

**What Happens**:
1. For each resource, check if it matches any shared service pattern
2. Create the shared services group if it doesn't exist
3. Add the resource to the shared services group
4. If the resource has a consolidated name, use that instead

**Connections**:
- **Removed**: Shared services from Resource Group hierarchy
- **Added**: Shared services to shared services group
- **Maintained**: Connections from resources to shared services

**Example**:
```
Resource Group
└── Virtual Network
    └── Subnet
        └── VM → Key Vault (in shared services)

Shared Services Group
├── Key Vault
├── Container Registry
└── Log Analytics Workspace
```

**Why**: Keeps the network topology clean while maintaining visibility of cross-cutting services.

---

## Resource Matching

### NIC to VM Matching

**Purpose**: Ensure VMs are connected to their NICs based on `network_interface_ids` references.

**What Happens**:
1. Find all NICs and VMs in the graph
2. For each VM, read its `network_interface_ids` attribute
3. For each NIC in that list, add the VM to the NIC's connections

**Transformation**:
```
Before:
VM metadata: network_interface_ids = [nic-web-01, nic-web-02]

After:
nic-web-01 → vm-web-01
nic-web-02 → vm-web-01
```

**Connections**:
- **Added**: NIC → VM (based on network_interface_ids)

**Why**: Makes the NIC-to-VM relationship explicit in the graph.

---

### Empty Group Removal

**Purpose**: Remove empty group nodes to keep diagrams clean.

**What Happens**:
1. Find all group nodes (Resource Groups, VNets, Subnets, NSGs)
2. Check if they have any connections (children)
3. If empty, remove from the graph

**Example**:
```
Before:
Resource Group "rg-empty" → (no resources)

After:
(Resource Group removed)
```

**Why**: Empty containers add no value and clutter the diagram.

---

## Special Behaviors

### Association Resource Cleanup

**NSG Associations**: Both subnet-NSG and NIC-NSG association resources are removed after processing:
- `azurerm_subnet_network_security_group_association`
- `azurerm_network_interface_security_group_association`

These are Terraform-specific linking resources that shouldn't appear in architecture diagrams.

**What Happens**:
1. Process the association (create direct connection)
2. Delete the association resource from the graph
3. Result: Direct connection without intermediate node

---

### Suffix Matching Rules

**Numbered Resources**: When resources have `count > 1`, they get numeric suffixes (`~1`, `~2`, etc.).

**Matching Ensures**:
```
subnet~1 → nsg~1
subnet~2 → nsg~2
```

**Prevents Invalid Connections**:
```
❌ subnet~1 → nsg~2  (cross-connection)
✅ subnet~1 → nsg~1  (matched)
```

**Pattern**: Uses regex `~(\d+)$` to extract suffix and match resources.

---

## Helper Functions Reference

### Core Helper Functions

```python
# From modules/helpers.py - Same helpers available as in AWS

def list_of_dictkeys_containing(dictionary, pattern):
    """Find all keys containing pattern."""
    return [k for k in dictionary.keys() if pattern in k]

def list_of_parents(graphdict, resource, strict=False):
    """Find all resources pointing to given resource."""
    parents = []
    for key, deps in graphdict.items():
        if strict:
            if resource in deps:
                parents.append(key)
        else:
            if "*" in resource:
                pattern = resource.replace("*", "")
                for dep in deps:
                    if pattern in dep and key not in parents:
                        parents.append(key)
            else:
                if resource in deps:
                    parents.append(key)
    return parents

def get_no_module_name(node):
    """Strip module prefix from resource name."""
    if node and "module." in node:
        parts = node.split(".")
        for i, part in enumerate(parts):
            if part != "module" and not parts[i-1] == "module":
                return ".".join(parts[i:])
    return node
```

### Azure-Specific Patterns

**Association Resource Pattern**:
```
// Azure uses association resources that should be removed after processing

// 1. Find association resources
associations = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_subnet_network_security_group_association")

// 2. Process each association
FOR EACH assoc IN associations:
    // Extract resource IDs from association metadata
    subnet_id = assoc.metadata["subnet_id"]
    nsg_id = assoc.metadata["network_security_group_id"]

    // Find actual resources using flexible matching
    target_subnet = FIND_BY_ID_OR_NAME(subnets, subnet_id)
    target_nsg = FIND_BY_ID_OR_NAME(nsgs, nsg_id)

    // Create direct connection (bypass association)
    ADD target_nsg TO graphdict[target_subnet]

    // Remove association from graph
    DELETE graphdict[assoc]
```

**Flexible ID Matching**:
```
FUNCTION MATCHES_REFERENCE(resource_name, reference_string):
    // Check if resource matches a reference (handles Azure resource IDs)

    // Full resource name in reference
    IF resource_name IN reference_string:
        RETURN true

    // Just the name part (after last dot)
    short_name = EXTRACT_NAME(resource_name)
    IF short_name IN reference_string:
        RETURN true

    RETURN false
```

**Filter Out Associations**:
```
// When finding resources, exclude association types
all_subnets = FIND_RESOURCES_CONTAINING(graphdict, "azurerm_subnet")
subnets = FILTER all_subnets WHERE "association" NOT IN resource_name
```

---

## Architectural Principles

### Resource Group as Top Container

Azure requires all resources to be in a Resource Group. TerraVision reflects this:

```
Resource Group (mandatory)
└── Resources organized by type
    ├── Network resources (VNets, Subnets)
    ├── Compute resources (VMs, VMSS)
    └── Other resources (Storage, Databases)
```

### VNet as Network Boundary

Virtual Networks are the primary network isolation boundary:

```
VNet
└── Subnets (required subdivision)
    └── Resources (VMs, NICs)
```

Unlike AWS where subnets are somewhat optional, Azure subnets are mandatory for most resources.

### NSG as Security Container

NSGs become containers that visually wrap the resources they protect:

```
Subnet
└── NSG (security boundary)
    └── Resources (protected by NSG)
```

This shows the security perimeter clearly.

### NICs as Implementation Details

Network Interfaces are shown but de-emphasized:
- VMs are placed at subnet level
- NICs are shown as children of VMs or within the connectivity path
- The focus is on VMs (the workload) not NICs (the plumbing)

### Load Balancers Connect to Backends

Load balancing relationships are direct:
```
Application Gateway → Backend VMs
Load Balancer → VMSS
```

No intermediate target groups or backend pools clutter the diagram.

### Shared Services Separate

Cross-cutting services (Key Vault, ACR, Monitoring) are grouped separately:
```
Resource Group 1
└── Application Resources

Resource Group 2
└── Data Resources

Shared Services Group
└── Platform Services (Key Vault, ACR, Monitoring)
```

This separation clarifies that these services are shared across workloads.

---

## Azure vs AWS Differences

### Organizational Model

**Azure**: Resource Group → VNet → Subnet → NSG → Resources
**AWS**: VPC → AZ → Subnet → Security Group → Resources

Azure doesn't have Availability Zones as a required grouping (though they exist).

### Security Groups

**Azure**: NSGs use association resources (explicit linking)
**AWS**: Security Groups reference directly

TerraVision removes Azure's association resources to create direct connections like AWS.

### Network Interfaces

**Azure**: NICs are explicit first-class resources
**AWS**: ENIs exist but are often implicit

TerraVision de-emphasizes NICs in Azure diagrams to match architectural thinking.

### Shared Services

**Azure**: Key Vault, ACR, Monitor are Azure-specific shared services
**AWS**: IAM, KMS, CloudWatch are AWS-specific shared services

Both are grouped similarly but with provider-specific services.

---

This specification describes the **architectural transformation** TerraVision applies to Azure resources to create diagrams that reflect Azure's organizational model and architectural best practices.
