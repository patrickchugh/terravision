# Contributing to TerraVision

Thank you for your interest in contributing to TerraVision! This document provides guidelines and best practices for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [AI-Assisted Development](#ai-assisted-development)
- [Architecture Guidelines](#architecture-guidelines)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment for all contributors.

## Getting Started

### Prerequisites

Ensure you have the following installed:

- Python 3.11+
- Terraform v1.x (v0.x not supported)
- Graphviz (`dot` command)
- Git
- Poetry (recommended) or pip
- Ollama (for local AI testing)
- AWS account (for bedrock AI testing)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install dependencies with Poetry (recommended)
poetry install
poetry shell

# Install pre-commit hooks
pre-commit install

# Verify installation
python terravision.py --help
```

### Running Tests

```bash
# Run all tests
poetry run pytest tests -v

# Run non-slow tests (for quick validation)
poetry run pytest -m "not slow"

# Run specific test file
poetry run pytest tests/test_provider_detection.py -v

# Run with coverage
poetry run pytest tests --cov=modules
```

## Development Workflow

1. **Fork the repository** and create a feature branch from `main`
2. **Make your changes** following the code standards below
3. **Write tests** for new functionality
4. **Run the test suite** to ensure all tests pass
5. **Format your code** with Black
6. **Submit a pull request** to the `main` branch

### Branch Naming

Use descriptive branch names:

- `feature/add-azure-support`
- `fix/security-group-parsing`
- `docs/update-readme`
- `refactor/provider-detection`

### Commit Messages

Write clear, descriptive commit messages:

```
Add support for GCP Cloud Run resources

- Implement Cloud Run handler in resource_handlers_gcp.py
- Add Cloud Run icons to resource_classes/gcp/
- Update cloud_config_gcp.py with special resources
- Add integration tests for Cloud Run
```

## Code Standards

### Python Style Guide

TerraVision uses **Black** for code formatting with the following configuration:

- Line length: 88 characters
- Follow PEP 8 conventions
- Use type hints where appropriate
- Write docstrings for public functions

### Formatting

```bash
# Check formatting (what CI runs)
poetry run black --check -v modules

# Auto-format code
poetry run black modules

# Run all pre-commit hooks
pre-commit run --all-files
```

### Code Organization

- **Provider-specific code** goes in `modules/config/cloud_config_<provider>.py` and `modules/resource_handlers_<provider>.py`
- **Shared utilities** belong in `modules/helpers.py`
- **Icons** are stored in `resource_classes/<provider>/`
- **Tests** mirror the module structure in `tests/`

### Import Order

Use isort conventions (automatically applied by pre-commit):

1. Standard library imports
2. Third-party imports
3. Local application imports

## Testing Requirements

### Test Coverage

- All new features must include tests
- Bug fixes should include regression tests
- Aim for >80% code coverage on new code

### Test Types

**Unit Tests** (`tests/*_unit_test.py`):

```python
def test_provider_detection():
    tfdata = {"all_resource": [{"type": "aws_instance"}]}
    result = detect_providers(tfdata)
    assert "aws" in result["providers"]
```

**Integration Tests** (`tests/integration_test.py`):

- Test the full pipeline with real Terraform code
- Mark as slow: `@pytest.mark.slow`

**Provider Tests** (`tests/test_<provider>_*.py`):

- Validate provider-specific functionality
- Test config loading and resource handlers

### Running Tests Locally

Before submitting a PR, ensure:

```bash
# All tests pass
poetry run pytest tests -v

# Code is formatted
poetry run black --check -v modules

# Pre-commit hooks pass
pre-commit run --all-files
```

## Pull Request Process

### Before Submitting

- [ ] Code follows Black formatting standards
- [ ] All tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated (README.md, CLAUDE.md if architecture changed)
- [ ] Pre-commit hooks pass
- [ ] No unnecessary dependencies added
- [ ] AI assistance disclosed (see below)

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## AI Assistance
- Tools used: [e.g., Claude Code, GitHub Copilot]
- Model: [e.g., Claude Sonnet 4.5, GPT-4]
- Scope: [e.g., "Generated test cases", "Refactored function X"]

## Checklist
- [ ] Tests pass
- [ ] Code formatted with Black
- [ ] Documentation updated
```

### Review Process

1. Any major revamps to code or new ideas not discussed with a maintainer will be rejected
2. Github passes Automated CI runs on all PRs (Black check, pytest suite)
3. Maintainer review required for merge, maintainer to review files changed
4. You address review feedback promptly
5. Keep PRs focused and reasonably sized - try to implement only one specific change per PR so it rollback will be easier.

## AI-Assisted Development

**TerraVision welcomes the use of AI tools for development!** AI assistance can accelerate development, improve code quality, and help with documentation.

### Disclosure Requirement

**All AI use for coding must be disclosed in pull requests.** Please include:

1. **Tools used**: Name of AI tool(s) (e.g., Claude Code, GitHub Copilot, ChatGPT, Cursor)
2. **Model and version**: Specific model used (e.g., Claude Sonnet 4.5, GPT-4 Turbo, Llama 3.1 70B)
3. **Scope of assistance**: What the AI helped with (e.g., "Generated test fixtures", "Refactored VPC handler", "Wrote docstrings")

### Example Disclosure

```markdown
## AI Assistance

- **Tools**: Claude Code CLI
- **Model**: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
- **Scope**:
  - Generated initial implementation of Azure resource handlers
  - Created unit tests for provider detection
  - Assisted with debugging Terraform graph parsing logic
```

### Why Disclose?

- **Transparency**: Helps maintainers understand the development process
- **Quality**: Allows reviewers to pay extra attention to AI-generated code
- **Learning**: Helps the community learn what AI tools work well for this project
- **Best practices**: Establishes a culture of responsible AI use

### AI Best Practices

- Always review and test AI-generated code thoroughly
- Ensure AI-generated code follows TerraVision's architecture patterns
- Verify that AI suggestions align with provider-specific conventions
- Use AI to augment your skills, not replace understanding

## Architecture Guidelines

### Adding New Cloud Providers

When adding support for a new cloud provider:

1. Create `modules/config/cloud_config_<provider>.py` with required constants:
   - `PROVIDER_PREFIX`, `ICON_LIBRARY`, `SPECIAL_RESOURCES`, etc.
2. Create `modules/resource_handlers_<provider>.py` with handler functions
3. Add provider prefix to `PROVIDER_PREFIXES` in `provider_detector.py`
4. Add icons to `resource_classes/<provider>/`
5. Add tests in `tests/test_provider_detection.py` and `tests/test_<provider>_resources.py`

### Multi-Cloud Support Pattern

TerraVision uses **dynamic provider detection** and **configuration loading**:

```python
# Detect provider from resource prefixes
provider = get_primary_provider_or_default(tfdata)

# Load provider-specific configuration
config = load_config(provider)

# Use provider-specific constants
icons = config.ICON_LIBRARY
special_resources = config.SPECIAL_RESOURCES
```

### Resource Handler Pattern

Special resources (VPCs, security groups, networks) follow a handler pattern:

```python
# In cloud_config_<provider>.py
SPECIAL_RESOURCES = {
    "provider_resource_type": "handler_function_name",
}

# In resource_handlers_<provider>.py
def handler_function_name(tfdata, resource):
    # Implementation
    return tfdata
```

### Debug Workflow

When debugging issues:

```bash
# Generate debug output
python terravision.py draw --source <path> --debug

# Inspect tfdata.json
cat tfdata.json | jq '.graphdict'

# Replay from debug file (skips terraform init/plan)
python terravision.py draw --source tfdata.json
```

## Project Structure

```
terravision/
├── modules/
│   ├── config/              # Provider-specific configurations
│   │   ├── cloud_config_aws.py
│   │   ├── cloud_config_azure.py
│   │   └── cloud_config_gcp.py
│   ├── resource_handlers_*.py  # Provider resource handlers
│   ├── resource_transformers.py  # Reusable Core graph transformers for all providers
│   ├── provider_detector.py    # Provider detection logic
│   ├── config_loader.py        # Dynamic config loading
│   ├── graphmaker.py           # Core graph construction
│   ├── drawing.py              # Graphviz rendering
│   └── helpers.py              # Utility functions
├── resource_classes/        # Icon libraries by provider
│   ├── aws/
│   ├── azure/
│   ├── gcp/
│   └── generic/
├── tests/                   # Test suite
├── terravision.py          # Main CLI entry point
└── pyproject.toml          # Poetry dependencies
```

## Getting Help

- **Documentation**: See [docs/ folder for more detailed info
- **Issues**: Search existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions
- **Examples**: Check `tests/fixtures/` for example Terraform code

## License

By contributing to TerraVision, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to TerraVision!
