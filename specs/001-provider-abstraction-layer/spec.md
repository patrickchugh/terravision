# Feature Specification: Provider Abstraction Layer

**Feature Branch**: `001-provider-abstraction-layer`  
**Created**: 2025-11-26  
**Status**: Draft  
**Input**: User description: "Implement Provider Abstraction Layer to decouple cloud-specific logic from core graph building and rendering, enabling multi-cloud support for Azure and GCP"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - AWS User Maintains Current Workflow (Priority: P1)

As an existing AWS-focused engineer, I want to generate architecture diagrams from my Terraform code without any changes to my workflow, so that the multi-cloud refactor does not disrupt my daily work.

**Why this priority**: This is the highest priority because breaking existing AWS users would violate the constitution's principle of maintaining backwards compatibility and client-side reliability. The 80%+ of current users rely on AWS diagram generation.

**Independent Test**: Can be fully tested by running existing AWS Terraform projects through the tool and verifying that diagrams match previous versions (regression testing against v0.8 snapshots).

**Acceptance Scenarios**:

1. **Given** an AWS Terraform project with VPC, EC2, RDS, and S3 resources, **When** I run `terravision draw --source ./aws-terraform`, **Then** the generated diagram matches the v0.8 output with identical resource grouping, relationships, and icons.

2. **Given** AWS Terraform using consolidated nodes (like multiple Load Balancers), **When** I generate a diagram, **Then** the consolidation behavior is identical to v0.8 (no regression in AWS-specific logic).

3. **Given** AWS Terraform with annotations YAML referencing `aws_*` resources, **When** I apply annotations, **Then** custom labels, connections, and modifications work exactly as before.

---

### User Story 2 - Multi-Cloud Engineer Specifies Provider (Priority: P2)

As a multi-cloud architect working with Azure resources, I want to specify `--provider azure` when generating diagrams from my Terraform code, so that Azure-specific resource handling and icons are applied correctly.

**Why this priority**: This is the core value proposition of the provider abstraction - enabling Azure and GCP support. This must work for the feature to deliver business value, but AWS compatibility (P1) must not be broken to achieve it.

**Independent Test**: Can be tested independently by creating a minimal Azure Terraform project (virtual network, subnet, VM, NSG) and verifying that `terravision draw --source ./azure-terraform --provider azure` generates a diagram with Azure-specific icons and relationships.

**Acceptance Scenarios**:

1. **Given** an Azure Terraform project with virtual_network and subnet resources, **When** I run `terravision draw --source ./azure-tf --provider azure`, **Then** the diagram shows Azure network icons and correct vnet→subnet relationships.

2. **Given** a GCP Terraform project with network, subnetwork, and compute_instance resources, **When** I run `terravision draw --source ./gcp-tf --provider gcp`, **Then** the diagram uses GCP-specific icons and applies GCP firewall/LB consolidation rules.

3. **Given** Terraform with both AWS and Azure resources (multi-cloud project), **When** I run without specifying provider, **Then** the system auto-detects providers from resource prefixes and applies correct handling per resource.

---

### User Story 3 - Contributor Adds New Provider (Priority: P3)

As an open-source contributor wanting to add Kubernetes provider support, I want to register a new provider using a documented interface without modifying core modules, so that I can extend TerraVision's capabilities independently.

**Why this priority**: This validates the extensibility of the abstraction layer and enables community contributions. It's lower priority than core AWS/Azure/GCP functionality but critical for long-term growth.

**Independent Test**: Can be tested by creating a minimal provider descriptor for a simple provider (e.g., `github_*` resources), registering it, and generating a diagram that includes resources from that provider alongside AWS resources.

**Acceptance Scenarios**:

1. **Given** I create a provider descriptor with resource prefixes, config module path, and handler module path, **When** I register it with the ProviderRegistry, **Then** resources matching those prefixes are recognized and processed using my custom handlers.

2. **Given** I implement provider-specific config (consolidated nodes, draw order, variants), **When** resources from my provider are included in Terraform, **Then** those config rules are applied without affecting AWS/Azure/GCP resources.

3. **Given** I create custom resource class icons for my provider, **When** diagrams are generated, **Then** my provider's icons are loaded from the correct directory path.

---

### Edge Cases

- What happens when Terraform contains mixed provider resources (AWS + Azure + GCP) in the same state file?
- How does system handle unknown provider prefixes not registered (e.g., `datadog_*` before Datadog provider is added)?
- What happens when provider config files are missing or malformed?
- How does system prioritize when multiple providers match the same resource prefix?
- What happens when a provider's resource handler function raises an exception?
- How does system handle provider auto-detection failures (ambiguous or no providers found)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain 100% backwards compatibility with existing AWS Terraform projects when no `--provider` flag is specified (default provider is AWS).

