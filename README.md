# TerraVision
TerraVision is a CLI tool that converts Terraform code into Professional Cloud Architecture Diagrams. Envisioned to be a Docs as Code tool that can be included in your CI/CD pipeline for automatically generating architecture diagrams that are accurate and always up to date. Supports AWS and soon Google and Azure cloud.

Turn this... 

![Terraform Code](./code.png "Turn Terraform code")

into this...

<img src="./architecture.dot.png" width="640" height="580">


This software is still in alpha testing and **code is shared on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied. Use at your own risk.

# Benefits of Terravision
1. Cost
	- Save Visio/Drawing software licenses - Terravision is free and open source
	- Doesn't require any cost incurring cloud resources to be spun up, it works instantly from your local machine
2. Accelerate and Automate
	- Wasting time with diagram tools aligning, connecting dots and laying out icons is not the best use of a highly paid architects time
	- Use TF variable files as inputs to create multiple variant diagrams from the same TF code
	- Automate creation of architecture diagrams by running terravision as part of CI/CD pipelines
	- YAML based Diagrams as code allows you to Annotate generated diagrams with additional custom labels and resources  e.g. unmanaged resources or external systems not captured in TF code
3. Consistency across organisation
	- Do you have standard modules or code blocks for all applications? Terravision auto downloads external modules to ensure the most updated architecture shown for all downstream Terraform projects
	- Consistent design of architecture diagrams using industry standard icons and style across teams (Standardised company logo, specific png artwork also possible)
4. Accurate Visibility 
	- Real time state of diagram shows current infrastructure that matches exactly what is deployed in production, not a diagram of how the app looked 6 months ago
	- Helps in architecture reviews, auditing, monitoring, reporting and debugging of the stack in a visual way
	- Custom Diagram code and output images can be put into source/version control for better maintainability and discoverability
5. Security
	- Don't need to give access to your AWS account or CLI to draw diagram
	- Doesn't create intrusive cloud resources  e.g. scanning instances or metadata tables which enterprises would need to approve
    - All source code stays in your local environment, diagrams are generated on your machines

# Installation and Usage

## Dependencies for all versions
* graphviz https://graphviz.org/download/
* git https://git-scm.com/downloads

## Quickstart
1. Install all dependencies as listed above
2. Download terravision binary for your platform from here
3. Copy binary to your `PATH` e.g. /usr/bin
4. Run `terravision` and specify your Terraform source files in the format:
``` bash
$ terravision --source ~/src/my-terraform-code
```

For Terraform source code in a Git repo you can also use the form:
``` bash
$ terravision --source https://github.com/your-repo/terraform-examples.git
```

## Install from source code
1. Clone the repo with ``git clone https://github.com/patrickchugh/terravision.git``
2. Ensure you are have Python 3.7 or above installed and working. Install python depdendecies
```
pip3 install pytest pyinstaller click python-hcl2 gitPython graphviz requests tqdm pyyaml
```
3. Add the `terravision` folder to your `$PATH` variable

## Annotating generated diagrams
No automatically generated diagram is going to have all the detail you need, at best it will get you 80-90% of the way there. To add custom annotations such as a main diagram title, additional labels on arrows or additional resources created outside your Terraform, include an `architecture.yml` file in the source code folder and it will be automatically loaded. Alternatively, specify a path to the annotations file as a parameter to terravision. 

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

# Detailed help

Type ``terravision --help`` for full command list or for help with a specific command
