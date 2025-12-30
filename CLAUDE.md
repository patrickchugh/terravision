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
10. detect_and_set_counts() → Set synthetic count for multi-instance resources
11. handle_special_resources() → VPC, subnet, security group logic
12. handle_variants() → Add resource variants (Lambda runtime, EC2 type)
13. create_multiple_resources() → Handle count/for_each (resource~1, resource~2)
14. reverse_relations() → Fix arrow directions
15. (Optional) _refine_with_llm() → AI diagram refinement
16. render_diagram()  → Generate Graphviz output
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

**detect_multi_instance_resources.py**: Configuration-driven detection of resources requiring synthetic count. Detects resources deployed across multiple subnets/zones/networks without explicit Terraform count, sets synthetic count attribute for automatic numbering.

### Multi-Instance Resource Detection

**Purpose**: Automatically detect and number resources that span multiple availability zones, subnets, or networks but lack explicit Terraform `count` or `for_each` attributes.

**How it works**:
1. Scans Terraform configuration for resources matching configured patterns
2. Checks if trigger attributes (e.g., `subnets`, `zones`) contain multiple references
3. Sets synthetic `count` equal to number of references
4. Optionally expands associated resources (e.g., security groups)
5. Lets `create_multiple_resources()` handle numbering naturally

**Configuration location**: `modules/detect_multi_instance_resources.py` → `MULTI_INSTANCE_PATTERNS`

**Adding new patterns**:
```python
MULTI_INSTANCE_PATTERNS = {
    "aws": [
        {
            "resource_types": ["aws_lb", "aws_alb", "aws_nlb"],
            "trigger_attributes": ["subnets"],  # Trigger if len > 1
            "also_expand_attributes": ["security_groups"],  # Also set count for these
            "resource_pattern": r"\$\{(aws_\w+\.\w+)",  # Regex to extract references
            "description": "ALB/NLB spanning multiple subnets",
        },
        # Add more AWS patterns...
    ],
    "azure": [
        {
            "resource_types": ["azurerm_lb"],
            "trigger_attributes": ["zones"],
            "also_expand_attributes": [],
            "resource_pattern": r'"([^"]+)"',  # Zones are strings
            "description": "Azure Load Balancer with multiple zones",
        },
        # Add more Azure patterns...
    ],
    # Add more providers...
}
```

**Example**: AWS ALB with `subnets = [subnet_a, subnet_b]` triggers count=2, creating `aws_alb.elb~1` and `aws_alb.elb~2`.

### Resource Handlers Pattern

**⚠️ CRITICAL PRINCIPLE**: Most services DO NOT need custom handlers. TerraVision's core engine (Terraform graph parsing + relationship detection + icon mapping) produces accurate diagrams for the majority of resources. **Default to no handler; add only when baseline output is demonstrably insufficient.**

**⚠️ MANDATORY VALIDATION BEFORE IMPLEMENTING HANDLERS**:

**📋 Complete the full validation checklist**: See `docs/BASELINE_VALIDATION_CHECKLIST.md` for the comprehensive validation process.

Before implementing ANY handler, you MUST complete this validation process:

1. **Generate Baseline Diagram**:
   - Create real Terraform code for the resource type
   - Run TerraVision WITHOUT any custom handler
   - Save the output graph JSON

2. **Analyze Baseline Output**:
   - Are the resources visible? (icons, labels)
   - Are the connections correct? (arrows show dependencies)
   - Is the hierarchy clear? (VPC → subnet → resources)
   - Can users understand the architecture?

3. **Decision**:
   - ✅ If baseline is clear → **STOP! No handler needed.**
   - ❌ If baseline is confusing → Document specific issues, proceed to handler

4. **Document Justification**:
   - What specific diagram problem does the handler solve?
   - Include baseline output vs. expected output comparison
   - Cannot be subjective "looks better" - must fix actual confusion/inaccuracy

**Example - API Gateway (Handler NOT Needed)**:
- Baseline shows: `Lambda → Integration → Method → Resource → API`
- This is clear and accurate!
- Custom handler trying to parse URIs added complexity for no benefit
- Result: No handler implemented ✅

**Example - Security Groups (Handler Needed)**:
- Baseline shows: `EC2 → Security Group` (simple dependency)
- Missing: Ingress/egress rules, which SG allows which traffic
- Problem: Can't understand network security model
- Result: Custom handler parses rules, adds directional arrows ✅

**When to implement a handler** (ALL must be true):
1. Baseline diagram is confusing, inaccurate, or misleading
2. Critical relationships are missing or incorrect
3. Cannot be fixed with general config (implied connections, edge nodes)
4. Pattern affects user comprehension

**When NOT to implement a handler**:
- Icons display correctly ✓
- Relationships clear from Terraform dependencies ✓
- Resource placement is logical ✓
- Architecture is understandable ✓

