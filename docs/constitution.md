<!--
Sync Impact Report:
- Version change: 1.5.0 → 1.6.0 (clarified credentials boundary in Principle II;
  expanded Principle I to explicitly require plan over state)
- Modified principles:
  - I. Code as Source of Truth — added explicit guidance on why plan is preferred
    over state file as the input source. State is a snapshot of yesterday's
    deployment; plan is the semantic content of the code.
  - II. Client-Side Security & Privacy — clarified that TerraVision itself
    requires no cloud credentials. Cloud API access happens only when Terraform
    is invoked by TerraVision to generate a plan. Pre-generated plan/graph file
    mode (`--planfile` / `--graphfile`) is fully credential-free.
- Added sections: None
- Removed sections: None
- Templates status:
  ✅ plan-template.md - Constitution Check section aligns with principles
  ✅ spec-template.md - Requirements sections align with testability principles
  ✅ tasks-template.md - Task organization reflects independent testing principles
  ✅ CLAUDE.md - No changes required
- Follow-up TODOs: None
-->

# TerraVision Constitution

## Core Principles

### I. Code as Source of Truth

The infrastructure code (Terraform) is the authoritative source of truth for architecture diagrams. Architecture diagrams MUST be generated from code (via `terraform plan` output), not from deployed state files, and not manually drawn. Machine-generated diagrams maintain accuracy by dynamically parsing actual infrastructure definitions and resolving conditionals, variables, counts, and for_each expressions through the Terraform evaluation engine.

**Why plan, not state**:

- **State is a snapshot of yesterday's deployment; plan is the semantic content of the code today.** A new feature branch with 50 new resources would show 0 in state but all 50 in plan. A half-deployed environment would show partial reality in state. A `count = var.enable_feature ? N : 0` block in state only reflects the last-applied value.
- **Variant rendering requires plan.** `--varfile prod.tfvars` vs `--varfile dev.tfvars` vs `--varfile dr.tfvars` produces fundamentally different architectures from the same code. State is one snapshot of one workspace at one point in time and cannot be pivoted to show "what would dev look like with this same code."
- **Pre-deployment review requires plan.** `terravision draw` against a feature branch shows the architecture impact before merging. Greenfield projects that have never been applied have no state but have valid plan output.
- **Conditional logic resolution requires plan.** `count`, `for_each`, `dynamic` blocks, and ternary expressions are evaluated by Terraform's plan engine. State is the *result* of evaluation, not the evaluation itself.
- **Plan outputs are CI-friendly.** `terraform plan -out=tfplan.bin && terraform show -json tfplan.bin > plan.json` already runs in most pipelines. TerraVision can consume that artifact via `--planfile` with zero new infrastructure or permissions.

State files MAY be used as an *optional enrichment overlay* to populate `(known after apply)` values in detailed metadata views (e.g., the interactive HTML sidebar), but MUST NOT be used as the primary or sole input source for diagram structure. When state-file enrichment is used, sensitive attributes MUST be redacted by default.

**Rationale**: Manual diagrams become outdated immediately after deployment. State-based diagrams document yesterday's deployment, not today's code. By treating code as truth and using `terraform plan` as the authoritative input, TerraVision shows what the code defines, supports multi-environment variants, works on undeployed branches, and accurately reflects conditional logic — all things state files cannot do.

### II. Client-Side Security & Privacy

TerraVision itself MUST NOT require cloud credentials, API access, or intrusive cloud resources. The TerraVision binary parses files (Terraform source, plan JSON, graph DOT) and renders diagrams. It does not authenticate to cloud providers, does not call cloud APIs, and does not write or read remote state.

Cloud API access happens only when TerraVision invokes Terraform as a subprocess to generate a plan from raw `.tf` files. In that mode, **Terraform — not TerraVision — is the component that needs credentials**, because Terraform's plan engine calls provider APIs to authenticate, look up data sources, and resolve computed values. TerraVision is a downstream consumer of plan output.

**Two operating modes:**

1. **Plan-from-source mode** (`terravision draw --source ./terraform`): TerraVision invokes Terraform, which calls cloud APIs to produce a plan. Cloud credentials are required by Terraform but never accessed or stored by TerraVision itself.
2. **Pre-generated plan mode** (`terravision draw --planfile plan.json --graphfile graph.dot --source ./terraform`): TerraVision consumes plan and graph files generated upstream (typically in a CI pipeline where Terraform already ran). **Zero cloud credentials of any kind are required.** This is the gold-standard path for high-security environments and air-gapped use.

