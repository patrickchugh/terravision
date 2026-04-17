# Installation Guide

## System Requirements

- **Python 3.10+**
- **Terraform 1.x** (v1.0.0 or higher) — not required when using `--planfile` mode
- **Git**
- **Graphviz**
- **Ollama** (Optional - only for local AI refinement)

> **Note**: If you use the `--planfile` and `--graphfile` options to provide pre-generated Terraform outputs, Terraform itself does not need to be installed. Only Python, Graphviz, and Git are required. See the [Usage Guide](usage-guide.md#pre-generated-plan-input) for details.

---

## Step 1: Install External Dependencies

### Graphviz

**macOS:**
```bash
brew install graphviz
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install graphviz
```

**Windows:**
Download from https://graphviz.org/download/

**Verify installation:**
```bash
dot -V
```

### Git

Most systems have Git pre-installed. Verify:
```bash
git --version
```

If not installed, download from https://git-scm.com/downloads

### Terraform

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/terraform
```

**Ubuntu/Debian:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Windows:**
Download from https://developer.hashicorp.com/terraform/downloads

**Verify installation:**
```bash
terraform version
# Must show v1.0.0 or higher
```

---

## Step 2: Install TerraVision

### Method 1: Install from PyPI (Recommended for Users)

TerraVision is published to PyPI, so a single command installs the CLI and wires it up on your PATH on macOS, Linux, and Windows.

#### Using `pipx` (preferred — isolated environment)

[`pipx`](https://pipx.pypa.io/) installs the CLI into its own isolated virtualenv so it can't clash with other Python tooling on your system.

```bash
# Install pipx first if you don't have it
# macOS:          brew install pipx && pipx ensurepath
# Ubuntu/Debian:  sudo apt install pipx && pipx ensurepath
# Windows:        python -m pip install --user pipx && python -m pipx ensurepath

pipx install terravision
terravision --version
```

#### Using `pip` (if you're already in a virtualenv)

```bash
pip install terravision
terravision --version
```

!!! tip "Upgrading"
    `pipx upgrade terravision` or `pip install --upgrade terravision` pulls the latest release from PyPI.

### Method 2: Docker (Zero Setup)

If you don't want to install Python, Graphviz, and Terraform locally, you can run everything inside the official Docker image. This is also the recommended method for containerized CI/CD systems.

#### Pull the image

```bash
docker pull patrickchugh/terravision:latest
```

Or build it yourself:

```bash
git clone https://github.com/patrickchugh/terravision.git && cd terravision
docker build -t patrickchugh/terravision .
```

#### Run it against your Terraform code

Mount your project into the container so it can see your `.tf` files and write output back:

```bash
# Local directory
docker run --rm -it -v "$(pwd):/project" patrickchugh/terravision \
  draw --source /project/yourfiles/ --varfile /project/your.tfvars

# Remote Git repository with subfolder
docker run --rm -it -v "$(pwd):/project" patrickchugh/terravision \
  draw --source https://github.com/your-repo/terraform-examples.git//mysubfolder/
```

#### Passing cloud credentials

If Terraform needs credentials to run `terraform plan`, pass them into the container. For AWS:

```bash
# Mount your AWS credentials folder
docker run --rm -it -v "$(pwd):/project" \
  -v ~/.aws:/home/terravision/.aws:ro \
  patrickchugh/terravision draw --source /project/yourfiles/

# Or pass credentials as environment variables
docker run --rm -it -v "$(pwd):/project" \
  -e AWS_ACCESS_KEY_ID=your-access-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret-key \
  patrickchugh/terravision draw --source /project/yourfiles/
```

!!! tip "Skip credentials entirely"
    Use `--planfile` and `--graphfile` with pre-generated Terraform plan output to bypass `terraform plan` altogether. See [Pre-Generated Plan Input](usage-guide.md#pre-generated-plan-input).

#### Pinning a Terraform version

The image includes `tfenv`, so you can install and select a specific Terraform version at runtime via `TFENV_TERRAFORM_VERSION`:

```bash
docker run --rm -it -v "$(pwd):/project" \
  -e TFENV_TERRAFORM_VERSION=1.9.8 \
  patrickchugh/terravision draw --source /project/yourfiles/
```

If `TFENV_TERRAFORM_VERSION` is omitted, the container runs `terravision` directly with the image's default Terraform.

### Method 3: Nix (Reproducible Shell)

If you have [Nix](https://nixos.org/download/) installed with flakes enabled, you can get a fully reproducible development shell with TerraVision and every dependency pinned.

#### Enter a dev shell

```bash
git clone https://github.com/patrickchugh/terravision.git && cd terravision
nix develop
```

This gives you `terravision`, `graphviz`, `terraform`, and `git` in your PATH with no system-level install needed.

#### One-shot run without cloning

```bash
nix run github:patrickchugh/terravision -- draw --source /path/to/terraform --show
```

### Method 4: Install from Source with Poetry (For Contributors)

Use this method if you plan to hack on TerraVision itself. It's the workflow used by CI and every maintainer.

#### Install Poetry

**macOS/Linux:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Windows:**
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

#### Install TerraVision with Poetry

```bash
# Clone repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install dependencies in an isolated virtual environment
poetry install

# Activate the venv (drop the `poetry run` prefix for subsequent commands)
eval $(poetry env activate)
terravision --version

# Or use `poetry run` for individual commands without activating
poetry run terravision --version
```

See the [Contributing Guide](CONTRIBUTING.md) for coding standards, tests, and the PR process.

---

## Step 3: Verify Installation

Run a test to ensure everything is working:

```bash
# Check TerraVision version
terravision --version

# Check help
terravision --help

# Verify all dependencies
terraform version
git --version
dot -V
python --version
```

---

## Optional: Install Ollama (For Local AI Refinement)

If you want to use local AI-powered diagram refinement:

### Install Ollama

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

### Setup Ollama

```bash
# Start Ollama server (runs automatically on macOS/Linux after install)
ollama serve

# Pull the llama3 model
ollama pull llama3

# Optional: Keep model loaded longer (default is 5 minutes)
export OLLAMA_KEEP_ALIVE=1h

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

---

## Troubleshooting Installation

### Python Version Issues

```bash
# Check Python version
python --version

# If Python 3.10+ not available, install it
# macOS
brew install python@3.10

# Ubuntu
sudo apt-get install python3.10
```

### Permission Issues (Linux/macOS)

If `pip install terravision` fails with permission errors, use `pipx` (recommended) or fall back to a user install / virtualenv:

```bash
# Preferred: isolated install via pipx (no sudo ever needed)
pipx install terravision

# Or user install
pip install --user terravision

# Or inside a virtualenv
python -m venv venv
source venv/bin/activate
pip install terravision
```

### PATH Issues

If `terravision` command is not found:

```bash
# Add to PATH temporarily
export PATH=$PATH:/path/to/terravision

# Add to PATH permanently (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH=$PATH:/path/to/terravision' >> ~/.bashrc
source ~/.bashrc
```

### Graphviz Not Found

If you get "dot command not found" error:

```bash
# Verify Graphviz installation
which dot

# If not found, reinstall Graphviz
# macOS
brew reinstall graphviz

# Ubuntu
sudo apt-get install --reinstall graphviz
```

---

## Next Steps

- **[Usage Guide](usage-guide.md)** - Learn how to use TerraVision
- **[Quick Start Examples](usage-guide.md#quick-start-examples)** - Try your first diagram
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
