# Publishing TerraVision to PyPI

## Prerequisites

1. **PyPI Account**: Create accounts at:
   - Test PyPI: https://test.pypi.org/account/register/
   - Production PyPI: https://pypi.org/account/register/

2. **API Tokens**: Generate API tokens for both:
   - Test PyPI: https://test.pypi.org/manage/account/token/
   - Production PyPI: https://pypi.org/manage/account/token/

## Step-by-Step Publishing

### 1. Update Version Number

Edit `pyproject.toml` and increment the version:
```toml
version = "0.9.1"  # Increment for each release
```

### 2. Update Author Email

Edit `pyproject.toml` and add your email:
```toml
authors = ["Patrick Chugh <your.email@example.com>"]
```

### 3. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 4. Build the Package

```bash
poetry build
```

This creates:
- `dist/terravision-0.9.0.tar.gz` (source distribution)
- `dist/terravision-0.9.0-py3-none-any.whl` (wheel distribution)

### 5. Test on Test PyPI (Recommended)

```bash
# Configure Test PyPI token
poetry config pypi-token.test-pypi <your-test-pypi-token>

# Publish to Test PyPI
poetry publish -r test-pypi
```

Test installation:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ terravision
```

### 6. Publish to Production PyPI

```bash
# Configure PyPI token
poetry config pypi-token.pypi <your-pypi-token>

# Publish to PyPI
poetry publish
```

### 7. Verify Installation

```bash
pip install terravision
terravision --version
```

## Alternative: Using Twine (Without Poetry)

If you prefer using twine directly:

```bash
# Install twine
pip install twine

# Build with Poetry
poetry build

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Upload to Production PyPI
twine upload dist/*
```

## Post-Publication

1. **Tag the Release in Git**:
```bash
git tag -a v0.9.0 -m "Release version 0.9.0"
git push origin v0.9.0
```

2. **Create GitHub Release**:
   - Go to https://github.com/patrickchugh/terravision/releases
   - Click "Draft a new release"
   - Select the tag you just created
   - Add release notes

3. **Update README Badge** (optional):
Add PyPI badge to README.md:
```markdown
[![PyPI version](https://badge.fury.io/py/terravision.svg)](https://badge.fury.io/py/terravision)
```

## Troubleshooting

### "Package already exists"
- Increment version number in `pyproject.toml`
- You cannot overwrite existing versions on PyPI

### "Invalid credentials"
- Regenerate API token
- Use `poetry config pypi-token.pypi <token>` to set it

### "Missing files in package"
- Check `MANIFEST.in` includes all necessary files
- Verify `packages` in `pyproject.toml` includes all modules

### "Import errors after installation"
- Ensure all dependencies are in `[tool.poetry.dependencies]`
- Test in a clean virtual environment

## Version Numbering

Follow Semantic Versioning (semver.org):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.9.0): New features, backward compatible
- **PATCH** (0.9.1): Bug fixes, backward compatible

Current status: **Alpha** (0.x.x)
- Move to 1.0.0 when production-ready
