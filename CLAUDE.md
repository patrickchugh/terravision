# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TerraVision is an AI-powered CLI tool that converts Terraform code into professional cloud architecture diagrams. It runs 100% client-side, securely parses Terraform plans, and generates visual representations of cloud infrastructure without requiring access to cloud environments.

## Documentation Location

All project documentation, specifications, design artifacts, and templates are located in the `/docs` folder. When using speckit skills (`/speckit.*` commands) or referencing project documentation:
- Specifications and feature docs are in `/docs`
- Design templates and planning artifacts are in `/docs`
- All speckit commands should reference and write to `/docs`

**Configuration**: The speckit documentation directory is configured via the `SPECS_DIR` environment variable in `.claude/settings.json`:
```json
"env": {
  "SPECS_DIR": "./docs"
}
```

This ensures all `/speckit.*` commands (specify, plan, tasks, etc.) create and read documents from `./docs` instead of the default `/specs` directory.

## Virtual Environment

**CRITICAL**: This project uses Poetry for dependency management. **ALWAYS** use `poetry run` prefix for all Python commands.

```bash
# ✅ CORRECT - Always use poetry run
poetry run python terravision.py draw --source <path>

# ❌ WRONG - Never run directly
python terravision.py draw --source <path>
```

## Commands

### Development Setup

```bash
# Poetry installation (recommended for development)
poetry install
poetry shell

# Quick install (global packages)
pip install -r requirements.txt
```

### Running TerraVision

```bash
# Basic diagram generation
poetry run python terravision.py draw --source <path>

# With AI refinement
poetry run python terravision.py draw --source <path> --aibackend bedrock
poetry run python terravision.py draw --source <path> --aibackend ollama

# Export graph data
poetry run python terravision.py graphdata --source <path> --outfile graph.json

# Debug mode (exports tfdata.json)
poetry run python terravision.py draw --source <path> --debug
```

### Testing

```bash
# Run all tests
poetry run pytest tests -v

# Run non-slow tests (for pre-commit)
poetry run pytest -m "not slow"

# Run specific test file
poetry run pytest tests/test_provider_detection.py -v

# Run with coverage
poetry run pytest tests --cov=modules
```

### Linting and Formatting

```bash
# Check formatting (CI enforced)
poetry run black --check -v modules

# Auto-format code
poetry run black modules

# Run pre-commit hooks
pre-commit run --all-files
```

### Building and Releasing

```bash
# Verify dependencies
dot --version      # Graphviz
terraform version  # Must be v1.x
git --version

# Clean cache (troubleshooting)
rm -rf ~/.terravision
```

## Architecture

### Multi-Cloud Provider Support

TerraVision supports AWS (full), GCP (partial), and Azure (partial). The architecture uses **dynamic provider detection** and **configuration loading**:

1. **Provider Detection** (`modules/provider_detector.py`): Analyzes Terraform resource prefixes (`aws_`, `azurerm_`, `google_`) to identify cloud providers
2. **Configuration Loader** (`modules/config_loader.py`): Dynamically loads provider-specific configs at runtime
3. **Provider Configs** (`modules/config/cloud_config_*.py`): Each provider has isolated configuration defining icons, relationships, special resources

**Key Pattern:**
```python
# Detection happens once during compilation
provider_detection = detect_providers(tfdata)
tfdata["provider_detection"] = provider_detection

# Throughout codebase, load provider-specific config
provider = get_primary_provider_or_default(tfdata)
config = load_config(provider)  # Returns cloud_config_aws, cloud_config_azure, or cloud_config_gcp
```

### Core Pipeline (compile_tfdata)

The main processing pipeline in `terravision.py` follows this flow:

```
1. tf_initplan()      → Initialize Terraform, run plan
2. tf_makegraph()     → Generate Terraform graph
3. read_tfsource()    → Parse .tf files with HCL2
4. prefix_module_names() → Handle Terraform modules
5. resolve_all_variables() → Interpolate variables
6. handle_special_cases() → Provider-specific resource processing
7. add_relations()    → Detect resource dependencies
8. consolidate_nodes() → Merge similar resources
9. add_annotations()  → Apply custom YAML annotations
10. handle_special_resources() → VPC, subnet, security group logic
11. handle_variants() → Add resource variants (Lambda runtime, EC2 type)
12. create_multiple_resources() → Handle count/for_each (resource~1, resource~2)
13. reverse_relations() → Fix arrow directions
14. (Optional) _refine_with_llm() → AI diagram refinement
15. render_diagram()  → Generate Graphviz output
```

### Key Modules

