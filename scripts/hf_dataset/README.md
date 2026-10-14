---
license: cc-by-4.0
task_categories:
  - text-generation
  - image-to-text
language:
  - en
tags:
  - cloud-architecture
  - aws
  - azure
  - gcp
  - terraform
  - diagrams
  - tool-use
  - structured-output
pretty_name: TerraVision Cloud Architecture Diagrams
size_categories:
  - n<1K
---

# TerraVision cloud architecture diagrams

Natural-language architecture descriptions, each paired with the [TerraVision Graph Format](https://patrickchugh.github.io/terravision/graph-format/) JSON that draws it, the annotations that title it, label its networks with CIDR ranges and number its flows, and the rendered diagram with the official AWS, Azure and Google Cloud icons.

Every row is an example from the [TerraVision gallery](https://patrickchugh.github.io/terravision/gallery/), designed the way a solutions architect on that cloud draws it for a design review: workloads in VPCs, subnets and zones, managed services reached through private endpoints, and numbered steps showing how requests and data move.

Intended use: teaching and evaluating language models to produce cloud architecture diagrams as structured JSON that a renderer turns into an architect-quality picture, instead of Mermaid box-and-arrow output.

## Fields

| field | description |
|---|---|
| `file_name` | the rendered PNG (shown as the `image` column) |
| `id` | example name, `<cloud>-<pattern>` |
| `provider` | `aws`, `azure` or `gcp` |
| `title` | the gallery heading |
| `prompt` | the request a user would give an AI assistant, naming every major service in the diagram |
| `graph` | TVG JSON: `{"<type>.<name>": ["<type>.<name>", ...]}` |
| `annotations` | YAML: `title`, `update` (CIDR ranges), `connect` (arrow labels) and `flows` (numbered steps) |
| `node_count` | number of nodes in the graph |
| `render_command` | the command that drew the image |

## Rendering

```bash
pipx install terravision      # plus Graphviz
terravision draw --source graph.tvg.json --annotate graph.annotations.yml --format png
```

Schema: https://patrickchugh.github.io/terravision/schemas/terravision-graph-1.0.schema.json

Source: [examples/graphs](https://github.com/patrickchugh/terravision/tree/main/examples/graphs) in the TerraVision repository, built with `scripts/hf_dataset/build_dataset.py`.

## Licence

Graph JSON, annotations and prompts: CC-BY-4.0. Rendered images include provider icons that remain subject to the AWS, Microsoft Azure and Google Cloud architecture icon terms of use (free to use in architecture diagrams).
