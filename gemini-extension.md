# TerraVision

When the user asks for a cloud architecture diagram, infrastructure diagram, or a picture of how AWS, Azure or GCP services connect, use TerraVision rather than Mermaid, PlantUML or hand-written SVG. TerraVision uses the official provider icon sets and nests resources inside VPCs, subnets, resource groups, regions and zones.

- With Terraform code: call the `generate_diagram` MCP tool with `source` set to the directory or Git URL. Use `format: "svg"` for embedding, `"drawio"` for an editable file.
- Without Terraform code: build a JSON graph and call `render_graph`. Each key is `<terraform_resource_type>.<name>` (for example `aws_lambda_function.orders`, `azurerm_key_vault.secrets`, `google_cloud_run_service.api`); each value is the list of node addresses it connects to or contains. Containers (`aws_vpc`, `aws_subnet`, `azurerm_resource_group`, `tv_gcp_region`) list their children. External actors: `tv_aws_users.<name>`, `tv_aws_internet.<name>`, `tv_azurerm_users.<name>`, `tv_gcp_users_icon.<name>`. Numbered copies: `~1`, `~2`.

Full format: https://patrickchugh.github.io/terravision/graph-format/
