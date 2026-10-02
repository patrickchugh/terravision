---
title: Diagram to Terraform (generate Terraform from an architecture diagram)
description: Design a cloud architecture as a diagram with your AI assistant, then generate the Terraform for it, verify the code by redrawing it, and keep the diagram in sync in CI.
---

# Diagram to Terraform

TerraVision works in both directions. Design a cloud architecture as a diagram with your AI assistant, then have the assistant write the Terraform for it. Draw the new code with TerraVision to confirm it matches the design, and let CI redraw the diagram whenever the code changes. Design, code and documentation stay the same thing.

## How do I generate Terraform from an architecture diagram?

1. Draw the design from a description in Claude, ChatGPT, Copilot or Cursor with TerraVision connected ([setup](ai-assistants.md)), and refine it until it is right.
2. Ask: *"Write the Terraform for this architecture."* The assistant writes Terraform for the resources, zones and connections in the diagram.
3. Verify: ask the assistant to draw the new Terraform. TerraVision builds that diagram from `terraform plan`, so you can compare it with the design.
4. Ask: *"Keep this diagram up to date in CI."* The assistant adds a workflow that redraws the diagram on every change.

## Why does starting from a TerraVision diagram help?

A TerraVision diagram is backed by a graph whose nodes are named with real Terraform resource types, such as `aws_ecs_service` or `azurerm_subnet`. The assistant is not guessing from a picture: it translates a structured list of resources, containers and connections into code, which leaves much less room for invention.

## How do I know the generated Terraform matches the diagram?

Draw it. TerraVision runs `terraform plan` on the generated code and renders what the plan says will be deployed. If the two diagrams differ, the code differs from the design. This step needs the cloud credentials Terraform would normally use, or a pre-generated plan file.

## Are the flows and labels from the design kept?

Yes. If the design has numbered request flows or connection labels, the assistant also writes a `terravision.yml` next to the Terraform. TerraVision reads it every time it draws the code, so later diagrams keep the same title, steps and labels.

## Is the generated Terraform production ready?

Treat it as a first draft. The quality depends on the AI model you use, and the assistant writes the code, not TerraVision. Review it, run `terraform plan` yourself, and apply your own security and naming standards before deploying.

## Which clouds are supported?

AWS, Azure and Google Cloud, one cloud per diagram. You can also ask the assistant to redraw a design on another cloud, for example *"draw the same thing on Azure"*, before generating the code.

## Related

- [AI cloud architecture diagram generator](ai-cloud-architecture-diagram-generator.md): description to diagram
- [Terraform diagram generator](terraform-diagram-generator.md): code to diagram
- [Use TerraVision with AI assistants](ai-assistants.md): the full round trip