**tfwrapper.py**: Terraform wrapper executing `terraform init`, `plan`, `graph`. Downloads remote modules, handles workspaces, processes terraform.tfvars.

**fileparser.py**: Parses .tf files using python-hcl2, extracts resources, variables, modules, outputs.

**interpreter.py**: Resolves Terraform variables, interpolations, expressions. Handles complex scenarios like `count`, `for_each`, module variables.

**graphmaker.py**: Core graph construction. Detects relationships by scanning resource attributes for references to other resources. Handles numbered resources (`resource~1`, `resource~2`) for count > 1.

**resource_handlers.py**: Dispatcher for provider-specific resource handlers. Routes to `resource_handlers_aws.py`, `resource_handlers_gcp.py`, or `resource_handlers_azure.py`.

**resource_handlers_aws.py / _gcp.py / _azure.py**: Provider-specific logic for VPCs, subnets, security groups, networks. Each has functions like `handle_vpc()`, `handle_subnet()`, `handle_security_group()`.

**drawing.py**: Renders final Graphviz diagram. Uses provider-specific icon libraries, applies styling, handles subgraphs (VPCs, availability zones).

**annotations.py**: Processes custom YAML annotations (`terravision.yml`) to add/remove/update nodes and connections.

**helpers.py**: Utility functions for node manipulation, JSON extraction, resource matching.

### Resource Handlers Pattern

TerraVision uses a **config-driven resource handler architecture** that supports three handler types:

#### Handler Types

**1. Pure Config-Driven** (7 AWS handlers)
- Uses only declarative transformation building blocks
- Defined in `modules/config/resource_handler_configs_aws.py`
- Example: `aws_vpc_endpoint`, `aws_eks_node_group`, `aws_db_subnet_group`
- **When to use**: Simple, repetitive operations (move, link, delete, expand)

**2. Hybrid** (3 AWS handlers)
- Uses transformations + custom Python function
- Transformations run first (or last via `handler_execution_order`)
- Examples:
  - `aws_subnet` (metadata prep + insert_intermediate_node transformer)
  - `aws_cloudfront_distribution` (link transformers + origin parsing)
  - `aws_efs_file_system` (bidirectional_link + custom cleanup)
- **When to use**: Common operations + unique logic

**3. Pure Function** (6 AWS handlers)
- Uses only custom Python code
- Defined in `resource_handlers_aws.py`, referenced in config
- Examples: `aws_security_group`, `aws_lb`, `aws_appautoscaling_target`
- **When to use**: Complex conditional logic, domain-specific patterns that don't map to generic transformers

#### Configuration Location

All handlers are defined in `modules/config/resource_handler_configs_<provider>.py`:

```python
RESOURCE_HANDLER_CONFIGS = {
    # Pure Config-Driven
    "aws_vpc_endpoint": {
        "description": "Move VPC endpoints into VPC parent and delete endpoint nodes",
        "transformations": [
            {"operation": "move_to_parent", "params": {...}},
            {"operation": "delete_nodes", "params": {...}},
        ],
    },

    # Hybrid (transformations + custom function)
    "aws_subnet": {
        "description": "Create availability zone nodes and link to subnets",
        "handler_execution_order": "before",  # Run custom function FIRST
        "additional_handler_function": "aws_prepare_subnet_az_metadata",
        "transformations": [
            {"operation": "insert_intermediate_node", "params": {...}},
        ],
    },

    # Pure Function
    "aws_security_group": {
        "description": "Process security group relationships and reverse connections",
        "additional_handler_function": "aws_handle_sg",
    },
}
```

#### Execution Order

By default, transformations run first, then the custom handler function. Use `handler_execution_order: "before"` to reverse this:

```python
"handler_execution_order": "before",  # Run custom function BEFORE transformations
"handler_execution_order": "after",   # Run custom function AFTER transformations (default)
```

#### Legacy Pattern (Deprecated)

The old `AWS_SPECIAL_RESOURCES` dict in `cloud_config_*.py` is deprecated in favor of the config-driven approach:

```python
# OLD (Deprecated)
AWS_SPECIAL_RESOURCES = {
    "aws_vpc": "handle_vpc",
    "aws_subnet": "handle_subnet",
}
```

The `handle_special_resources()` function in `graphmaker.py` now uses `RESOURCE_HANDLER_CONFIGS` from the config files.

### Numbered Resources (Count/For_Each)

Resources with `count > 1` or `for_each` are expanded into numbered instances with `~` suffix:

