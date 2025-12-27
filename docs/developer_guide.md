# Developer Guide

This file provides guidance to Devs seeking to improve Terravision.

## Project Overview

TerraVision is an AI-powered CLI tool that converts Terraform code into professional cloud architecture diagrams. It runs 100% client-side, securely parses Terraform plans, and generates visual representations of cloud infrastructure without requiring access to cloud environments.



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
python terravision.py draw --source <path>

# With AI refinement
python terravision.py draw --source <path> --aibackend bedrock
python terravision.py draw --source <path> --aibackend ollama

# Export graph data
python terravision.py graphdata --source <path> --outfile graph.json

# Debug mode (exports tfdata.json)
python terravision.py draw --source <path> --debug
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

TerraVision uses a hybrid configuration-driven approach for resource handlers. Handlers are defined in `RESOURCE_HANDLER_CONFIGS` dict in each `cloud_config_<provider>.py`:

**Three handler types:**

1. **Pure config-driven**: Use only transformation building blocks (7 AWS handlers)
2. **Hybrid**: Use transformations + custom Python function (0 AWS handlers currently)
3. **Pure function**: Use only custom Python function (9 AWS handlers)

```python
# modules/config/resource_handler_configs_aws.py
RESOURCE_HANDLER_CONFIGS = {
    # Pure config-driven
    "aws_vpc_endpoint": {
        "description": "Move VPC endpoints into VPC parent and delete endpoint nodes",
        "transformations": [
            {"operation": "move_to_parent", "params": {...}},
            {"operation": "delete_nodes", "params": {...}},
        ],
    },
    # Pure function
    "aws_security_group": {
        "description": "Process security group relationships and reverse connections",
        "additional_handler_function": "aws_handle_sg",
    },
}
```

The `handle_special_resources()` function in `graphmaker.py` executes:
1. Config-driven transformations (if `transformations` key exists)
2. Additional handler function (if `additional_handler_function` key exists)

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

### Configuration-Driven Handlers

TerraVision uses a hybrid approach for resource handlers:

**Pure config-driven** (simple operations):
```python
"aws_vpc_endpoint": {
    "transformations": [
        {"operation": "move_to_parent", "params": {...}},
        {"operation": "delete_nodes", "params": {...}},
    ],
}
```

**Pure function** (complex logic):
```python
"aws_security_group": {
    "additional_handler_function": "aws_handle_sg",
}
```

**Hybrid** (both config and custom logic):
```python
"aws_complex_resource": {
    "transformations": [{"operation": "expand_to_numbered_instances", "params": {...}}],
    "additional_handler_function": "aws_handle_complex_custom",
}
```

See `docs/CONFIGURATION_DRIVEN_HANDLERS.md` for details.

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
python terravision.py draw --source <path> --debug

# Inspect tfdata.json (contains all_resource, original_metadata, graphdict)
cat tfdata.json | jq '.graphdict'

# Replay from debug file (skips terraform init/plan)
python terravision.py draw --source tfdata.json
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
