# TerraVision
TerraVision converts Terraform code to Professional Cloud Architecture Diagrams. Envisioned to be a Docs as Code tool that can be included in your CI/CD pipeline for automatically generating architecture diagrams that are accurate and always up to date. Supports AWS and soon Google and Azure cloud.

## Dependencies
* graphviz
* git


## Quickstart
1. Install all dependencies as listed above
2. Download terravision binary for your platform from here
3. Copy binary to your `PATH` e.g. /usr/bin
4. Run `terravision` and specify your Terraform source files in the format:
```
$ terravision --source ~/src/my-terraform-code
```

For Terraform source code in a Git repo you can also use the form:
```
$ terravision --source https://github.com/your-repo/terraform-examples.git
```

## Annotating generated diagrams
You may wish to add custom annotations such as a title, additional labels on arrows or other resources created outside your Terraform to your diagram. This can be accomplished by including an `architecture.yml` file along with your source code which will be automatically loaded. Alternatively, you can do so by specifying the path to the annotations file as parameter to terravision:

```
terravision --source https://github.com/your-repo/terraform-examples.git --annotate /Users/me/MyDocuments/annotations.yml
```

The format of this file is a standard YAML configuration file that is similar to the example below. The node names follow the same conventions as Terraform resource names and support wildcards. You can add a custom parameter to any TF resource called `edge_labels` to add text to the connection line to a specific resource node1:

```
format: 0.1
title: Serverless Wordpress Site
# Draw new connection lines that are not apparent from the Terraforms
connect:
  aws_rds_cluster.this:
    - aws_ssm_parameter.db_master_user : SSM Connection
# Remove connections between nodes that are currently shown
disconnect:
  aws_cloudwatch*.*:
    - aws_ecs_service.this
    - aws_ecs_cluster.this
# Delete the following nodes
remove:
  - aws_iam_role.task_execution_role
# Add the following nodes
add:
  aws_subnet.another_one :
    cidr_block: "123.123.1.1"
# Modify params/metadata of existing node
update:
  aws_ecs_service.this:
    # Add custom labels to the connection lines that already exist between ECS->RDS
    edge_labels:
      - aws_rds_cluster.this: Database Queries
  aws_cloudfront* :
    edge_labels:
      - aws_acm_certificate.this: SSL Cert
 # Make all resources starting with aws_ecs have the following label
  aws_ecs* :
   label: "My Custom Label"

```