For LLM-based AI refinement, only minimal aggregate metadata may be sent to backends — never sensitive code, secrets, or runtime values. Local AI backends (Ollama) MUST be available for environments that prohibit any external API calls.

**Rationale**: The clear separation between TerraVision (credential-free) and Terraform (the component that needs credentials when used) lets enterprises adopt TerraVision in environments where the security team controls credential boundaries. CI pipelines that already run `terraform plan` for review can pipe the resulting JSON directly into TerraVision in a separate, credential-free job, isolating the credential surface to a single existing pipeline step. State file backends are deliberately not read by TerraVision because that would re-introduce a credential dependency for a use case (diagram generation) that does not require it.

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

AI-powered diagram refinement MUST remain optional and support multiple backends (cloud-based, local). AI refinement MUST add missing connections, suggest meaningful diagram titles and external actors, generate numbered flow sequences where an end-to-end path exists, and enforce architectural conventions. Local AI options (Ollama) MUST be available for privacy-sensitive environments.

AI refinement MUST NOT modify the deterministic graph data (graphdict, tfdata) — all AI output MUST be expressed as a separate annotation artifact (e.g., `terravision.ai.yml`) or as positional-only edits to a laid-out DOT file that pass a strict validation gate before image generation.

**Rationale**: AI improves diagram quality by applying architectural best practices and detecting missing relationships, but must remain optional to support air-gapped environments. Multiple backend support allows organizations to choose between convenience (cloud) and privacy (local). Resource grouping/simplification was explicitly removed from the mandated capabilities in v1.7.0 because the risk of the AI hiding load-bearing resources outweighed the readability benefit; grouping may return as an opt-in capability in a future amendment once a safe heuristic is proven.

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

- **CO-001**: Cloud-specific configuration MUST be stored in `modules/config/cloud_config_<provider>.py` files (e.g., `cloud_config_aws.py`, `cloud_config_azure.py`, `cloud_config_gcp.py`)
- **CO-002**: Provider-specific resource handlers MUST be implemented in `modules/resource_handlers_<provider>.py` files (e.g., `resource_handlers_aws.py`, `resource_handlers_azure.py`, `resource_handlers_gcp.py`)
- **CO-003**: Common modules (e.g., `graphmaker.py`, `drawing.py`, `fileparser.py`, `interpreter.py`, `tfwrapper.py`) MUST NOT contain hardcoded provider-specific logic or resource types
- **CO-004**: Provider detection and configuration loading MUST use dynamic dispatch patterns to route to provider-specific implementations
- **CO-005**: New cloud provider support MUST follow the established pattern: create `cloud_config_<provider>.py` + `resource_handlers_<provider>.py` without modifying common modules

**Rationale**: Strict separation of provider-specific code from common infrastructure ensures maintainability, testability, and extensibility as new cloud providers are added. This architectural boundary prevents provider-specific logic from polluting shared modules and enables teams to add cloud support without risk of breaking existing providers.

#### Resource Handler Implementation Guidelines

**CRITICAL PRINCIPLE**: Most services DO NOT need custom handlers. TerraVision's core engine (Terraform graph parsing + relationship detection + icon mapping) produces accurate diagrams for the majority of resources. Only implement handlers when the baseline output is demonstrably insufficient.

**When to implement a handler** (ALL must be true):
1. The baseline diagram is confusing, inaccurate, or misleading for that resource type
2. Critical relationships are missing or incorrect
3. The issue cannot be fixed with general config (implied connections, edge nodes, etc.)
4. The pattern affects user comprehension of architecture

**When NOT to implement a handler**:
- Icons display correctly
- Relationships are clear from Terraform dependencies
- Resource placement is logical
- Users can understand the architecture without special handling

All resource handlers MUST follow a **config-first approach**, preferring declarative configuration over imperative Python code. Handlers MUST be implemented using the hybrid configuration-driven architecture in `modules/config/resource_handler_configs_<provider>.py`.

**Enforcement Rules**:

- **CO-005.1**: Most services MUST NOT have custom handlers - trust the baseline Terraform graph parsing
- **CO-006**: Resource handlers MUST be implemented as **Pure Config-Driven** (using only transformation building blocks) whenever possible
- **CO-007**: Resource handlers SHOULD use **Hybrid approach** (config transformations + custom Python function) when combining generic operations with unique logic
- **CO-008**: Resource handlers MAY use **Pure Function** (custom Python only) ONLY when logic is too complex to express declaratively (conditional logic with multiple branches, domain-specific parsing, selective filtering with complex rules)
- **CO-009**: Custom Python handler functions MUST include clear documentation explaining why config-driven approach was insufficient
- **CO-010**: New transformers SHOULD be added to `resource_transformers.py` when a pattern is reused across 2+ handlers
- **CO-011**: Handler configurations MUST include descriptive `description` field explaining purpose and handler type rationale
- **CO-012**: Parameters ending in `_function` or `_generator` in transformation configs are automatically resolved to function references - use this convention for all callable parameters
- **CO-013**: The transformer library SHOULD remain stable at ~30 operations and reach a saturation point that won't increase no matter how many cloud providers are supported. New transformers require justification that the pattern: (a) appears in 4+ handlers across 2+ cloud providers, (b) cannot be expressed by composing existing transformers, and (c) represents a fundamental graph operation not yet covered

**Decision Hierarchy** (attempt in order):
1. **Pure Config-Driven** - Use only existing transformers (70% code reduction, easiest to maintain)
2. **Hybrid** - Add new generic transformer if pattern is reusable, supplement with custom function for unique logic
3. **Pure Function** - Only for complex conditional logic that cannot be expressed declaratively

**Rationale**: TerraVision's core Terraform graph parsing handles most resources correctly without custom handlers. Adding handlers prematurely creates maintenance burden and complexity. When handlers ARE needed, config-driven approach reduces code by 70%, improves maintainability through reusable building blocks, and makes transformation logic transparent and testable. Requiring justification for imperative code prevents premature optimization and ensures the transformation library grows to handle common patterns. The automatic function resolution feature enables declarative configs to reference callable parameters without boilerplate. Limiting transformer growth to ~30 operations prevents DSL complexity while leveraging cross-provider reuse (3× multiplier for AWS/Azure/GCP). **Default to no handler; add only when baseline output is insufficient.**

### Quality Requirements

- **QR-001**: Architecture diagrams MUST be generated without requiring deployed infrastructure (work from `terraform plan`, not remote state)
- **QR-002**: Tool MUST handle large Terraform projects (200+ resources) efficiently with simplified diagram options
- **QR-003**: Tool MUST automatically download and parse organizational/external Terraform modules
- **QR-004**: Debug mode MUST export intermediate state (tfdata.json) for troubleshooting without re-running slow terraform operations
- **QR-005**: All CLI commands MUST support both human-readable and JSON output formats
- **QR-006**: Module cache and temporary files MUST use `~/.terravision` directory; cache MUST be clearable via `rm -rf ~/.terravision`

### Testing Standards

- **TS-001**: Changes MUST NOT break terraform plan parsing for supported Terraform versions (1.x)
- **TS-002**: Provider support additions MUST include icon library and resource mapping tests
- **TS-003**: Annotation functionality MUST be tested with valid and malformed YAML inputs
- **TS-004**: CI/CD integration examples MUST be validated against actual pipeline runners
- **TS-005**: Poetry MUST be used for dependency management; all Python commands in documentation and development MUST use `poetry run` prefix (e.g., `poetry run python terravision.py`, `poetry run pytest`)
- **TS-006**: Code MUST be formatted with Black using 88-character line length; CI MUST enforce formatting via `poetry run black --check -v modules`; violations MUST fail builds
- **TS-007**: Pre-commit hooks MUST run non-slow tests (`poetry run pytest -m "not slow"`); terraform-dependent tests MUST be marked with `@pytest.mark.slow`

## Validation System
A validation system has been implemented to enforce safeguards around expected JSON modifications. The process documented in BASELINE_VALIDATION_CHECKLIST.md, EXPECTED_JSON_MODIFICATION_POLICY.md, VALIDATION_FINDINGS.md and POST_IMPLEMENTATION_VALIDATION.md should be used before marking any tasks compelte.


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

**Version**: 1.6.0 | **Ratified**: 2025-12-07 | **Last Amended**: 2026-04-06
