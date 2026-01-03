# Test Fixture: Azure VM and VMSS

**User Story**: US-1 - Azure Compute Architecture Visualization

## Purpose

This test fixture validates the following Azure resource handlers:
- Resource Group container hierarchy (FR-001)
- VNet container hierarchy (FR-003)
- Subnet container hierarchy (FR-004)
- Network Security Group security boundaries (FR-005, FR-022)
- Virtual Machine placement (FR-006)
- VM Scale Set zone expansion (FR-007, FR-008)
- NIC placement and associations (FR-009)

## Resources

### Hierarchy
- **Resource Group**: `rg-terravision-test`
  - **VNet**: `vnet-terravision-test` (10.0.0.0/16)
    - **Subnet**: `subnet-main` (10.0.1.0/24)
      - **NSG**: `nsg-terravision-test` (with SSH rule)
        - **VM**: `vm-terravision-test` (Standard_B1s)
        - **VMSS**: `vmss-terravision-test` (3 instances across zones 1,2,3)

### Association Resources (Should be removed in diagram)
- `azurerm_subnet_network_security_group_association.main` - Links NSG to Subnet

## Expected Diagram Output

The diagram should show:

1. **Hierarchy**: Resource Group → VNet → Subnet → NSG → (VM + VMSS)
2. **VMSS Expansion**: VMSS should expand to 3 numbered instances (`vmss~1`, `vmss~2`, `vmss~3`)
3. **Zone Placement**: Each VMSS instance should be associated with its availability zone
4. **NIC Connections**: NIC should connect VM to Subnet
5. **Association Removal**: NSG association resource should NOT appear in diagram

## Validation Criteria

- ✅ Resources appear with correct Azure icons
- ✅ Hierarchy is visually clear (nested containers or subgraphs)
- ✅ VMSS expands to 3 instances with zone labels
- ✅ NSG shows security boundary around resources
- ✅ Association resource is hidden from diagram
- ✅ Connections follow Terraform dependencies

## Running This Test

```bash
# Generate baseline diagram (without custom handlers)
poetry run python terravision.py graphdata --source tests/fixtures/azure_terraform/test_vm_vmss/ --outfile baseline-us1.json --debug

# Generate diagram with handlers
poetry run python terravision.py draw --source tests/fixtures/azure_terraform/test_vm_vmss/

# Run automated test
poetry run pytest tests/test_azure_resources.py::test_vm_vmss_handler -v
```

## Notes

- This test uses `skip_provider_registration = true` to allow testing without Azure credentials
- SSH public key is a dummy key for testing purposes only
- VM and VMSS use minimal SKU (Standard_B1s) to keep costs low if accidentally deployed
