<!--
Sync Impact Report:
- Version change: 1.0.0 → 1.1.0 (added new technical standard)
- Modified principles: None
- Added sections: Technical Standards > Code Organization > Provider-Specific Code Isolation
- Removed sections: None
- Templates status:
  ✅ plan-template.md - Constitution Check section aligns with principles
  ✅ spec-template.md - Requirements sections align with testability principles
  ✅ tasks-template.md - Task organization reflects independent testing principles
  ⚠ CLAUDE.md - Already contains detailed guidance on provider-specific architecture that aligns with new standard
- Follow-up TODOs: None
-->

# TerraVision Constitution

## Core Principles

### I. Code as Source of Truth

The infrastructure code (Terraform) is the authoritative source of truth for architecture diagrams. Architecture diagrams MUST be generated from code, not manually drawn. Human-generated architecture diagrams are inherently stale in high-velocity environments. Machine-generated diagrams maintain accuracy by dynamically parsing actual infrastructure definitions.

**Rationale**: Manual diagrams become outdated immediately after deployment. By treating code as truth and automating diagram generation, TerraVision ensures architecture documentation reflects deployed reality, reducing discrepancies between documentation and production.

### II. Client-Side Security & Privacy

All processing MUST occur 100% client-side without cloud environment access. TerraVision MUST NOT require cloud credentials, API access, or intrusive cloud resources. Only minimal aggregate metadata may be sent to LLM backends - never sensitive code or runtime values.

**Rationale**: Enterprise security requirements prohibit tools that need cloud access or expose sensitive infrastructure details. Client-side processing ensures organizations maintain complete control over their infrastructure code and secrets without third-party exposure.

### III. Docs as Code (DaC)

Architecture diagrams MUST be treatable as code artifacts: versioned, automated, and integrated into CI/CD pipelines. Diagrams MUST be generated in build/test/release phases and committed to version control alongside infrastructure code.

**Rationale**: Documentation should follow the same discipline as code - versioned, reviewed, and automated. CI/CD integration ensures diagrams update automatically with infrastructure changes, eliminating manual diagram maintenance overhead.

### IV. Dynamic Parsing & Accuracy

The tool MUST dynamically parse conditionally created resources and variables to generate accurate architecture visuals. Diagrams MUST reflect the actual infrastructure that would be deployed, including conditional logic and variable substitution.

**Rationale**: Static parsing misses conditional resources and variable-driven infrastructure. Dynamic parsing ensures diagrams show what actually gets deployed based on workspace/variable configurations, not just what's theoretically possible.

### V. Multi-Cloud & Provider Agnostic Design

The architecture MUST support multiple cloud providers (AWS, GCP, Azure) and on-premises infrastructure with consistent icon libraries and styling. Provider-specific implementations MUST follow industry-standard architectural patterns and approved visual styles.

**Rationale**: Organizations operate in multi-cloud environments. Provider-agnostic design allows a single tool to document entire infrastructure portfolios, while consistent styling ensures diagrams remain readable across different cloud platforms.

### VI. Extensibility Through Annotations

Generated diagrams MUST be extensible via YAML-based annotations without modifying source code. Users MUST be able to add custom labels, connections, resources, and titles to supplement auto-generated output. Annotations follow Diagrams as Code principles.

**Rationale**: Automated generation achieves 80-90% completeness but cannot capture external systems, organizational context, or non-Terraform resources. YAML annotations provide declarative, version-controllable extensibility without code modification.

### VII. AI-Assisted Refinement (Optional)

AI-powered diagram refinement MUST remain optional and support multiple backends (cloud-based, local). AI refinement MUST fix groupings, add missing connections, and enforce architectural conventions. Local AI options (Ollama) MUST be available for privacy-sensitive environments.

**Rationale**: AI improves diagram quality by applying architectural best practices and detecting missing relationships, but must remain optional to support air-gapped environments. Multiple backend support allows organizations to choose between convenience (cloud) and privacy (local).

## Technical Standards

### Supported Technologies

- **Language**: Python 3.10+
- **Required Dependencies**: Terraform 1.x, Git, Graphviz
- **Optional Dependencies**: Ollama (for local AI), AWS Bedrock (for cloud AI)
- **Input Formats**: .tf, .tf.json, .tfvars, .tfvars.json, Git repositories, pre-generated JSON
- **Output Formats**: PNG (default), SVG, PDF, BMP, JSON

### Code Organization

#### Provider-Specific Code Isolation

All cloud-specific resource handling logic MUST reside exclusively in provider-specific configuration and handler modules. Common modules shared across all cloud service providers (CSPs) MUST remain provider-agnostic.

**Enforcement Rules**:

