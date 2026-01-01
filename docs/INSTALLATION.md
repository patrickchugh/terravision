# Installation Guide

## System Requirements

- **Python 3.10+**
- **Terraform 1.x** (v1.0.0 or higher)
- **Git**
- **Graphviz**
- **Ollama** (Optional - only for local AI refinement)

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

### Method 1: Quick Install (For Users)

This method installs packages globally and is suitable for casual users.

#### macOS/Linux

```bash
# Clone repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install Python dependencies
pip install -r requirements.txt

# Make script executable
chmod +x terravision.py

# Create symbolic link
ln -s $(pwd)/terravision.py $(pwd)/terravision

# Add to PATH (add this to ~/.bashrc or ~/.zshrc for persistence)
export PATH=$PATH:$(pwd)

# Test installation
terravision --version
```

#### Windows

```powershell
# Clone repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install Python dependencies
pip install -r requirements.txt

# Create batch file wrapper
echo @python "%~dp0terravision.py" %* > terravision.bat

# Copy to system directory (requires admin privileges)
copy terravision.bat C:\Windows\System32\

# Test installation
terravision --version
```

### Method 2: Poetry Install (For Developers)

This method uses Poetry for dependency management and is recommended for developers.

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

# Install dependencies in virtual environment
poetry install

# Activate virtual environment
poetry shell

# Or use poetry run for individual commands
poetry run terravision --version
```

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

```bash
# If pip install fails with permission errors, use --user flag
pip install --user -r requirements.txt

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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

- **[Usage Guide](USAGE_GUIDE.md)** - Learn how to use TerraVision
- **[Quick Start Examples](USAGE_GUIDE.md#quick-start-examples)** - Try your first diagram
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
