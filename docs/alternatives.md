---
title: TerraVision vs draw.io, Lucidchart, Eraser, Mermaid and other cloud diagram tools
description: How TerraVision compares with draw.io, Lucidchart, Visio, Cloudcraft, Eraser, Mermaid, D2, mingrammer Diagrams and live cloud scanners for creating cloud architecture diagrams.
---

# TerraVision compared with other cloud architecture diagram tools

Tools for cloud architecture diagrams fall into five groups: manual drawing tools (draw.io, Lucidchart, Visio), AI design workspaces (Eraser), diagram-as-code tools (Mermaid, D2, Diagrams), live cloud scanners (Hava, Cloudviz, Holori, Cloudcraft) and generators that draw from a description or from infrastructure code (TerraVision). This page says plainly where each one fits. Details about other products reflect our understanding in October 2026 and may have changed.

| | TerraVision | draw.io, Lucidchart, Visio | Eraser | Mermaid, D2 | Diagrams (mingrammer) | Live scanners (Hava, Cloudviz, Holori, Cloudcraft) |
|---|---|---|---|---|---|---|
| How you make a diagram | Describe it to Claude or ChatGPT, or point at Terraform | Drag, drop and connect by hand | Prompt, pasted code or image | Write a text DSL | Write Python code | Connect a cloud account |
| Diagram from a text prompt | Yes, through your AI assistant | Only if your organisation approves third-party models | Yes, built-in AI | Assistant writes Mermaid or D2 | No | No |
| Diagram from Terraform | Built from `terraform plan`, so modules, `count`, `for_each` and conditionals are resolved | No | AI interprets the files you paste | No | No | Deployed state, not code |
| Draw an environment you cannot log in to, or one not built yet | Yes, from the code and a variables file: `--varfile prod.tfvars` draws prod, `--varfile dev.tfvars` draws dev | Drawn by hand | From pasted code | Drawn by hand | Written by hand | No, draws the account it is connected to |
| Terraform from the design | Yes, written by your AI assistant and checked by redrawing the code | Lucidchart beta, AWS only, paid add-on | No | No | No | Varies |
| Official AWS, Azure, GCP icons | Yes | Yes, shape libraries | Yes | Not built in | Yes | Yes |
| VPC, subnet, zone grouping | Built in, per provider | Drawn by hand | Generic groups | Generic groups | Manual clusters | Built in |
| Stays current with the code | Redrawn in CI on every change | Manual updates | Repository sync | Manual updates | Manual updates | Follows the live account |
| Runs locally | Yes | draw.io and Visio: yes | No (SaaS) | Yes | Yes | No (SaaS) |
| Needs access to your cloud account | Not to the account it draws; Terraform needs credentials the provider accepts | No | No | No | No | Yes, read-only |
| Price | Free, open source | Free (draw.io) to paid | Free tier, paid plans | Free, open source | Free, open source | Paid plans |
| Other diagram types (sequence, ERD, flowchart) | No | Yes | Yes | Yes | No | No |

## TerraVision vs draw.io, Lucidchart and Visio

draw.io, Lucidchart and Visio are manual drawing tools: you drag icons from the AWS, Azure or GCP shape libraries, draw the boxes and connect them by hand. They give you complete control and take the most time, and the diagram goes out of date when the system changes. draw.io and Lucidchart have added AI diagram generators, but they send your prompt to third-party models, so they are an option only if your organisation approves them. TerraVision works inside the assistant you already use through MCP, so it needs no new vendor or AI approval. TerraVision generates the diagram from a description or from Terraform, with the grouping and layout done for you. The two work well together: generate with TerraVision, export as a draw.io file, and do the final polish by hand in draw.io or Lucidchart. SVG output can be placed in PowerPoint or Visio.

## TerraVision vs Cloudcraft

Cloudcraft is a hosted designer best known for isometric AWS diagrams, and it can import a live AWS environment. It no longer exports Terraform. It is a commercial product. TerraVision produces the flat, official-style diagrams used in vendor reference architectures, covers AWS, Azure and Google Cloud, needs no access to your cloud account, and is free. Choose Cloudcraft for 3D-style visuals of a running AWS estate; choose TerraVision for official-style diagrams from a description or from code.

## TerraVision vs Eraser

Eraser is a hosted design workspace: its AI turns a prompt or pasted code into a diagram you edit on a canvas, and it also covers flowcharts, ERDs, sequence and BPMN diagrams. For Terraform, Eraser's instructions are to paste the contents of your `.tf` or state files into the prompt, and its AI decides what to draw. Terraform state files can hold secrets such as database passwords and access keys in plain text, so pasting one into any hosted tool may breach your organisation's security policy. TerraVision only draws cloud architecture, but it builds the diagram from `terraform plan`, so modules, `count`, `for_each` and conditionals are resolved rather than interpreted, applies each provider's grouping conventions, runs locally and is free. Choose Eraser for collaborative whiteboard-style design across diagram types; choose TerraVision when the diagram must match the code or must not leave your machine.

## TerraVision vs Mermaid and D2

Mermaid and D2 are general-purpose text diagram languages, each with its own syntax to learn, and the better choice for sequence diagrams, flowcharts and class diagrams. For cloud architecture neither has the official AWS, Azure or GCP icon sets built in (in D2 you link each node's icon by image URL), and neither has a notion of VPCs, subnets or zones. TerraVision's JSON graph is as short as either, uses Terraform resource names, and renders with official icons and provider grouping. AI assistants can use TerraVision for cloud diagrams and Mermaid or D2 for everything else.

## TerraVision vs Diagrams (mingrammer)

Diagrams is a Python library: you write a script that declares each node, cluster and edge, and it renders with Graphviz and official icons. It does not read Terraform. TerraVision needs no script: it derives the diagram from Terraform, or takes a plain JSON graph, and handles grouping and layout rules for you. Choose Diagrams if you want full manual control in Python; choose TerraVision to generate the diagram from existing infrastructure code or from an AI assistant.

## TerraVision vs live cloud scanners (Hava, Cloudviz, Holori)

Live scanners connect to your cloud accounts with read-only access and draw what is deployed, including drift and resources created by hand. They are hosted, commercial services. TerraVision draws the desired state from code, needs no access to the account it draws, and works before anything is deployed. Use a scanner to audit what is running; use TerraVision for design reviews, pull requests and documentation that follows the code.

A scanner can only draw an account it has been given access to. TerraVision draws from the code plus a variables file, so it can draw production for engineers who are not given production access, and it can draw an environment that does not exist yet: pass `--varfile prod.tfvars` and it shows what the code would deploy there.

## TerraVision vs `terraform graph`

`terraform graph` outputs a raw dependency graph in DOT format. TerraVision uses that graph as one input, enriches it with plan data, groups resources into networks and zones, and applies official icons to produce a readable architecture diagram.

## Which tool should I use to generate a cloud architecture diagram?

- You want to design in plain English, get the diagram, then the Terraform, and check one against the other: TerraVision.
- You have Terraform and want an accurate diagram: TerraVision.
- You want an AI assistant to draw AWS, Azure or GCP architecture with official icons, locally and free: TerraVision through its [MCP server](mcp-server.md).
- You draw diagrams by hand today in draw.io, Lucidchart or Visio: generate the first version with TerraVision, then polish the exported draw.io file.
- You want a shared canvas and many diagram types: Eraser.
- You want sequence diagrams or flowcharts in Markdown: Mermaid.
- You want to see what is actually deployed, including drift: a live cloud scanner.
