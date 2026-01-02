"""
Azure Style Demonstration Script
Manually creates Azure resources to show new visual styling:
- Light grey card backgrounds (#F2F2F2)
- Azure blue color scheme (#0078D4, #50E6FF)
- Lighter borders (penwidth=1)
- Dashed Resource Group containers
- Availability Zone groups (dotted style)
- Flat hierarchy
"""

from resource_classes import Canvas, setdiagram
from resource_classes.azure.groups import (
    AZUREGroup,
    ResourceGroupCluster,
    VNetGroup,
    SubnetGroup,
    AvailabilityZone,
    SharedServicesGroup,
)
from resource_classes.azure.compute import VM, VMScaleSets
from resource_classes.azure.database import SQLDatabases
from resource_classes.azure.storage import StorageAccounts
from resource_classes.azure.security import KeyVaults
from resource_classes.azure.network import (
    VirtualNetworks,
    ApplicationGateway,
    LoadBalancers,
)

# Create canvas
diagram = Canvas(
    name="Azure Architecture - Style Demo",
    filename="azure-style-demo",
    direction="TB",
    outformat="png",
)
setdiagram(diagram)

# Azure Cloud boundary
with AZUREGroup("Azure Cloud"):

    # Shared Services Group (outside Resource Group)
    with SharedServicesGroup("Shared Services"):
        kv = KeyVaults("Key Vault\nProd")
        storage_shared = StorageAccounts("Storage Account\nLogs")

    # Resource Group
    with ResourceGroupCluster("rg-production"):

        # Virtual Network
        with VNetGroup("vnet-prod (10.0.0.0/16)"):

            # Subnet 1 - Web Tier
            with SubnetGroup("subnet-web (10.0.1.0/24)"):

                # Availability Zone 1
                with AvailabilityZone("Zone 1"):
                    vm1 = VM("VM-Web-01")

                # Availability Zone 2
                with AvailabilityZone("Zone 2"):
                    vm2 = VM("VM-Web-02")

            # Subnet 2 - Data Tier
            with SubnetGroup("subnet-data (10.0.2.0/24)"):

                # Availability Zone 1
                with AvailabilityZone("Zone 1"):
                    db1 = SQLDatabases("SQL Database\nPrimary")

                # Availability Zone 2
                with AvailabilityZone("Zone 2"):
                    db2 = SQLDatabases("SQL Database\nReplica")

            # Subnet 3 - App Services
            with SubnetGroup("subnet-app (10.0.3.0/24)"):
                vmss = VirtualMachineScaleSets("VMSS App\n(3 instances)")

        # Load Balancer (outside VNet, in RG)
        lb = LoadBalancers("Load Balancer\nPublic")

        # Application Gateway (outside VNet, in RG)
        appgw = ApplicationGateway("App Gateway\nWAF")

# Connections
diagram.edge(appgw, lb, label="routes to")
diagram.edge(lb, vm1, label="")
diagram.edge(lb, vm2, label="")
diagram.edge(vm1, db1, label="query")
diagram.edge(vm2, db2, label="query")
diagram.edge(vmss, kv, label="secrets")
diagram.edge(vm1, storage_shared, label="logs")
diagram.edge(vm2, storage_shared, label="logs")

# Render
print("Rendering Azure style demonstration diagram...")
diagram.render()
print(f"✓ Diagram saved to: {diagram.filename}.{diagram.outformat}")