**Examples of services that DON'T need handlers**:
- `aws_s3_bucket` - Icon displays, connections from Lambda/EC2 work via Terraform graph
- `aws_dynamodb_table` - Relationships to Lambda work automatically
- `aws_sqs_queue` - Standard queue-to-Lambda pattern works without handler
- Most compute, storage, and database services work fine with baseline parsing

**Examples of services that DO need handlers**:
- `aws_security_group` - Bidirectional relationships + numbered resource matching (complex logic)
- `aws_vpc` / `aws_subnet` - Hierarchical containment (VPC → AZ → Subnet) not in Terraform graph
- `aws_api_gateway_rest_api` - Sub-resources need consolidation + integration parsing

TerraVision uses a **config-driven resource handler architecture** per constitution CO-005.1 through CO-013 that supports three handler types:

#### Constitutional Requirements (CO-005.1 through CO-013)

- **CO-005.1**: Most services MUST NOT have custom handlers - trust baseline Terraform graph parsing

- **CO-006**: Handlers MUST be Pure Config-Driven whenever possible
- **CO-007**: Handlers SHOULD use Hybrid approach when combining generic operations with unique logic
- **CO-008**: Handlers MAY use Pure Function ONLY when logic is too complex for declarative expression
- **CO-009**: Custom functions MUST document why config-driven was insufficient
- **CO-010**: New transformers added when pattern reused across 3+ handlers
- **CO-011**: Configurations MUST include descriptive `description` field
- **CO-012**: Parameters ending in `_function` or `_generator` auto-resolve to function references
- **CO-013**: Transformer library SHOULD remain stable at ~30 operations (currently 24)

#### Handler Types

**Decision Hierarchy** (attempt in order):
1. Pure Config-Driven (preferred)
2. Hybrid (common)
3. Pure Function (only when necessary)

**Current AWS Handler Distribution**:
- **Pure Config-Driven**: ~7% (e.g., `aws_eks_node_group`, `aws_elasticache_replication_group`)
- **Hybrid**: ~79% (e.g., `aws_subnet`, `aws_cloudfront_distribution`, `aws_api_gateway_rest_api`)
- **Pure Function**: ~14% (e.g., `aws_security_group`, `aws_lb`, `aws_sfn_state_machine`)

**1. Pure Config-Driven** (Preferred)
- Uses only declarative transformation building blocks (24 available transformers)
- Defined in `modules/config/resource_handler_configs_aws.py`
- Example: `aws_elasticache_replication_group` (expansion + suffix matching)
- **When to use**: Pattern matches existing transformers exactly

**2. Hybrid** (Most Common)
- Uses transformations + custom Python function
- Transformations run first (or last via `handler_execution_order`)
- Examples:
  - `aws_subnet` (metadata prep + insert_intermediate_node transformer)
  - `aws_cloudfront_distribution` (link transformers + origin parsing)
  - `aws_api_gateway_rest_api` (consolidation + integration URI parsing)
- **When to use**: Generic operations + unique parsing/matching logic

**3. Pure Function** (Complex Logic Only)
- Uses only custom Python code
- Defined in `resource_handlers_aws.py`, referenced in config
- Examples: `aws_security_group`, `aws_sfn_state_machine` (JSON parsing)
- **When to use**: Complex conditional logic with multiple branches that transformers cannot express declaratively

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

**Follow config-driven architecture per CO-006 through CO-013**:

1. Create `modules/config/resource_handler_configs_<provider>.py` with handler configurations (PRIMARY)
2. Create `modules/config/cloud_config_<provider>.py` with provider constants (edge nodes, icon library, etc.)
3. Create `modules/resource_handlers_<provider>.py` with custom functions (ONLY for Hybrid/Pure Function handlers)
4. Add provider prefix to `PROVIDER_PREFIXES` in `provider_detector.py`
5. Add icons to `resource_classes/<provider>/`
6. Update tests in `tests/test_provider_detection.py`

**Cross-Provider Reusability**: Aim for 70-80% transformer reuse across providers. Example: `expand_to_numbered_instances` used for AWS EKS → Azure AKS → GCP GKE node groups.

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

### In `resource_handler_configs_<provider>.py` (PRIMARY - Config-Driven)

- `RESOURCE_HANDLER_CONFIGS`: Dict mapping resource types to handler configurations
  - Pure Config-Driven: Only `transformations` array
  - Hybrid: `transformations` + `additional_handler_function`
  - Pure Function: Only `additional_handler_function`
  - All require `description` field explaining handler type rationale (CO-011)

### In `cloud_config_<provider>.py` (SECONDARY - Provider Constants)

