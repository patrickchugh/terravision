<!--
Sync Impact Report - Constitution Update
========================================
Version: 0.1.0 → 1.0.0
Date: 2025-11-26
Type: MAJOR (initial constitution ratification)

Changes:
- Initial constitution created for TerraVision project
- Established 7 core principles
- Defined Python development standards
- Established testing and quality requirements
- Created governance framework

New Sections:
- Core Principles (7 principles)
- Development Standards
- Quality & Testing Requirements
- Governance

Template Consistency Status:
- ✅ plan-template.md: Constitution Check section references this file
- ✅ spec-template.md: Requirements align with principles
- ✅ tasks-template.md: Task organization supports test-first approach
- ⚠️  No command-specific templates found (N/A for this project)

Follow-up Actions:
- None - initial version complete
-->

# TerraVision Constitution

## Core Principles

### I. Client-Side Security First

TerraVision MUST operate 100% client-side without external API calls or cloud access requirements. All Terraform parsing, graph generation, and diagram rendering MUST execute locally. NO user code, credentials, or sensitive data may be transmitted externally. Only metadata (resource types, relationships) may be persisted to local files when explicitly requested via debug flags.

**Rationale**: Enterprise security requirements demand that infrastructure-as-code analysis tools never expose cloud credentials, configuration secrets, or architectural details to third parties. Client-side execution enables adoption in security-conscious organizations and air-gapped environments.

### II. Terraform Fidelity

Diagram accuracy MUST reflect the actual Terraform state through dynamic parsing of conditionally created resources, variable resolution, and module expansion. The system MUST support terraform plan output, variable files (.tfvars), workspaces, and remote git module sources. Diagrams MUST represent what will be deployed, not static approximations.

**Rationale**: Architecture diagrams lose value when they diverge from deployed reality. High-velocity releases make manually maintained diagrams obsolete instantly. Machine-generated diagrams from authoritative Terraform sources provide accuracy that freestyle diagrams cannot match.

### III. Extensibility Through Annotations

Auto-generated diagrams MUST be customizable via YAML annotations without modifying source code. The annotation system MUST support: diagram titles, custom labels, additional resources (unmanaged infrastructure), connection overrides (add/remove edges), and attribute modifications. Annotations MUST use Terraform resource naming conventions and support wildcards.

**Rationale**: No automated tool captures 100% of architectural context. Annotations enable users to augment generated diagrams with external systems, security zones, or business context while maintaining the 80-90% automation benefit and keeping annotations version-controlled alongside infrastructure code.

### IV. Multi-Provider Architecture

The codebase MUST support AWS, GCP, Azure, and on-premises resources through a provider abstraction layer. Provider-specific logic (resource handlers, icon mappings, consolidation rules, implied relationships) MUST be isolated in provider-specific modules. Core graph building, rendering, and CLI logic MUST remain provider-agnostic. New providers MUST be addable without modifying core modules.

**Rationale**: Cloud architectures increasingly span multiple providers and hybrid environments. Hard-coded AWS assumptions limit tool utility and create technical debt. Provider abstraction enables gradual multi-cloud support (AWS complete, GCP/Azure in progress) without breaking existing workflows.

### V. Docs-as-Code Integration

TerraVision MUST function as a CI/CD pipeline component generating architecture diagrams automatically after build/test/release phases. The CLI MUST support batch processing, multiple output formats (PNG, SVG, PDF), JSON graph export, and non-interactive execution. Output MUST be deterministic for version control and diffing.

**Rationale**: Manual diagram updates in fast-moving projects create bottlenecks and documentation drift. Automated diagram generation integrated with CI/CD keeps architecture documentation synchronized with deployments, enables diagram history tracking, and reduces manual toil.

### VI. Testability and Quality

All code MUST adhere to Black formatting (88-char line length), isort import ordering (skip drawing.py), and type hints for function signatures using the typing module. Tests MUST use pytest with unittest framework patterns. Pre-commit hooks MUST enforce linting. Python version support MUST target 3.9-3.11 strictly. Tests marked "slow" MUST be excludable for fast feedback loops.

**Rationale**: Consistent code style reduces cognitive load and review friction. Type hints catch errors early and serve as inline documentation. Fast test suites enable rapid iteration while comprehensive tests (including slow integration tests) ensure correctness. Strict Python version targeting prevents compatibility issues with enterprise environments.

### VII. Simplicity and Dependency Minimalism

