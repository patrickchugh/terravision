# Troubleshooting Guide

## Common Issues

### Installation Issues

#### "terraform command not found"

**Problem**: Terraform is not installed or not in PATH

**Solution**:
```bash
# Verify Terraform installation
terraform version

# If not installed, install Terraform
# macOS
brew install terraform

# Ubuntu/Debian
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

#### "dot command not found"

**Problem**: Graphviz is not installed

**Solution**:
```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install graphviz

# Windows
# Download from https://graphviz.org/download/

# Verify installation
dot -V
```

#### "Terraform version not supported"

**Problem**: Terraform version is too old

**Solution**:
```bash
# Check current version
terraform version

# TerraVision requires Terraform v1.0.0 or higher
# Upgrade Terraform
brew upgrade terraform  # macOS
# Or download latest from https://developer.hashicorp.com/terraform/downloads
```

#### Python Version Issues

**Problem**: Python 3.10+ not available

**Solution**:
```bash
# Check Python version
python --version

# Install Python 3.10+
# macOS
brew install python@3.10

# Ubuntu
sudo apt-get install python3.10

# Use specific Python version
python3.10 -m pip install -r requirements.txt
```

---

### Terraform Enterprise / Remote Backend Issues

#### "Backend configuration changed" or "State locked"

**Problem**: TerraVision conflicts with Terraform Enterprise remote backend

**Explanation**: TerraVision automatically forces local backend execution to generate complete infrastructure diagrams (not just state deltas). This is intentional and required for accurate visualization.

**How it works**:
- TerraVision copies `override.tf` to your source directory
- This forces `backend "local"` configuration
- Terraform ignores remote state and shows all resources
- Your actual TFE state remains unchanged

**Solution**: This is expected behavior - no action needed. TerraVision will:
1. Temporarily override your backend configuration
2. Generate a fresh plan showing all resources
3. Create the diagram from the complete infrastructure definition
4. Leave your remote state untouched

**Note**: If you see `override.tf` in your directory after running TerraVision, you can safely delete it or add to `.gitignore`.

#### "TFE_TOKEN required for module registry"

**Problem**: Private Terraform Enterprise module registry requires authentication

**Solution**:
```bash
# Set TFE token for private module access
export TFE_TOKEN="your-tfe-token"

# Generate token from TFE UI:
# Settings > Tokens > Create an API token

