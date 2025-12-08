# Feature Specification: Multi-Cloud Provider Support (GCP & Azure)

**Feature Branch**: `001-multi-cloud-support`
**Created**: 2025-12-07
**Status**: Draft
**Input**: User description: "Add support for GCP and Azure terraform resources. The cloud_config.py file needs to be separated for each platform and the cloud provider for each terraform project should be detected during parsing. Once we know which cloud provider we are working with, constants read in for each platform should be from the appropriate cloud_config.py file"

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

### User Story 3 - Multi-Cloud Project Support (Priority: P3)

A solutions architect working on a multi-cloud deployment has Terraform code that provisions resources across AWS, GCP, and Azure. They need to visualize their entire infrastructure. When they run TerraVision, the tool detects all cloud providers used and generates separate diagrams per provider (e.g., `architecture-aws.png`, `architecture-gcp.png`, `architecture-azure.png`). This scenario is rare since most Terraform projects are single-cloud by design.

**Why this priority**: While uncommon (most Terraform projects use a single cloud provider), multi-cloud is an emerging pattern. This is P3 because users can already generate diagrams by running TerraVision on each cloud provider's directory separately.

**Independent Test**: Can be tested by running `terravision draw` on a Terraform project with multiple provider blocks and verifying that separate diagram files are generated for each detected provider.

**Acceptance Scenarios**:

1. **Given** a Terraform project with AWS, GCP, and Azure providers, **When** user runs `terravision draw`, **Then** system detects all three providers and generates three separate diagram files (one per provider)
2. **Given** a multi-cloud project, **When** diagrams are generated, **Then** each diagram follows its respective provider's styling conventions and contains only resources from that provider
3. **Given** a multi-cloud project with resources from two providers, **When** diagram generation completes, **Then** user receives clearly named output files indicating which provider each diagram represents

---

### Edge Cases

- What happens when Terraform project has no provider block specified (provider inherited from parent module)?
- What happens when unknown or custom Terraform providers are used (e.g., Kubernetes, Datadog)?
- How does system handle Terraform projects with provider aliases (multiple instances of same provider)?
- What happens when user has GCP/Azure provider blocks but no resources for that provider?
- How does system handle deprecated or renamed GCP/Azure resources?
- What happens when cloud provider cannot be detected definitively?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically detect cloud provider(s) used in Terraform project by parsing provider blocks and resource types
- **FR-002**: System MUST support Azure Terraform resources with appropriate icon mappings for core services (Virtual Machines, Storage Accounts, VNets, Azure Functions, SQL Database, AKS, etc.)
- **FR-003**: System MUST support GCP Terraform resources with appropriate icon mappings for core services (Compute Engine, Cloud Storage, VPC, Cloud Functions, Cloud SQL, GKE, etc.)
- **FR-004**: System MUST load provider-specific configuration constants from separate configuration files based on detected provider
- **FR-005**: System MUST use separate resource handlers for each cloud provider (AWS, GCP, Azure) to process provider-specific resource types and relationships
- **FR-006**: System MUST maintain backward compatibility with existing AWS Terraform projects
- **FR-007**: System MUST apply provider-specific styling (colors, icon style, grouping conventions) to generated diagrams
- **FR-008**: System MUST handle Terraform projects with mixed cloud providers (AWS + GCP + Azure) by generating separate diagrams per provider
- **FR-009**: Users MUST be able to generate diagrams for Azure projects in all supported formats (PNG, SVG, PDF, BMP)
- **FR-010**: Users MUST be able to generate diagrams for GCP projects in all supported formats (PNG, SVG, PDF, BMP)
- **FR-011**: System MUST use official cloud provider icons and follow provider-specific architectural diagram conventions
- **FR-012**: System MUST support annotations (YAML-based) for Azure and GCP diagrams same as AWS
- **FR-013**: System MUST export graph data (JSON) for Azure and GCP projects same as AWS
- **FR-014**: System MUST support AI-powered refinement for Azure and GCP diagrams using provider-specific architectural best practices

### Assumptions

- Azure and GCP icon libraries will start with 50-100 core services (expandable over time) rather than AWS's 200+ services initially
- Cloud provider detection will use standard Terraform provider block syntax (`provider "google"`, `provider "azurerm"`)
- Provider-specific configuration files will follow naming convention: `cloud_config_aws.py`, `cloud_config_gcp.py`, `cloud_config_azure.py`
- Most Terraform projects are single-cloud by design; multi-cloud projects in a single repository are rare
- Multi-cloud projects will always generate separate diagrams per provider (e.g., `architecture-aws.png`, `architecture-azure.png`, `architecture-gcp.png`)
- Each cloud provider requires its own resource handler to properly process provider-specific resource types, attributes, and relationships
- Existing `cloud_config.py` will be refactored to `cloud_config_aws.py` maintaining backward compatibility

### Key Entities

- **Cloud Provider Configuration**: Provider-specific settings including icon mappings, color schemes, service names, AI refinement prompts, and architectural conventions
- **Resource Handler**: Provider-specific processing logic that understands how to parse, interpret, and extract relationships from each cloud provider's Terraform resource types (separate handlers for AWS, GCP, Azure)
- **Provider Detection Result**: Information about which cloud provider(s) are used in the Terraform project, including primary provider and any secondary providers
- **Resource Icon Mapping**: Mapping between Terraform resource types (e.g., `google_compute_instance`) and visual icon files for each cloud provider
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
- **SC-009**: System correctly handles at least 50 core Azure resource types at initial release
- **SC-010**: System correctly handles at least 50 core GCP resource types at initial release
- **SC-011**: Users can extend GCP/Azure resource support by adding icon mappings without modifying core parsing logic
- **SC-012**: Documentation clearly explains Azure and GCP support status, limitations, and roadmap for additional services
