

# TerraVision

TerraVision is an AI-powered CLI tool that converts Terraform code into Professional Cloud Architecture Diagrams and solves the problem of keeping the most important document in cloud projects, the architecture diagram, up to date. With high velocity releases the norm now, machine generated architecture diagrams are more accurate than relying on the freestyle diagram drawn by the cloud architect that probably doesn't match reality anymore. 

TerraVision securely runs 100% Client Side without any dependency or access to your Cloud environment, dynamically parses your conditionally created resources and variables and generates an automatic visual of your architecture. TerraVision is designed to be a 'Docs as Code' (DaC) tool that can be included in your CI/CD pipeline to update architecture diagrams after your build/test/release pipeline phases and supplement other document generators like readthedocs.io alongside it. 


## Status
**Current Version: 0.8**

[![lint-and-test](https://github.com/patrickchugh/terravision/actions/workflows/lint-and-test.yml/badge.svg)](https://github.com/patrickchugh/terravision/actions/workflows/lint-and-test.yml)


## Supported Cloud Providers
- ✅ **AWS** (Full support with 200+ services)
- 🔄 **Google Cloud Platform** (Coming soon)
- 🔄 **Microsoft Azure** (Coming soon)
- ✅ **On-Premises** (Generic infrastructure components)

Turn this... 

![Terraform Code](./images/code.png "Turn Terraform code")

into this...

<img src="./images/architecture.png" width="640" height="580">

> **⚠️ Alpha Software Notice**  
> This software is still in alpha testing and **code is shared on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied. Use at your own risk.

# Benefits of terravision
1. Cost
	- Save Visio/Drawing software licenses - terravision is free and open source
	- Doesn't require any cost incurring cloud resources to be spun up, it works instantly from your local machine
	- Regularly updating diagrams aligning, connecting dots and laying out icons is not the best use of your architect staff costs
2. Accelerate and Automate
	- Use TF variable files as inputs to create multiple variant diagrams from the same TF code
   - Doesn't require infrastructure to exist to document it. Terravision works off your terraform plan not your remote statefile
	- Automate creation of architecture diagrams by running terravision as part of CI/CD pipelines
	- YAML based Diagrams as code allows you to Annotate generated diagrams with additional custom labels and resources  e.g. unmanaged resources or external systems not captured in TF code
3. Consistency across organisation
	- Auto downloads your organisational / external modules to ensure the latest view of downstream Terraform modules
	- Consistent design of architecture diagrams using industry standard icons and AWS/GCP/Azure approved style across teams 
4. Accurate Visibility 
	- Real time state of diagram shows current infrastructure that matches exactly what is deployed in production today
	- Helps in third party architecture reviews, auditing, monitoring, reporting and debugging of the stack in a visual way
	- Custom Diagram code and output images can be put into source/version control for better maintainability and discoverability
5. Security
	- Don't need to give access to your AWS account, credentials or CLI to draw diagram
	- Doesn't create intrusive cloud resources  e.g. scanning instances or metadata tables which enterprises would need to approve
  	- All source code stays in your local environment, diagrams are generated on your machines without calling out to external APIs
   - Only metatdata is saved in memory or external files not any sensitive code or runtime environment values

# Installation and Usage

## System Requirements
- **Python 3.10+** 
- **Terraform 1.x**   
- **Git**  
- **Graphviz**
- **Ollama** (Optional - only required if using `--aibackend ollama`)

## 1. Install External Dependencies

### Required Dependencies
1. **Graphviz** - https://graphviz.org/download/
   ```bash
   # macOS
   brew install graphviz
   
   # Ubuntu/Debian
   sudo apt-get install graphviz
   
   # Windows
   # Download from https://graphviz.org/download/
   ```

2. **Git** - https://git-scm.com/downloads
   ```bash
   # Most systems have git pre-installed
   git --version
   ```

3. **Terraform** - https://developer.hashicorp.com/terraform/downloads
   ```bash
   # Verify installation
   terraform version
   # Must be v1.0.0 or higher
   ```



## 2. Install TerraVision

### Method 1: Quick Install in MacOS/Linux (For Casual Users - will install packages globally)
```bash
# Clone the repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install Python dependencies
pip install -r requirements.txt

# Make script executable in Linux
chmod +x terravision.py

# Create symbolic link without extension (Unix/Linux/macOS)
ln -s $(pwd)/terravision.py $(pwd)/terravision

# Add to PATH
export PATH=$PATH:$(pwd)


```

**For Windows:**
```powershell
# Clone the repository
git clone https://github.com/patrickchugh/terravision.git
cd terravision

# Install Python dependencies
pip install -r requirements.txt

# Create batch file wrapper
echo @python "%~dp0terravision.py" %* > terravision.bat

# Add current directory to PATH or copy terravision.bat to a directory in PATH
copy terravision.bat C:\Windows\System32\


``` 

### Method 2: Poetry Install (Recommended for Developers and Power Users)
```bash
# MacOS or Linux users - Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# For Windows Users
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Clone and install with Poetry
git clone https://github.com/patrickchugh/terravision.git
cd terravision
poetry install

# Activate virtual environment
source $(poetry env info --path)/bin/activate

# Create symbolic link without extension
ln -s $(pwd)/terravision.py $(pwd)/terravision

# Add current terravision directory to PATH
export PATH=$PATH:$(pwd)
```

## Basic Usage

### Generate Architecture Diagram
```bash
# Basic usage - analyze current directory
terravision draw

# Specify source directory
terravision draw --source ~/src/my-terraform-code

# Use specific Terraform workspace
terravision draw --source ~/src/my-terraform-code --workspace production

# Use variable files
terravision draw --source ~/src/my-terraform-code --varfile prod.tfvars

# Generate different formats
terravision draw --source ~/src/my-terraform-code --format svg
terravision draw --source ~/src/my-terraform-code --format pdf

# Show diagram after generation
terravision draw --source ~/src/my-terraform-code --show

# Use AI backend for diagram refinement (default: bedrock)
terravision draw --source ~/src/my-terraform-code --aibackend bedrock
terravision draw --source ~/src/my-terraform-code --aibackend ollama
```

### Remote Git Repository Support
```bash
# Analyze Git repository
terravision draw --source https://github.com/your-repo/terraform-examples.git

# Analyze specific subfolder in Git repo
terravision draw --source https://github.com/your-repo/terraform-examples.git//aws/vpc

```

### Export Graph Data
```bash
# Export resource relationships as JSON
terravision graphdata --source ~/src/my-terraform-code

# Show only unique services used
terravision graphdata --source ~/src/my-terraform-code --show_services

# Export to custom filename
terravision graphdata --source ~/src/my-terraform-code --outfile my-resources.json
```



## Advanced Features


### Use with annotations
```bash
# Add your own custom annotations such as labels, resources or new connections
terravision draw --source https://github.com/your-repo/terraform-examples.git --annotate ./custom-annotations.yml
```

### Working with Pre-generated JSON from previous terravision run (faster)
```bash
# Export and reuse graph data
terravision graphdata --source ~/src/terraform --outfile graph.json

# Use previously exported JSON data (just the graph dict)
terravision draw --source ./graph.json
terravision draw --source ./graph.json --format svg

# Reprocess and replay from previous debug (for troubleshooting without calling slow terraform init/plan/analayse again)
terravision draw --source /your_source_files --debug  # createas a tfdata.json in current folder
terravision draw --source tfdata.json
```

### Debug Mode
```bash
# Enable debug output for troubleshooting and which will dump all state info into tfdata.json
terravision draw --source ~/src/my-terraform-code --debug
```

## AI-Powered Diagram Refinement

TerraVision can use AI models to automatically refine and improve your architecture diagrams by fixing resource groupings, adding missing connections, and ensuring proper AWS architectural conventions.

### Supported AI Backends

#### AWS Bedrock (Default)
Uses AWS Bedrock API via API Gateway for cloud-based AI refinement.

```bash
# Use Bedrock backend (default)
terravision draw --source ~/src/my-terraform-code --aibackend bedrock
```

**Configuration:**
Edit `modules/cloud_config.py` to set your Bedrock API endpoint:
```python
BEDROCK_API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat"
```

#### Ollama (Local)
Uses a local Ollama server for privacy-focused, offline AI refinement.

```bash
# Use Ollama backend
terravision draw --source ~/src/my-terraform-code --aibackend ollama
```

**Setup:**
1. Install Ollama from https://ollama.ai/download
2. Start Ollama server and pull a model:
   ```bash
   # Start Ollama (runs automatically on macOS/Linux after install)
   ollama serve
   
   # Pull the llama3 model
   ollama pull llama3
   
   # Set model to stay loaded longer (optional, prevents premature unloading)
   # Default timeout is 5 minutes, extend to 1 hour:
   export OLLAMA_KEEP_ALIVE=1h
   ```
3. Edit `modules/cloud_config.py` to set your Ollama server (default is localhost):
   ```python
   OLLAMA_HOST = "http://localhost:11434"
   ```

### AI Refinement Prompts

The AI models use specialized prompts defined in `modules/cloud_config.py`:

- **AWS_REFINEMENT_PROMPT**: Guides the AI to fix resource groupings, connections, and ensure AWS best practices
- **AWS_DOCUMENTATION_PROMPT**: Generates architecture summaries and documentation

### Setting Up AWS Bedrock Backend

TerraVision includes Terraform code to deploy a serverless AWS Bedrock proxy with API Gateway:

```bash
# Navigate to the Terraform directory
cd ai-backend-terraform

# Configure your settings
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings

# Deploy the infrastructure
terraform init
terraform apply

# Get your API endpoint
terraform output api_endpoint
```

**Infrastructure Components:**
- **API Gateway**: REST API with streaming support for real-time responses
- **Lambda Function**: Node.js 20.x function with response streaming
- **DynamoDB**: Rate limiting and usage tracking
- **CloudWatch**: Monitoring, logging, and cost alerts
- **IAM Roles**: Least-privilege access for Lambda to invoke Bedrock

**Terraform Variables:**
```hcl
variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
}

variable "rate_limit_per_hour" {
  description = "Maximum requests per client per hour"
  type        = number
  default     = 100
}

variable "cost_alert_threshold" {
  description = "Cost alert threshold in USD"
  type        = number
  default     = 50
}
```

After deployment, update `modules/cloud_config.py` with the output endpoint:
```python
BEDROCK_API_ENDPOINT = "<your-api-endpoint-from-terraform-output>"
```
 

# Annotating generated diagrams
No automatically generated diagram is going to have all the detail you need, at best it will get you 80-90% of the way there. To add custom annotations such as a main diagram title, additional labels on arrows or additional resources created outside your Terraform, include a `terravision.yml` file in the source code folder and it will be automatically loaded. Alternatively, specify a path to the annotations file as a parameter to terravision. 

``` bash
terravision --source https://github.com/your-repo/terraform-examples.git --annotate /Users/me/MyDocuments/annotations.yml
```

The .yml file is a standard YAML configuration file that is similar to the example below with one or more headings called `title`, `connect`, `disconnect`, `add`, `remove` or `update`. The node names follow the same conventions as Terraform resource names https://registry.terraform.io/providers/hashicorp/aws/latest/docs and support wildcards. You can add a custom label to any TF resource by modifying the attributes of the resource and adding the `label` attribute (doesn't exist in Terraform). For lines/connections, you can modify the resource attributes by adding terravision specific `edge_labels` to add text to the connection line to a specific resource node. See the example below:

``` yaml
format: 0.1
# Main Diagram heading
title: Serverless Wordpress Site
# Draw new connection lines that are not apparent from the Terraforms
connect:
  aws_rds_cluster.this:
    - aws_ssm_parameter.db_master_user : Retrieve credentials from SSM
# Remove connections between nodes that are currently shown
disconnect:
  # Wildcards mean these disconnections apply to any cloudwatch type resource called logs
  aws_cloudwatch*.logs:
    - aws_ecs_service.this
    - aws_ecs_cluster.this
# Delete the following nodes
remove:
  - aws_iam_role.task_execution_role
# Add the following nodes
add:
  aws_subnet.another_one :
    # Specify Terraform attributes for a resource like this 
    cidr_block: "123.123.1.1"
# Modify attributes of existing node
update:
  aws_ecs_service.this:
    # Add custom labels to the connection lines that already exist between ECS->RDS
    edge_labels:
      - aws_rds_cluster.this: Database Queries
  # Wildcards save you listing multiple resources of the same type. This edge label is added to all CF->ACM connections.
  aws_cloudfront* :
    edge_labels:
      - aws_acm_certificate.this: SSL Cert
 # Add a custom label to a resource node. Overrides default label
  aws_ecs_service.this :
   label: "My Custom Label"

```

## Command Reference

### Main Commands

#### `terravision draw`
Generates architecture diagrams from Terraform code.

**Options:**
- `--source` - Source location (folder, Git URL, or JSON file)
- `--workspace` - Terraform workspace (default: "default")
- `--varfile` - Path to .tfvars file (can be used multiple times)
- `--outfile` - Output filename (default: "architecture")
- `--format` - Output format: png, pdf, svg, bmp (default: png)
- `--show` - Automatically open diagram after generation
- `--simplified` - Generate simplified high-level diagram
- `--annotate` - Path to custom annotations YAML file
- `--aibackend` - AI backend for diagram refinement: bedrock, ollama (default: bedrock)
- `--debug` - Enable debug output

#### `terravision graphdata`
Exports resource relationships and metadata as JSON.

**Options:**
- `--source` - Source location (folder, Git URL, or JSON file)
- `--workspace` - Terraform workspace (default: "default")
- `--varfile` - Path to .tfvars file (can be used multiple times)
- `--outfile` - Output JSON filename (default: "architecture.json")
- `--show_services` - Show only unique services list
- `--annotate` - Path to custom annotations YAML file
- `--aibackend` - AI backend for diagram refinement: bedrock, ollama
- `--debug` - Enable debug output

### Global Options
- `--version` - Show version information
- `--help` - Show help message

## Supported File Types

### Input Sources
- **Terraform files** (`.tf`, `.tf.json`)
- **Variable files** (`.tfvars`, `.tfvars.json`)
- **Git repositories** (HTTPS URLs)
- **Pre-generated JSON** (`.json` graph data)
- **Annotation files** (`.yml`, `.yaml`)

### Output Formats
- **PNG** (default) - Raster image format
- **SVG** - Scalable vector graphics
- **PDF** - Portable document format
- **BMP** - Bitmap image format
- **JSON** - Graph data export

## Troubleshooting

### Common Issues

1. **"terraform command not found"**
   ```bash
   # Verify Terraform installation
   terraform version
   # Should show v1.x.x
   ```

2. **"dot command not found"**
   ```bash
   # Install Graphviz
   brew install graphviz  # macOS
   sudo apt-get install graphviz  # Ubuntu
   ```

3. **"Terraform version not supported"**
   - terravision requires Terraform v1.0.0 or higher
   - Upgrade Terraform: https://developer.hashicorp.com/terraform/downloads

4. **"No resources found"**
   - Ensure your Terraform code is valid
   - Run `terraform plan` to verify configuration
   - Check that source path contains `.tf` files

5. **"Cannot reach Ollama server"**
   - Verify Ollama is running: `curl http://localhost:11434/api/tags`
   - If server is unresponsive, kill existing processes:
     ```bash
     lsof -ti:11434 | xargs kill -9
     ollama serve
     ```
   - Ensure llama3 model is installed: `ollama pull llama3`



### Debug Mode
Use `--debug` flag for detailed troubleshooting information:
```bash
terravision draw --source ~/src/terraform --debug
```

This will:
- Show detailed processing steps
- Export intermediate JSON files
- Display full error traces
- Show detailed intermediate variable information

### Getting Help

For detailed help on any command:
```bash
terravision --help
terravision draw --help
terravision graphdata --help
```

## Performance Tips

1. **Large Terraform Projects**
   - Use `--simplified` for overview diagrams
   - Export to JSON first, then generate multiple diagram variants
   - Use specific workspaces to reduce scope

2. **CI/CD Integration**
   ```bash
   # Example CI pipeline step
   terravision draw --source . --format svg --outfile architecture-${BUILD_NUMBER}
   ```

3. **Batch Processing**
   ```bash
   # Generate multiple formats
   for format in png svg pdf; do
     terravision draw --source . --format $format --outfile arch-$format
   done
   ```

## Version Information

**Current Version:** 0.8

**Recent Updates:**
- Enhanced cloud provider support
- Improved JSON export capabilities
- Better error handling and debugging
- Performance optimizations for large projects