# Or use .terraformrc credentials
cat ~/.terraformrc
# credentials "app.terraform.io" {
#   token = "your-token"
# }
```

**Note**: TFE_TOKEN is only needed for accessing private module registries, not for basic diagram generation.

---

### Runtime Issues

#### "No resources found"

**Problem**: TerraVision can't find Terraform resources

**Checklist**:
1. Verify Terraform code is valid:
   ```bash
   cd /path/to/terraform
   terraform init
   terraform validate
   terraform plan
   ```

2. Check source path contains `.tf` files:
   ```bash
   ls -la /path/to/terraform/*.tf
   ```

3. Ensure Terraform can initialize:
   ```bash
   terraform init
   ```

4. Try with debug mode:
   ```bash
   terravision draw --source /path/to/terraform --debug
   ```

#### "Module not found" or "Module download failed"

**Problem**: Terraform modules can't be downloaded

**Solution**:
```bash
# Clear Terraform cache
rm -rf .terraform/

# Clear TerraVision cache
rm -rf ~/.terravision/

# Re-initialize
terraform init

# Try again
terravision draw --source /path/to/terraform
```

#### "Permission denied" errors

**Problem**: Insufficient permissions

**Solution**:
```bash
# Make terravision.py executable
chmod +x terravision.py

# If pip install fails, use --user flag
pip install --user -r requirements.txt

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### Pre-Generated Plan File Issues

#### "This appears to be a binary Terraform plan file"

**Problem**: You passed a binary `.tfplan` file instead of JSON

**Solution**: Convert the binary plan to JSON first:
```bash
terraform show -json tfplan.bin > plan.json
terravision draw --planfile plan.json --graphfile graph.dot --source ./terraform
```

#### "Plan file does not contain 'resource_changes'"

**Problem**: The JSON file is not a valid Terraform plan output

**Solution**: Ensure you use `terraform show -json` to export the plan:
```bash
terraform plan -out=tfplan.bin
terraform show -json tfplan.bin > plan.json
```

Do not use `terraform plan -json` (streaming output) — use `terraform show -json` on a saved plan file.

#### "Plan file contains no resource changes"

**Problem**: The Terraform plan has no resources to create, update, or destroy

**Solution**: Verify that `terraform plan` shows resources:
```bash
terraform plan
# Should show resources to create/update/destroy
```

If no resources appear, check your Terraform code and variable files.

#### "--planfile requires --graphfile and --source"

**Problem**: You must provide all three options together

**Solution**: Always provide `--planfile`, `--graphfile`, and `--source`:
```bash
terravision draw \
  --planfile plan.json \
  --graphfile graph.dot \
  --source ./terraform
```

#### "WARNING: --workspace/--varfile ignored with --planfile"

**Problem**: These options are irrelevant when using pre-generated plan files

**Explanation**: When you provide a `--planfile`, TerraVision skips Terraform execution entirely. The workspace and variable file were already applied when the plan was originally generated. This warning is informational — your diagram will still be generated correctly.

---

### Diagram Generation Issues

#### Empty or Incomplete Diagrams

**Problem**: Diagram is generated but shows no resources or is incomplete

**Checklist**:
1. Run Terraform plan to ensure resources exist:
   ```bash
   terraform plan
   ```

2. Check if resources are conditionally created:
   ```bash
   # Use appropriate variable files
   terravision draw --source . --varfile prod.tfvars
   ```

3. Verify workspace:
   ```bash
   # Use correct workspace
   terravision draw --source . --workspace production
   ```

4. Enable debug mode:
   ```bash
   terravision draw --source . --debug
   # Check tfdata.json for parsed resources
   ```

#### Diagram Layout Issues

**Problem**: Resources are overlapping or poorly positioned

**Solutions**:
1. Try simplified mode:
   ```bash
   terravision draw --source . --simplified
   ```

2. Use different output format:
   ```bash
   terravision draw --source . --format svg
   ```

3. Use annotations to adjust layout:
   ```yaml
   # terravision.yml
   remove:
     - aws_iam_role.*  # Remove noisy resources
   ```

#### Missing Connections

**Problem**: Expected connections between resources are not shown

**Solutions**:
1. Check if resources are actually connected in Terraform:
   ```bash
   terraform show
   ```

2. Add connections via annotations:
   ```yaml
   # terravision.yml
   connect:
     aws_lambda_function.api:
       - aws_rds_cluster.db: "Database queries"
   ```

3. Enable debug mode to see connection processing:
   ```bash
   terravision draw --source . --debug
   ```

---

### AI Refinement Issues

#### "Cannot reach Ollama server"

**Problem**: Ollama server is not running or not accessible

**Solution**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start Ollama
ollama serve

# If port is in use, kill existing process
lsof -ti:11434 | xargs kill -9
ollama serve

# Verify llama3 model is installed
ollama list
ollama pull llama3
```

#### "Ollama model not loaded"

**Problem**: Model unloads too quickly

**Solution**:
```bash
# Extend keep-alive time (default is 5 minutes)
export OLLAMA_KEEP_ALIVE=1h

# Restart Ollama
ollama serve
```

#### "Bedrock API error"

**Problem**: AWS Bedrock API is not configured or accessible

**Solution**:
1. Verify API endpoint in `modules/cloud_config.py`:
   ```python
   BEDROCK_API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat"
   ```

2. Check API Gateway is deployed:
   ```bash
   cd ai-backend-terraform
   terraform output api_endpoint
   ```

3. Verify API is accessible:
   ```bash
   curl -X POST https://your-api-endpoint/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "test"}'
   ```

---

### Performance Issues

#### Slow Diagram Generation

**Problem**: TerraVision takes too long to generate diagrams

**Solutions**:
1. Export to JSON first, then generate multiple formats:
   ```bash
   terravision graphdata --source . --outfile graph.json
   terravision draw --source graph.json --format svg
   terravision draw --source graph.json --format png
   ```

2. Use simplified mode:
   ```bash
   terravision draw --source . --simplified
   ```

3. Use specific workspace to reduce scope:
   ```bash
   terravision draw --source . --workspace production
   ```

4. Clear cache:
   ```bash
   rm -rf ~/.terravision/
   ```

#### Large File Sizes

**Problem**: Generated diagrams are too large

**Solutions**:
1. Use SVG format (smaller and scalable):
   ```bash
   terravision draw --source . --format svg
   ```

2. Use simplified mode:
   ```bash
   terravision draw --source . --simplified
   ```

3. Remove unnecessary resources via annotations:
   ```yaml
   remove:
     - aws_iam_role.*
     - aws_cloudwatch_log_group.*
   ```

---

### Annotation Issues

#### Annotations Not Applied

**Problem**: Annotations in terravision.yml are ignored

**Checklist**:
1. Verify file name is exactly `terravision.yml`
2. Check YAML syntax:
   ```bash
   # Use online YAML validator or
   python -c "import yaml; yaml.safe_load(open('terravision.yml'))"
   ```

3. Verify resource names exist:
   ```bash
   terravision graphdata --source . --show_services
   ```

4. Enable debug mode:
   ```bash
   terravision draw --source . --debug
   ```

#### Wildcards Not Matching

**Problem**: Wildcard patterns don't match expected resources

**Solution**:
```bash
# List all resources to verify patterns
terravision graphdata --source . --outfile resources.json
cat resources.json | jq 'keys'

# Test specific patterns
grep "aws_lambda" resources.json
```

---

### Git Repository Issues

#### "Failed to clone repository"

**Problem**: Can't access Git repository

**Solutions**:
1. Verify repository URL:
   ```bash
   git clone https://github.com/user/repo.git
   ```

2. Check authentication:
   ```bash
   # For private repos, use SSH or token
   git clone git@github.com:user/repo.git
   ```

3. Specify subfolder:
   ```bash
   terravision draw --source https://github.com/user/repo.git//terraform/aws
   ```

#### "Module source not found"

**Problem**: Terraform modules in Git can't be accessed

**Solution**:
```bash
# Ensure Git credentials are configured
git config --global credential.helper store

# Or use SSH keys
ssh-add ~/.ssh/id_rsa
```

---

## Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
terravision draw --source /path/to/terraform --debug
```

**Debug mode provides**:
- Detailed processing steps
- Intermediate JSON files (tfdata.json)
- Full error traces
- Variable resolution details

**Analyze debug output**:
```bash
# Check parsed resources
cat tfdata.json | jq '.graphdict | keys'

# Check metadata
cat tfdata.json | jq '.meta_data'

# Check connections
cat tfdata.json | jq '.graphdict["aws_lambda_function.api"]'
```

---

## Getting Help

### Check Documentation
- [Installation Guide](INSTALLATION.md)
- [Usage Guide](USAGE_GUIDE.md)
- [Annotations Guide](ANNOTATIONS.md)

### Command Help
```bash
terravision --help
terravision draw --help
terravision graphdata --help
```

### Report Issues
- **GitHub Issues**: https://github.com/patrickchugh/terravision/issues
- **Discussions**: https://github.com/patrickchugh/terravision/discussions

### Include in Bug Reports
1. TerraVision version: `terravision --version`
2. Python version: `python --version`
3. Terraform version: `terraform version`
4. Operating system
5. Debug output: `terravision draw --debug`
6. Minimal reproducible example

---

## Quick Fixes

### Reset Everything

```bash
# Clear all caches
rm -rf ~/.terravision/
rm -rf .terraform/
rm -f tfdata.json

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Reinitialize Terraform
terraform init

# Try again
terravision draw --source . --debug
```

### Verify Installation

```bash
# Check all dependencies
terraform version  # Should be v1.0.0+
python --version   # Should be 3.10+
dot -V            # Should show Graphviz version
git --version     # Should show Git version

# Test TerraVision
terravision --version
terravision --help
```

---

## Still Having Issues?

If you've tried everything and still have problems:

1. **Enable debug mode** and save output:
   ```bash
   terravision draw --source . --debug > debug.log 2>&1
   ```

2. **Create minimal example** that reproduces the issue

3. **Open GitHub issue** with:
   - Debug log
   - Minimal example
   - System information
   - Steps to reproduce

We're here to help! 🚀