- `aws_instance.web` with count=3 becomes `aws_instance.web~1`, `aws_instance.web~2`, `aws_instance.web~3`
- Connections are matched by suffix: `web~1 → db~1`, `web~2 → db~2`
- Security groups are extended to match numbered resources they protect

### AI Refinement Backends

Two AI backends refine diagrams:

**Bedrock**: AWS API Gateway + Lambda + Bedrock (infrastructure in `ai-backend-terraform/`)
**Ollama**: Local llama3 model (localhost:11434)

Both use provider-specific prompts from `cloud_config_*.py` (`AWS_REFINEMENT_PROMPT`, `AZURE_REFINEMENT_PROMPT`, etc.) to fix groupings and connections.

### Icon Libraries

Icons are sourced from provider-specific directories defined in each config:

- AWS: `resource_classes/aws/` (200+ services)
- Azure: `resource_classes/azure/`
- GCP: `resource_classes/gcp/`
- Generic: `resource_classes/generic/` (fallback icons)

## Important Patterns

### Adding New Cloud Provider

1. Create `modules/config/cloud_config_<provider>.py` with required constants
2. Create `modules/resource_handlers_<provider>.py` with handler functions
3. Add provider prefix to `PROVIDER_PREFIXES` in `provider_detector.py`
4. Add icons to `resource_classes/<provider>/`
5. Update tests in `tests/test_provider_detection.py`

### Testing Provider-Specific Code

When modifying provider-specific functionality, always run:
```bash
poetry run pytest tests/test_provider_detection.py -v
poetry run pytest tests/test_config_loader.py -v
poetry run pytest tests/test_<provider>_resources.py -v
```

### Debug Workflow

When debugging Terraform parsing issues:
```bash
# Generate debug output
poetry run python terravision.py draw --source <path> --debug

# Inspect tfdata.json (contains all_resource, original_metadata, graphdict)
cat tfdata.json | jq '.graphdict'

# Replay from debug file (skips terraform init/plan)
poetry run python terravision.py draw --source tfdata.json
```

### Pre-commit Hooks

The repo uses pre-commit to run pytest on non-slow tests before each commit. Hook defined in `.pre-commit-config.yaml`.

## CI/CD

GitHub Actions workflow (`.github/workflows/lint-and-test.yml`) runs on push/PR to main:

1. Installs Poetry, Python 3.11, Terraform, Graphviz
2. Runs Black formatter check on `modules/` directory
3. Executes pytest test suite
4. Uses AWS OIDC for integration tests requiring AWS credentials

## Configuration Files

**pyproject.toml**: Poetry dependencies, Black config (line-length 88), isort config
**requirements.txt**: Pip fallback for non-Poetry users
**.pre-commit-config.yaml**: Pre-commit hook running pytest
**.github/workflows/lint-and-test.yml**: CI pipeline

## Critical Constants

Each `cloud_config_*.py` defines these provider-specific constants:

- `PROVIDER_PREFIX`: Resource name prefix(es) (e.g., `["aws_"]` or `["azurerm_", "azuread_"]`)
- `ICON_LIBRARY`: Path to icon directory
- `SPECIAL_RESOURCES`: Dict mapping resource types to handler functions
- `GROUP_NODES`: Resources that create subgraphs (VPCs, resource groups)
- `CONSOLIDATED_NODES`: Resources to merge into single nodes
- `NODE_VARIANTS`: Resources with variants (Lambda runtime, EC2 type)
- `IMPLIED_CONNECTIONS`: Keywords that imply connections
- `REVERSE_ARROW_LIST`: Resources requiring reversed arrow direction
- `FORCED_DEST/FORCED_ORIGIN`: Resources with fixed connection direction
- `SHARED_SERVICES`: Resources shared across modules (IAM roles, etc.)
- `EDGE_NODES`: Resources at diagram boundaries
- `AUTO_ANNOTATIONS`: Auto-applied labels

## Testing Philosophy

- **Unit tests**: Test individual functions in isolation (`tests/*_unit_test.py`)
- **Integration tests**: Test full pipeline with real Terraform code (`tests/integration_test.py`)
- **Provider tests**: Validate provider detection and config loading (`tests/test_provider_detection.py`, `tests/test_config_loader.py`)
- **Mark slow tests**: Use `@pytest.mark.slow` for tests that run terraform commands

## Known Constraints

- Terraform must be v1.x (v0.x not supported)
- Requires external dependencies: Graphviz (`dot`), Git, Terraform
- Security groups require special handling due to complex ingress/egress rules
- Module paths must be resolvable (Git URLs cloned to `~/.terravision/`)
- JSON debug files from different TerraVision versions may not be compatible
