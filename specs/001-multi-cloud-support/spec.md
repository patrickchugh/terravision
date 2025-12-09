# Feature Specification: Multi-Cloud Provider Support (GCP & Azure)

**Feature Branch**: `001-multi-cloud-support`
**Created**: 2025-12-07
**Status**: Draft
**Input**: User description: "Add support for GCP and Azure terraform resources. The cloud_config.py file needs to be separated for each platform and the cloud provider for each terraform project should be detected during parsing. Once we know which cloud provider we are working with, constants read in for each platform should be from the appropriate cloud_config.py file"

## Clarifications

### Session 2025-12-08

- Q: When the system detects cloud providers in a Terraform project, which detection method should take priority? → A: Resource types first - Check resource prefixes (e.g., `google_`, `azurerm_`, `aws_`) in resources, fall back to provider blocks if no resources found
- Q: What should the system do when it cannot detect any cloud provider (no recognizable resource prefixes and no provider blocks)? → A: Alert user and exit
- Q: Where should the Azure and GCP icons be sourced from for the diagram generation? → A: Diagrams library - Use existing `diagrams` Python library which includes official AWS, GCP, and Azure icons (same approach as current AWS implementation)
- Q: How should users be able to add support for new Azure/GCP resource types not in the initial 50-100 core services? → A: Code modification - Users must modify the cloud_config_*.py files directly and understand Python to add new resources

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Azure Diagram Generation (Priority: P1)

A cloud architect working with Microsoft Azure infrastructure needs to generate architecture diagrams from their Terraform code. They run TerraVision on their Azure Terraform project, and the tool automatically detects Azure resources, uses appropriate Azure icons and styling, and generates a diagram following Azure architectural best practices.

**Why this priority**: Azure is the third major cloud provider and completes the "big three" cloud support. Azure has the largest enterprise adoption among the two new providers, making this feature the highest priority for reaching enterprise users.

**Independent Test**: Can be fully tested by running `terravision draw --source <azure-terraform-project>` on an Azure-only project and verifying the output diagram contains Azure-styled resources with correct icons and relationships.

**Acceptance Scenarios**:

1. **Given** a Terraform project with only Azure provider resources, **When** user runs `terravision draw`, **Then** the tool detects Azure as the cloud provider and generates a diagram with Azure-specific icons and styling
2. **Given** an Azure Terraform project with compute, storage, and networking resources, **When** diagram is generated, **Then** all Azure resources are correctly represented with official Azure icons
3. **Given** an Azure project with resource groups and subscriptions, **When** diagram is generated, **Then** resources are properly grouped by resource group following Azure conventions
4. **Given** an Azure Terraform project, **When** user requests PDF format, **Then** diagram uses Azure-approved color scheme and architectural patterns

---

### User Story 2 - GCP Diagram Generation (Priority: P2)

A DevOps engineer working with Google Cloud Platform infrastructure needs to generate architecture diagrams from their Terraform code. They run TerraVision on their GCP Terraform project, and the tool automatically detects GCP resources, uses appropriate GCP icons and styling, and generates a diagram following GCP architectural best practices.

**Why this priority**: GCP is explicitly listed as "Coming soon" in the README (Status section), making it a logical second cloud provider to support. Many organizations use GCP, and this unblocks a significant user base.

**Independent Test**: Can be fully tested by running `terravision draw --source <gcp-terraform-project>` on a GCP-only project and verifying the output diagram contains GCP-styled resources with correct icons and relationships.

**Acceptance Scenarios**:

1. **Given** a Terraform project with only GCP provider resources, **When** user runs `terravision draw`, **Then** the tool detects GCP as the cloud provider and generates a diagram with GCP-specific icons and styling
2. **Given** a GCP Terraform project with compute, storage, and networking resources, **When** diagram is generated, **Then** all GCP resources are correctly represented with official GCP icons
3. **Given** a GCP project with variables and conditionals, **When** user provides tfvars file, **Then** diagram shows only resources that would actually be deployed based on variable values
4. **Given** a GCP Terraform project, **When** user requests SVG format, **Then** diagram uses GCP-approved color scheme and architectural patterns

---

### ~~User Story 3 - Multi-Cloud Project Support (Priority: P3)~~ **DEFERRED**

**Status**: Out of scope for v0.9 release - Deferred to future release

**Rationale**: Most Terraform projects use a single cloud provider. Users can generate diagrams for multi-cloud projects by running TerraVision separately on each provider's directory. This functionality will be added in a future release after gathering user feedback on single-provider support.

**Original Description**: A solutions architect working on a multi-cloud deployment has Terraform code that provisions resources across AWS, GCP, and Azure. They need to visualize their entire infrastructure by generating separate diagrams per provider (e.g., `architecture-aws.png`, `architecture-gcp.png`, `architecture-azure.png`).

---

### Edge Cases

