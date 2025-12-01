# Quick Guide: Analyzing a Project

## 1. Start with the Big Picture

Read these files first (in order):
- `README.md` - What the project does, how to use it
- `CONTRIBUTING.md` / `DEVELOPMENT.md` - Development workflow
- `ARCHITECTURE.md` / `docs/` - System design & structure
- Project-specific docs in root (like `AGENTS.md`, `ROADMAP.md`)

## 2. Understand the Structure

```bash
# Get file tree overview
ls -la
tree -L 2  # or use your file explorer

# Identify key areas:
# - Entry points (main.py, index.js, cli.py, terravision.py)
# - Core modules (src/, lib/, modules/)
# - Tests (tests/, __tests__)
# - Config (pyproject.toml, package.json, Cargo.toml)
# - Docs (docs/, README.md)
```

## 3. Technology Stack

Check these files:
- **Python**: `pyproject.toml`, `requirements.txt`, `setup.py`
- **JavaScript/Node**: `package.json`, `tsconfig.json`
- **Rust**: `Cargo.toml`
- **Go**: `go.mod`
- **Ruby**: `Gemfile`

Look for:
- Dependencies (what libraries are used?)
- Build/test commands
- Python/Node version requirements

## 4. Code Flow Analysis

### Find Entry Points:

```bash
# Python
grep -r "if __name__ == .__main__." 
grep -r "@click.command\|@app.route"

# JavaScript  
grep -r "exports\|module.exports\|export default"
```

### Trace Key Functions:

1. Read the entry point (e.g., `cli.py`, `main.py`, `terravision.py`)
2. Follow function calls to understand flow
3. Look for core business logic (usually in `src/` or `lib/`)

## 5. Test Analysis

```bash
# Find tests
ls tests/

# Check test commands
# Python: pytest, unittest
# JS: jest, mocha
# Check package.json or pyproject.toml for test scripts
```

## 6. Active Development Areas

Check:

```bash
# Recent changes
git log --oneline -20

# Active branches  
git branch -a

# TODO/FIXME comments
grep -r "TODO\|FIXME\|XXX" --include="*.py"

# Open issues (if specs/ exists)
ls specs/
```

## 7. Quick Analysis Checklist

- [ ] What problem does this solve?
- [ ] What's the tech stack?
- [ ] Where's the entry point?
- [ ] What are the core modules?
- [ ] How do I build/test it?
- [ ] What's the data flow?
- [ ] Are there any current tasks/specs in progress?
- [ ] What's the test coverage like?

## 8. TerraVision-Specific Quick Start

### Project Overview

**Purpose**: Generate architecture diagrams from Terraform infrastructure code (AWS/Azure/GCP)

**Tech Stack**: 
- Python 3.9-3.11
- Poetry (dependency management)
- Graphviz (diagram rendering)
- Click (CLI framework)
- pytest (testing)

### Quick Commands

```bash
# Install dependencies
poetry install

# Run all tests
poetry run pytest

# Run fast tests only (skip slow integration tests)
poetry run pytest -m "not slow"

# Run single test
poetry run pytest tests/helpers_unit_test.py::TestGetvar::test_getvar_from_dict -v

# Format code
poetry run black .
poetry run isort .

# Pre-commit hooks
poetry run pre-commit run --all-files

# Run TerraVision
poetry run terravision --help
```

### Project Structure

```
terravision/
├── terravision.py              # CLI entry point
├── modules/                    # Core business logic
│   ├── cloud_config/          # Provider configurations (AWS/Azure/GCP)
│   ├── resource_handlers/     # Provider-specific resource handling
│   ├── provider_runtime.py    # Provider abstraction layer
│   ├── graphmaker.py          # Graph generation
│   ├── drawing.py             # Diagram rendering
│   ├── interpreter.py         # Terraform plan parsing
│   └── helpers.py             # Utility functions
├── resource_classes/          # Diagram node classes
│   ├── aws/                   # AWS resource classes
│   ├── generic/               # Generic resource classes
│   └── onprem/                # On-prem resource classes
├── tests/                     # Test suite
│   ├── *_unit_test.py        # Unit tests
│   ├── integration_test.py   # Integration tests
│   └── performance_test.py   # Performance benchmarks
└── docs/                      # Documentation
    ├── ARCHITECTURAL.md       # System architecture
    ├── ADDING_PROVIDERS.md    # Provider development guide
    ├── ROADMAP.md             # Future plans
    └── QUICKSTART.md          # This file
```

