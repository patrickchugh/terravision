#!/usr/bin/env python3
"""Build the terravision-cloud-diagrams dataset from the gallery examples.

    poetry run python scripts/hf_dataset/build_dataset.py --repo .            # build locally
    uv run --no-project --with huggingface_hub python scripts/hf_dataset/build_dataset.py --repo . --push

One row per examples/graphs/<name>.tvg.json: the prompt from that example's
section in docs/gallery.md (or from extra_prompts.json beside this script,
for an example without a gallery entry), the graph, its annotations file and
the rendered PNG. Render the examples first with scripts/render_examples.py;
this script copies their PNGs and renders nothing.

The output folder (default build/hf-dataset) is in Hugging Face ImageFolder
layout: data/metadata.jsonl, one JSON object per row whose file_name names
the PNG beside it, plus the dataset card README.md from this folder. --push
uploads it to patrickchugh/terravision-cloud-diagrams with huggingface_hub,
creating the dataset on the first push. It is not a project dependency:
the uv command above brings it, after `uvx --from huggingface_hub hf auth
login` with a write token.

Prints the row count and every example skipped, and exits 1 if any was.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET_REPO = "patrickchugh/terravision-cloud-diagrams"
PROVIDERS = (("tv_aws_", "aws"), ("aws_", "aws"), ("tv_azurerm_", "azure"),
             ("tv_azure_", "azure"), ("azurerm_", "azure"), ("tv_gcp_", "gcp"),
             ("google_", "gcp"))  # fmt: skip


def gallery_entries(gallery):
    """Map each example name to (title, prompt) from its docs/gallery.md section."""
    entries = {}
    for section in re.split(r"\n(?=## )", gallery.read_text()):
        image = re.search(r"\(assets/gallery/([a-z0-9-]+)\.webp\)", section)
        prompt = re.search(r"\*\*Ask your AI assistant:\*\*\n\n> (.+)\n", section)
        heading = re.match(r"## (.+?)(?: \{ #[^}]+\})?\n", section)
        if image and prompt:
            entries[image.group(1)] = (
                heading.group(1).strip() if heading else image.group(1),
                prompt.group(1).strip(),
            )
    return entries


def provider_of(graph):
    found = set()
    for node in set(graph) | {t for targets in graph.values() for t in targets}:
        for prefix, provider in PROVIDERS:
            if node.startswith(prefix):
                found.add(provider)
                break
    return found.pop() if len(found) == 1 else "multi"


def build(repo, out):
    examples = repo / "examples" / "graphs"
    entries = gallery_entries(repo / "docs" / "gallery.md")
    extra_path = HERE / "extra_prompts.json"
    extra = json.loads(extra_path.read_text()) if extra_path.exists() else {}

    if out.exists():
        shutil.rmtree(out)
    data = out / "data"
    data.mkdir(parents=True)
    rows, skipped = [], []
    for graph_path in sorted(examples.glob("*.tvg.json")):
        stem = graph_path.name[: -len(".tvg.json")]
        png = examples / f"{stem}.png"
        annotations = examples / f"{stem}.annotations.yml"
        title, prompt = entries.get(stem, (stem, extra.get(stem)))
        if not prompt:
            skipped.append(f"{stem}: no gallery prompt and no extra_prompts.json entry")
            continue
        if not png.exists():
            skipped.append(
                f"{stem}: {png.name} missing; run scripts/render_examples.py"
            )
            continue
        graph = json.loads(graph_path.read_text())
        shutil.copy(png, data / png.name)
        annotate = f" --annotate {annotations.name}" if annotations.exists() else ""
        rows.append({
            "file_name": png.name,
            "id": stem,
            "provider": provider_of(graph),
            "title": title,
            "prompt": prompt,
            "graph": json.dumps(graph, separators=(",", ":")),
            "annotations": annotations.read_text() if annotations.exists() else "",
            "node_count": len(set(graph) | {t for v in graph.values() for t in v}),
            "render_command": f"terravision draw --source {graph_path.name}{annotate} --format png",
        })  # fmt: skip
    with open(data / "metadata.jsonl", "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    shutil.copy(HERE / "README.md", out / "README.md")
    return rows, skipped


def push(out):
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit("--push needs huggingface_hub: pip install huggingface_hub")
    api = HfApi()
    # The first push creates the dataset; later ones find it there
    api.create_repo(DATASET_REPO, repo_type="dataset", exist_ok=True)
    api.upload_folder(
        repo_id=DATASET_REPO,
        repo_type="dataset",
        folder_path=str(out),
        commit_message="Update from the TerraVision gallery",
    )
    print(f"pushed {out} to https://huggingface.co/datasets/{DATASET_REPO}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="TerraVision checkout (default: .)")
    parser.add_argument(
        "--out", help="output folder (default: <repo>/build/hf-dataset)"
    )
    parser.add_argument("--push", action="store_true", help=f"upload to {DATASET_REPO}")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve() if args.out else repo / "build" / "hf-dataset"
    rows, skipped = build(repo, out)
    providers = {
        p: sum(r["provider"] == p for r in rows) for p in ("aws", "azure", "gcp")
    }
    print(f"wrote {len(rows)} rows to {out} "
          f"({', '.join(f'{k} {v}' for k, v in providers.items())}), {len(skipped)} skipped")  # fmt: skip
    for reason in skipped:
        print(f"  skipped {reason}")
    if skipped:
        return 1
    if args.push:
        push(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