- `PROVIDER_PREFIX`: Resource name prefix(es) (e.g., `["aws_"]` or `["azurerm_", "azuread_"]`)
- `ICON_LIBRARY`: Path to icon directory
- `EDGE_NODES`: Resources at diagram boundaries (API Gateway, CloudFront, etc.)
- `GROUP_NODES`: Resources that create subgraphs (VPCs, resource groups)
- `NODE_VARIANTS`: Resources with variants (Lambda runtime, EC2 type)
- `IMPLIED_CONNECTIONS`: Keywords that imply connections
- `REVERSE_ARROW_LIST`: Resources requiring reversed arrow direction
- `FORCED_DEST/FORCED_ORIGIN`: Resources with fixed connection direction
- `SHARED_SERVICES`: Resources shared across modules (IAM roles, etc.)
- `AUTO_ANNOTATIONS`: Auto-applied labels

**Deprecated (Legacy)**:
- `SPECIAL_RESOURCES`: Replaced by `RESOURCE_HANDLER_CONFIGS` in handler config files
- `HIDE_NODES`: Now defined in `RESOURCE_HANDLER_CONFIGS` via `delete_nodes` transformer

**⚠️ IMPORTANT**: For resource consolidation (merging multiple resources into one node), use `CONSOLIDATED_NODES` directly in `cloud_config_<provider>.py`. DO NOT use transformers for consolidation - the `consolidate_into_single_node` transformer was removed in favor of the simpler, centralized `CONSOLIDATED_NODES` mechanism.

## Testing Philosophy

- **Unit tests**: Test individual functions in isolation (`tests/*_unit_test.py`)
- **Integration tests**: Test full pipeline with real Terraform code (`tests/integration_test.py`)
- **Provider tests**: Validate provider detection and config loading (`tests/test_provider_detection.py`, `tests/test_config_loader.py`)
- **Validation tests**: Test output quality and catch rendering issues (`tests/test_validation.py`)
- **Mark slow tests**: Use `@pytest.mark.slow` for tests that run terraform commands

## Graph Validation

**CRITICAL**: TerraVision includes validation checks to catch common issues that cause rendering problems or incorrect diagrams.

### Validation Functions (modules/helpers.py)

- `validate_no_shared_connections()`: Detects when multiple groups (subnets, AZs) share connections to the same resource, which causes graphviz rendering issues
- `validate_graphdict()`: Aggregates all validation checks

### Shared Connection Violations

**Problem**: When multiple group nodes point to the same resource, graphviz cannot render correctly.

Example violation:
```json
{
  "aws_subnet.a": ["aws_instance.web"],
  "aws_subnet.b": ["aws_instance.web"]
}
```

**Solution**: Resources must be expanded into numbered instances:
```json
{
  "aws_subnet.a": ["aws_instance.web~1"],
  "aws_subnet.b": ["aws_instance.web~2"],
  "aws_instance.web~1": [],
  "aws_instance.web~2": []
}
```

### Running Validation

Validation tests run automatically in `tests/test_validation.py`:
- `test_no_shared_connections_in_expected_outputs`: Validates all expected JSON files
- These tests should NEVER be skipped or modified to pass
- If validation fails, fix the handler to expand resources, don't regenerate expected JSON

### When Implementing Handlers

Before marking a task complete:
1. Run validation tests: `poetry run pytest tests/test_validation.py -v`
2. If validation fails, resources need to be expanded into numbered instances
3. Add expansion logic to the handler (see numbered resources pattern below)
4. DO NOT regenerate expected JSON to bypass validation

## Expected JSON Modification Policy

**CRITICAL RULE**: Expected test outputs (`tests/json/expected-*.json`) should RARELY be modified. When tests fail, the default assumption is that the code has a bug, NOT that the expected output is wrong.

See `docs/EXPECTED_JSON_MODIFICATION_POLICY.md` for complete policy.

### Quick Rules

✅ **ONLY modify expected JSON when**:
- Adding a new test case for a new feature
- Explicit user request to change rendering behavior
- Bug fix that improves accuracy (with user approval)
- Validation failure with approved fix

❌ **NEVER modify expected JSON to**:
- Make failing tests pass without investigation
- Fix side effects from other changes without fixing the handler
- Bypass validation failures
- "Improve" output without user approval

### Required Process

1. **Investigate WHY test failed** (don't just look at the diff)
2. **Get user approval** before modifying expected JSON
3. **Document thoroughly** in commit message
4. **Validate no regressions** after modification

### Red Flags

🚩 Batch regeneration of multiple expected files
🚩 "Tests failed → Regenerate expected → Tests pass ✓"
🚩 No investigation of root cause
🚩 "Looks fine to me" without user approval

**If in doubt, ask the user before modifying expected JSON.**

## Known Constraints

- Terraform must be v1.x (v0.x not supported)
- Requires external dependencies: Graphviz (`dot`), Git, Terraform
- Security groups require special handling due to complex ingress/egress rules
- Module paths must be resolvable (Git URLs cloned to `~/.terravision/`)
- JSON debug files from different TerraVision versions may not be compatible
