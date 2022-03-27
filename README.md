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


