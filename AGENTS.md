# Agent Guidelines for TerraVision

## Build, Lint, and Test Commands
- **Install dependencies**: `poetry install` (uses Poetry for dependency management)
- **Run all tests**: `poetry run pytest`
- **Run single test**: `poetry run pytest tests/helpers_unit_test.py::TestGetvar::test_getvar_from_dict -v`
- **Run fast tests only**: `poetry run pytest -m "not slow"` (excludes slow-marked tests)
- **Format code**: `poetry run black .` and `poetry run isort .` (Black line-length: 88, targets Python 3.9-3.11)
- **Pre-commit hooks**: `poetry run pre-commit run --all-files` (runs pytest on non-slow tests)

## Code Style Guidelines
- **Python version**: 3.9-3.11 (strictly enforced by pyproject.toml)
- **Imports**: Group standard library, third-party, then local modules. Use `import modules.X as X` pattern for internal modules
- **Type hints**: Use typing module annotations (`Dict[str, Any]`, `List`, `Optional`, `Tuple`) for function signatures
- **Docstrings**: Google-style docstrings for modules and functions, include Args/Returns sections
- **Naming**: snake_case for functions/variables, UPPER_CASE for module-level constants from cloud_config
- **Error handling**: Use click.echo() with click.style() for user-facing errors (fg="red", bold=True), sys.exit() for fatal errors
- **Exception suppression**: Use `contextlib.suppress()` for expected exceptions (e.g., JSON parsing)
- **Click framework**: All CLI commands use @click decorators with clear help text and defaults
- **Data structures**: Primary data container is `tfdata` dict with keys: `graphdict`, `metadata`, `all_resource`, `annotations`
- **File operations**: Use pathlib.Path for paths, tempfile for temporary directories
- **Special notes**: Skip isort for drawing.py (configured in pyproject.toml). Tests use unittest framework with sys.path manipulation for imports

## Active Technologies
- Python 3.9-3.11 (enforced by pyproject.toml; constitution requirement) + click 8.1.3, GitPython 3.1.31, graphviz 0.20.1, python-hcl2 4.3.0, PyYAML 6.0 (001-provider-abstraction-layer)
- N/A (no persistent storage; outputs to local files only) (001-provider-abstraction-layer)
- Python 3.9-3.11 (strictly enforced by pyproject.toml) + click 8.1.3 (CLI framework), graphviz 0.20.1 (diagram rendering), python-hcl2 4.3.0 (Terraform parsing), GitPython 3.1.31 (module fetching), PyYAML 6.0 (annotations) (002-code-quality-fixes)
- Local files only (Terraform .tf files, JSON graph exports, .tfvars, YAML annotations); no cloud/database storage (002-code-quality-fixes)

## Recent Changes
- 001-provider-abstraction-layer: Added Python 3.9-3.11 (enforced by pyproject.toml; constitution requirement) + click 8.1.3, GitPython 3.1.31, graphviz 0.20.1, python-hcl2 4.3.0, PyYAML 6.0