- **FR-002**: System MUST support explicit provider selection via `--provider <name>` CLI flag where `<name>` is one of: aws, azure, gcp.

- **FR-003**: System MUST auto-detect provider(s) from Terraform resource prefixes when no explicit `--provider` flag is given (detect `aws_`, `azurerm_`, `google_` prefixes).

- **FR-004**: System MUST isolate all provider-specific configuration (consolidated nodes, group nodes, draw order, variants, reverse arrows, shared services, auto annotations) in provider-specific modules under `modules/cloud_config/{aws,azure,gcp}.py`.

- **FR-005**: System MUST load provider configurations dynamically at runtime based on detected or specified provider(s), not via hardcoded imports.

- **FR-006**: System MUST route all provider-specific resource handling (special resource handlers like VPC/subnet relationships, LB consolidation, security group reversals) through a provider registry that dispatches to provider-specific handler modules.

- **FR-007**: System MUST support mixed-provider Terraform graphs where resources from multiple providers (e.g., AWS + Azure) coexist in the same diagram.

- **FR-008**: System MUST tag each node in metadata with its provider identifier (e.g., `meta_data[node]["provider"] = "aws"`) for provider-aware processing.

- **FR-009**: System MUST provide a registration interface for future providers to plug in without modifying core graph building, rendering, or CLI modules.

- **FR-010**: System MUST fail gracefully when encountering unknown provider resources, falling back to generic node rendering with a warning message.

- **FR-011**: Core modules (graphmaker, interpreter, helpers, drawing, annotations) MUST NOT import provider-specific constants directly; they MUST access config through ProviderContext interfaces.

- **FR-012**: System MUST maintain diagram output determinism (same Terraform input produces identical diagram) across refactor from hard-coded AWS to provider abstraction.

### Key Entities

- **ProviderDescriptor**: Metadata describing a provider including: provider ID (string), resource prefixes (tuple), cloud config module path (string), handler module path (string). Used for provider registration and discovery.

- **ProviderContext**: Runtime container holding loaded provider configurations and handler modules. Provides interface methods: `detect_provider_for_node(node)`, `get_config(provider_id)`, `get_handler(provider_id)`, `consolidate()`, `map_variant()`, `implied_connections()`. Manages provider-specific operations.

- **CloudConfig**: Provider-specific configuration data structure containing: CONSOLIDATED_NODES, GROUP_NODES, EDGE_NODES, DRAW_ORDER, AUTO_ANNOTATIONS, NODE_VARIANTS, REVERSE_ARROW_LIST, FORCED_DEST, FORCED_ORIGIN, IMPLIED_CONNECTIONS, SHARED_SERVICES, ALWAYS_DRAW_LINE, NEVER_DRAW_LINE, ACRONYMS_LIST, NAME_REPLACEMENTS. Loaded per provider.

- **ResourceHandler**: Provider-specific functions for special resource processing (e.g., `aws_handle_vpc_subnets`, `azure_handle_vnet_subnets`, `gcp_handle_firewall`). Registered in handler modules per provider.

- **ServiceMapping**: Cross-provider resource categorization mapping Terraform resource types to canonical categories (compute, network, storage, database, security, management). Enables semantic grouping across providers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Existing AWS Terraform projects generate diagrams with 100% parity to v0.8 outputs (zero regressions in visual output, grouping, relationships, or icons when tested against 20+ AWS sample projects).

- **SC-002**: Azure and GCP Terraform projects successfully generate diagrams with provider-specific icons and relationships when specifying `--provider azure` or `--provider gcp` (tested with 5+ sample projects per provider).

- **SC-003**: Mixed-provider Terraform projects (AWS + Azure or AWS + GCP) generate diagrams showing resources from both providers with correct per-provider handling (tested with 3+ multi-cloud sample projects).

- **SC-004**: Core modules (graphmaker, drawing, helpers, interpreter, annotations) contain zero direct imports of `AWS_*` constants (validated via static code analysis using grep/AST parsing).

- **SC-005**: System can register and process a new provider (e.g., Kubernetes with `kubernetes_*` prefixes) in under 3 hours of development time for someone with moderate Python experience, following documentation (measured via contributor trial).

- **SC-006**: Diagram generation time for 500-node AWS graphs remains within 10% of v0.8 baseline performance (no significant performance regression from abstraction overhead).

- **SC-007**: Test coverage for provider detection, config loading, handler dispatch, and mixed-provider scenarios reaches 80% line coverage (measured via pytest --cov).

- **SC-008**: All P0 critical issues from CODEREVIEW.md related to provider coupling (Issues #1, #2, #3) are resolved as validated by code review checklist.