### Key Entry Points

1. **CLI**: `terravision.py` - Main CLI with Click commands
2. **Provider System**: `modules/provider_runtime.py` - Multi-cloud abstraction
3. **Graph Generation**: `modules/graphmaker.py` - Dependency graph creation
4. **Diagram Rendering**: `modules/drawing.py` - Graphviz diagram generation

### Data Flow

```
Terraform Plan JSON
    ↓
interpreter.py (parse plan)
    ↓
graphmaker.py (build dependency graph)
    ↓
provider_runtime.py (apply provider-specific configs)
    ↓
drawing.py (render Graphviz diagram)
    ↓
PNG/SVG output
```

### Current State

- **Version**: 0.8 → 0.9 (multi-cloud foundation)
- **Providers**: AWS (mature), Azure (Phase 6), GCP (Phase 6)
- **Tests**: 78/79 passing (98.7%)
- **Recent Work**: Provider Abstraction Layer (SPEC-001) - 7 phases complete
- **Performance**: All operations < 1ms (1,800x-50,000x faster than targets)

### Development Workflow

1. Make code changes
2. Run tests: `poetry run pytest`
3. Format code: `poetry run black . && poetry run isort .`
4. Run pre-commit hooks: `poetry run pre-commit run --all-files`
5. Commit changes

### Testing Strategy

- **Unit tests**: Test individual functions/classes
- **Integration tests**: Test end-to-end CLI commands
- **Performance tests**: Validate < 1ms operation targets
- **Slow tests**: Marked with `@pytest.mark.slow`, skip with `-m "not slow"`

### Common Tasks

**Add a new cloud provider:**
1. Read `/docs/ADDING_PROVIDERS.md` (comprehensive guide)
2. Create config in `modules/cloud_config/your_provider.py`
3. Register in `modules/provider_runtime.py`
4. Add resource images to `resource_images/your_provider/`
5. Write tests in `tests/`
6. Estimated time: 2-4 hours

**Run a specific test:**
```bash
poetry run pytest tests/helpers_unit_test.py -v
```

**Debug a test:**
```bash
poetry run pytest tests/integration_test.py::test_help -v --pdb
```

**Check performance:**
```bash
poetry run pytest tests/performance_test.py -v
```

## Pro Tips

- **Use grep/search liberally** - Find patterns quickly
- **Follow imports** - Understand dependencies
- **Read tests** - They show how code is meant to be used
- **Check git history** - See what changed recently
- **Look for AGENTS.md** - Project-specific agent guidelines
- **Check .github/workflows** - CI/CD tells you the full build/test process

## Common Pitfalls

❌ Don't read every file linearly  
✅ Do use a top-down approach: README → Architecture → Entry points → Core logic

❌ Don't skip the tests  
✅ Do read tests to understand expected behavior

❌ Don't ignore build/dependency files  
✅ Do check pyproject.toml/package.json for scripts and dependencies

## Time Budget

- **Initial analysis**: 15-30 minutes for medium projects
- **Deep dive**: 1-2 hours for full understanding
- **Ready to contribute**: 2-4 hours including running tests

## Next Steps

After reading this guide:

1. Run `poetry install` to set up the environment
2. Run `poetry run pytest -m "not slow"` to verify setup
3. Read `/docs/ARCHITECTURAL.md` for system design
4. Explore the codebase starting from `terravision.py`
5. Try running: `poetry run terravision --help`

## Getting Help

- **Documentation**: Check `/docs/` folder
- **Code examples**: Look in `/tests/` for usage patterns
- **Architecture**: Read `/docs/ARCHITECTURAL.md`
- **Adding providers**: Read `/docs/ADDING_PROVIDERS.md`
- **Issues**: Check GitHub issues or create new ones

---

**Welcome to TerraVision!** 🎉