- What happens when Terraform project has no provider block specified (provider inherited from parent module)?
- What happens when unknown or custom Terraform providers are used (e.g., Kubernetes, Datadog)?
- How does system handle Terraform projects with provider aliases (multiple instances of same provider)?
- What happens when user has GCP/Azure provider blocks but no resources for that provider?
- How does system handle deprecated or renamed GCP/Azure resources?
- What happens when cloud provider cannot be detected definitively (no recognizable resource prefixes and no provider blocks)? → Alert user and exit

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically detect cloud provider(s) used in Terraform project by first checking resource type prefixes (`google_`, `azurerm_`, `aws_`), falling back to provider blocks only if no resources are found
- **FR-001a**: When cloud provider cannot be detected (no recognizable resource prefixes and no provider blocks), system must alert user that there are no cloud resources present and exit.
- **FR-002**: System MUST support Azure Terraform resources with appropriate icon mappings for core services (Virtual Machines, Storage Accounts, VNets, Azure Functions, SQL Database, AKS, etc.)
- **FR-003**: System MUST support GCP Terraform resources with appropriate icon mappings for core services (Compute Engine, Cloud Storage, VPC, Cloud Functions, Cloud SQL, GKE, etc.)
- **FR-004**: System MUST load provider-specific configuration constants from separate configuration files based on detected provider
- **FR-005**: System MUST use separate resource handlers for each cloud provider (AWS, GCP, Azure) to process provider-specific resource types and relationships
- **FR-006**: System MUST maintain backward compatibility by producing the same deterministic rules based graph object when run with existing AWS Terraform projects, unless there are errors in the previous output
- **FR-007**: System MUST apply provider-specific styling (colors, icon style, grouping conventions) to generated diagrams
- **FR-008**: Users MUST be able to generate diagrams for Azure, GCP and AWS projects in all supported formats (PNG, SVG, PDF, BMP)
- **FR-011**: System MUST use official cloud provider icons from the `diagrams` Python library and follow provider-specific architectural diagram conventions
- **FR-012**: System MUST support annotations (YAML-based) for Azure and GCP diagrams same as AWS
- **FR-013**: System MUST export graph data (JSON) for Azure and GCP projects same as AWS
- **FR-014**: System MUST support AI-powered refinement for AWS, Azure and GCP diagrams using provider-specific architectural best practices

### Assumptions

- Azure and GCP icons will be sourced from the `diagrams` Python library (same as current AWS implementation), with initial support for 50-100 core services (expandable over time) rather than AWS's 200+ services initially
- Cloud provider detection will use standard Terraform provider block syntax (`provider "google"`, `provider "azurerm"`)
- Provider-specific configuration files organized in `modules/config/` subdirectory: `modules/config/cloud_config_aws.py`, `modules/config/cloud_config_gcp.py`, `modules/config/cloud_config_azure.py`
- Most Terraform projects are single-cloud by design; multi-cloud projects in a single repository are rare (multi-cloud support deferred to future release)
- Each cloud provider requires its own resource handler to properly process provider-specific resource types, attributes, and relationships
- Existing `modules/cloud_config.py` will be moved to `modules/config/cloud_config_aws.py` with imports updated throughout codebase
- Users can extend resource support by directly modifying `modules/config/cloud_config_*.py` files (requires Python knowledge); no separate configuration file or plugin system will be provided initially

### Key Entities

- **Cloud Provider Configuration**: Provider-specific settings including icon mappings, color schemes, service names, AI refinement prompts, and architectural conventions
- **Resource Handler**: Provider-specific processing logic that understands how to parse, interpret, and extract relationships from each cloud provider's Terraform resource types (separate handlers for AWS, GCP, Azure)
- **Provider Detection Result**: Information about which cloud provider(s) are used in the Terraform project, including primary provider and any secondary providers
- **Resource Icon Mapping**: Mapping between Terraform resource types (e.g., `google_compute_instance`) and icon classes from the `diagrams` Python library for each cloud provider
- **Provider-Specific Styling**: Color palettes, grouping rules, connection styles, and layout preferences for each cloud provider

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully generate architecture diagrams for Azure Terraform projects with the same commands and options available for AWS projects
- **SC-002**: Users can successfully generate architecture diagrams for GCP Terraform projects with the same commands and options available for AWS projects
- **SC-003**: Diagram generation for Azure projects completes within the same performance targets as AWS projects (no more than 20% slower for similar-sized projects)
- **SC-004**: Diagram generation for GCP projects completes within the same performance targets as AWS projects (no more than 20% slower for similar-sized projects)
- **SC-005**: Generated Azure diagrams use recognizable official Azure icons and styling that Azure users can immediately identify
- **SC-006**: Generated GCP diagrams use recognizable official GCP icons and styling that GCP users can immediately identify
- **SC-007**: All existing AWS diagram generation functionality continues to work without regression (backward compatibility maintained)
- **SC-008**: Cloud provider detection achieves 100% accuracy on Terraform projects with explicit provider blocks
- **SC-009**: System correctly handles at least 30 core Azure resource types at initial release
- **SC-010**: System correctly handles at least 30 core GCP resource types at initial release
- **SC-011**: Users can extend GCP/Azure resource support by modifying the respective `cloud_config_*.py` files to add new resource-to-icon mappings (requires Python knowledge)
- **SC-012**: Documentation clearly explains Azure and GCP support status, limitations, and roadmap for additional services