- **CO-001**: Cloud-specific resource handling logic MUST be implemented in `modules/config/cloud_config_<provider>.py` files (e.g., `cloud_config_aws.py`, `cloud_config_azure.py`, `cloud_config_gcp.py`)
- **CO-002**: Provider-specific resource handlers MUST be implemented in `modules/resource_handlers_<provider>.py` files (e.g., `resource_handlers_aws.py`, `resource_handlers_azure.py`, `resource_handlers_gcp.py`)
- **CO-003**: Common modules (e.g., `graphmaker.py`, `drawing.py`, `fileparser.py`, `interpreter.py`, `tfwrapper.py`) MUST NOT contain hardcoded provider-specific logic or resource types
- **CO-004**: Provider detection and configuration loading MUST use dynamic dispatch patterns to route to provider-specific implementations
- **CO-005**: New cloud provider support MUST follow the established pattern: create `cloud_config_<provider>.py` + `resource_handlers_<provider>.py` without modifying common modules

**Rationale**: Strict separation of provider-specific code from common infrastructure ensures maintainability, testability, and extensibility as new cloud providers are added. This architectural boundary prevents provider-specific logic from polluting shared modules and enables teams to add cloud support without risk of breaking existing providers.

### Quality Requirements

- **QR-001**: Architecture diagrams MUST be generated without requiring deployed infrastructure (work from `terraform plan`, not remote state)
- **QR-002**: Tool MUST handle large Terraform projects (200+ resources) efficiently with simplified diagram options
- **QR-003**: Tool MUST automatically download and parse organizational/external Terraform modules
- **QR-004**: Debug mode MUST export intermediate state (tfdata.json) for troubleshooting without re-running slow terraform operations
- **QR-005**: All CLI commands MUST support both human-readable and JSON output formats

### Testing Standards

- **TS-001**: Changes MUST NOT break terraform plan parsing for supported Terraform versions (1.x)
- **TS-002**: Provider support additions MUST include icon library and resource mapping tests
- **TS-003**: Annotation functionality MUST be tested with valid and malformed YAML inputs
- **TS-004**: CI/CD integration examples MUST be validated against actual pipeline runners

## Development Workflow

### Feature Development

1. **Specification**: New features MUST include user scenarios with acceptance criteria
2. **Testing**: Core functionality changes MUST be validated with real Terraform repositories
3. **Documentation**: New features MUST update README with usage examples and troubleshooting
4. **Backward Compatibility**: Changes MUST maintain compatibility with existing Terraform code, Graph Transformation logic and annotation files. All deterministic JSON output should pass the unit tests to ensure the same values are produced with new code.
5. Format and location changes of config files are permitted when new cloud providers are introduced or where necessary.

### Code Review Requirements

- **CR-001**: Parser changes require validation against 3+ real-world Terraform repositories
- **CR-002**: Icon/styling changes require visual comparison screenshots in PR
- **CR-003**: AI backend changes require testing with both Bedrock and Ollama
- **CR-004**: Security-related changes require explicit threat model consideration
- **CR-005**: Provider-specific code changes MUST NOT modify common modules (enforces CO-001 through CO-005)

### Release Criteria

- **RC-001**: Each release MUST increment version following semantic versioning in pyproject.toml
- **RC-002**: Breaking changes to annotation YAML format require migration guide
- **RC-003**: New cloud provider support requires icon library with the top 30 services ready for use
- **RC-004**: Performance regressions >20% on reference repositories block release

## Governance

### Constitution Authority

This constitution supersedes all other development practices and documentation. Any conflict between this constitution and other guidance documents MUST be resolved in favor of the constitution. Amendments require documented justification, technical review, and version increment.

### Amendment Procedure

1. **Proposal**: Document proposed change with rationale and impact analysis
2. **Review**: Technical review of implications across codebase and user workflows
3. **Approval**: Maintainer approval required for principle additions/removals
4. **Migration**: Update dependent templates, documentation, and examples
5. **Version**: Increment constitution version following semantic versioning

### Compliance & Enforcement

- **All pull requests** MUST verify compliance with security principles (client-side processing, no credentials)
- **Feature proposals** that violate Code as Source of Truth principle MUST be rejected
- **Architectural changes** requiring server-side processing or cloud credentials MUST provide compelling justification and maintain client-side alternative
- **Complexity additions** (new dependencies, architectural patterns) MUST demonstrate necessity over simpler alternatives
- **Provider-specific changes** MUST comply with Code Organization standards (CO-001 through CO-005)

### Versioning Policy

- **MAJOR**: Backward-incompatible changes to CLI interface, annotation format, or core principles
- **MINOR**: New cloud provider support, new output formats, new AI backends, new principles, new technical standards
- **PATCH**: Bug fixes, documentation updates, icon additions, clarifications

**Version**: 1.1.0 | **Ratified**: 2025-12-07 | **Last Amended**: 2025-12-20