External dependencies MUST be justified and minimal. REQUIRED: Terraform 1.x (core functionality), Graphviz (rendering), Git (module fetching), Python 3.9+ (runtime). Python dependencies managed via Poetry for developers, requirements.txt for users. NO unnecessary abstractions, frameworks, or complexity that obscure Terraform → Graph → Diagram data flow. Code MUST prioritize readability over cleverness.

**Rationale**: Each dependency introduces installation friction, security surface, and maintenance burden. TerraVision's value proposition includes "works instantly from your local machine" and "no cloud resources required." Lean dependencies support this. Simplicity in data structures (tfdata dict with graphdict/metadata keys) enables debugging and extension by contributors.

## Development Standards

### Code Organization

- **Module imports**: Group standard library, third-party, then local modules. Use `import modules.X as X` pattern for internal modules
- **Data structures**: Primary data container is `tfdata` dict with keys: `graphdict`, `metadata`, `all_resource`, `annotations`
- **Click CLI framework**: All commands use @click decorators with clear help text and defaults
- **Error handling**: Use click.echo() with click.style() for user-facing errors (fg="red", bold=True), sys.exit() for fatal errors
- **Exception suppression**: Use contextlib.suppress() for expected exceptions (e.g., JSON parsing)
- **File operations**: Use pathlib.Path for paths, tempfile for temporary directories

### Python Code Style

- **Python version**: Target 3.9-3.11 strictly (enforced by pyproject.toml)
- **Formatting**: Black with 88-char line length (exception: skip isort for drawing.py per pyproject.toml)
- **Type hints**: Use typing module annotations (Dict[str, Any], List, Optional, Tuple) for all function signatures
- **Docstrings**: Google-style docstrings for modules and functions with Args/Returns sections
- **Naming conventions**: snake_case for functions/variables, UPPER_CASE for module-level constants from cloud_config
- **Special patterns**: Extract provider-specific constants to cloud_config modules (AWS_CONSOLIDATED_NODES, etc.)

## Quality & Testing Requirements

### Testing Strategy

- **Framework**: pytest with unittest.TestCase patterns for class-based tests
- **Test organization**: tests/ directory with unit tests, integration tests (marked @pytest.mark.slow for heavy Terraform operations)
- **Fast feedback**: Default `pytest` runs non-slow tests; use `pytest -m "not slow"` explicitly
- **Pre-commit integration**: Pre-commit hooks run pytest on non-slow tests automatically
- **Coverage**: Critical paths (Terraform parsing, graph building, provider detection) MUST have unit test coverage

### Commands

- **Install**: `poetry install` (dev) or `pip install -r requirements.txt` (users)
- **Run all tests**: `poetry run pytest`
- **Run fast tests**: `poetry run pytest -m "not slow"`
- **Format**: `poetry run black .` and `poetry run isort .`
- **Pre-commit**: `poetry run pre-commit run --all-files`
- **Single test**: `poetry run pytest tests/helpers_unit_test.py::TestGetvar::test_getvar_from_dict -v`

### Quality Gates

- Pre-commit hooks MUST pass before commits are accepted
- No lint warnings from Black/isort
- All non-slow tests MUST pass before merges to main
- Type hints MUST be present on public functions
- New provider-specific features MUST include provider isolation (no bleeding into core modules)

## Governance

This constitution supersedes all other development practices and serves as the authoritative source for architectural decisions, coding standards, and quality requirements.

### Amendment Process

1. **Proposal**: Constitution changes MUST be proposed with clear rationale and impact analysis
2. **Review**: Technical lead or maintainers MUST review for alignment with project mission
3. **Documentation**: Amendments MUST update this file with version bump and change log
4. **Migration**: Breaking changes MUST include migration guide or backward compatibility plan

### Versioning Policy

Constitution follows semantic versioning:
- **MAJOR**: Breaking architectural changes, removed principles, or incompatible governance shifts
- **MINOR**: New principles added, expanded guidance, new sections that add requirements
- **PATCH**: Clarifications, wording improvements, typo fixes, non-semantic refinements

### Compliance

- All PRs and code reviews MUST verify adherence to these principles
- Architecture changes that violate principles MUST be explicitly justified and documented
- Complexity (new abstractions, dependencies, provider-specific bleeding into core) MUST be justified against Section VII (Simplicity)
- Use AGENTS.md for runtime development guidance (build commands, test execution)
- Constitution violations found in existing code SHOULD be tracked as technical debt and remediated incrementally

**Version**: 1.0.0 | **Ratified**: 2025-11-26 | **Last Amended**: 2025-11-26
