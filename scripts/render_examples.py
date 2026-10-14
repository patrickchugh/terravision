#!/usr/bin/env python3
"""Render every gallery example and refresh what is generated from them.

    poetry run python scripts/render_examples.py                 # out-of-date examples
    poetry run python scripts/render_examples.py --force         # every example
    poetry run python scripts/render_examples.py aws-batch-hpc   # just these

For each examples/graphs/<name>.tvg.json this validates the graph, renders it
with its <name>.annotations.yml to <name>.png and <name>.svg beside it, and
prints every warning: the validator's (a node listed in two boxes, an arrow to
a container or a shared service), TerraVision's own (a flow step or arrow
label that draws nothing, an update naming a missing node) and the gallery's
(a network or subnet without a CIDR range, fewer than two flows). An example
whose PNG is newer than its graph and annotations is skipped unless --force,
but is still checked.

Then it runs scripts/make_gallery_images.py for the web-sized copies, sets
each gallery image's width and height in docs/gallery.md from them, and runs
scripts/update_llms_examples.py for the example list in docs/llms.txt and
docs/llms-full.txt.

Exits 1 if any example fails to validate or render. Warnings are printed but
do not fail the run; tests/test_examples_gallery.py fails on them.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "graphs"
GALLERY = ROOT / "docs" / "gallery.md"
MANIFEST = ROOT / "docs" / "assets" / "gallery" / "sources.json"
VALIDATOR = (
    ROOT / "skills" / "terravision-cloud-diagrams" / "scripts" / "validate_graph.py"
)
FORMATS = ("png", "svg")

# Boxes whose label shows a CIDR range, and the attributes that set it.
CIDR_ATTRIBUTES = {
    "aws_vpc": "cidr_block",
    "aws_subnet": "cidr_block",
    "azurerm_virtual_network": "address_space",
    "azurerm_subnet": "address_prefixes",
    "google_compute_subnetwork": "ip_cidr_range",
}
MIN_FLOWS = 2

sys.path.insert(0, str(ROOT))


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_graph", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stems():
    return sorted(p.name[: -len(".tvg.json")] for p in EXAMPLES.glob("*.tvg.json"))


def sources(stem):
    graph = EXAMPLES / f"{stem}.tvg.json"
    annotations = EXAMPLES / f"{stem}.annotations.yml"
    return graph, annotations if annotations.exists() else None


def check(stem):
    """Return (errors, warnings) for one example, without rendering it."""
    import yaml

    from modules import annotations as tv_annotations

    validator = load_validator()
    graph_path, annotations_path = sources(stem)
    graph = json.loads(graph_path.read_text())
    errors = validator.validate(graph)
    if errors:
        return errors, []
    found = list(validator.warnings(graph))
    if annotations_path is None:
        return [], found + [f"no {stem}.annotations.yml"]

    loaded = yaml.safe_load(annotations_path.read_text()) or {}
    tfdata = {"graphdict": graph, "meta_data": {}}
    flows = loaded.get("flows") or {}
    found += tv_annotations.flow_warnings(flows, graph)
    found += tv_annotations.apply_edge_labels(tfdata, loaded.get("connect"))
    found += tv_annotations.apply_attribute_updates(tfdata, loaded.get("update"))
    found += _hidden_arrow_warnings(validator, flows, loaded.get("connect"))

    if len(flows) < MIN_FLOWS:
        found.append(
            f"has {len(flows)} flow(s); gallery examples have {MIN_FLOWS} or more"
        )
    update = loaded.get("update") or {}
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    for node in sorted(nodes):
        attribute = CIDR_ATTRIBUTES.get(validator.type_of(node))
        if attribute and attribute not in (update.get(node) or {}):
            found.append(
                f"{node} has no {attribute} in update:, so its box shows no CIDR range"
            )
    return [], found


def _hidden_arrow_warnings(validator, flows, connect):
    """Flow steps and labels on arrows that are not drawn: to a shared service."""

    def hidden(src, dst):
        for a, b in ((src, dst), (dst, src)):
            if validator.type_of(a) in validator.SHARED_SERVICES:
                return a
            if (
                validator.type_of(b) in validator.SHARED_SERVICES
                and validator.type_of(a) not in validator.ALWAYS_DRAW_LINE
            ):
                return b
        return None

    found = []
    number = 0
    for name, flow in flows.items():
        for step in flow.get("steps") or []:
            number += 1
            ref = step.get("resource", "")
            if " -> " in ref:
                src, dst = (part.strip() for part in ref.split(" -> ", 1))
                shared = hidden(src, dst)
                if shared:
                    found.append(
                        f"Step {number} of flow {name!r} draws no badge: arrows "
                        f"to {shared} are not drawn (shared service)."
                    )
    for src, entries in (connect or {}).items():
        for entry in entries if isinstance(entries, list) else [entries]:
            for dst in entry if isinstance(entry, dict) else [entry]:
                shared = hidden(src, dst)
                if shared:
                    found.append(
                        f"The label on {src} -> {dst} is not drawn: arrows to "
                        f"{shared} are not drawn (shared service)."
                    )
    return found


def is_fresh(stem):
    graph, annotations = sources(stem)
    outputs = [EXAMPLES / f"{stem}.{fmt}" for fmt in FORMATS]
    if not all(out.exists() for out in outputs):
        return False
    newest_source = max(p.stat().st_mtime for p in (graph, annotations) if p)
    return (EXAMPLES / f"{stem}.png").stat().st_mtime > newest_source


def render(stem, outdir=EXAMPLES, formats=FORMATS):
    """Render one example into outdir as <stem>.<fmt>.

    Returns the WARNING lines TerraVision printed. Raises RuntimeError with
    its output when a render fails.
    """
    graph, annotations = sources(stem)
    printed = []
    for fmt in formats:
        command = [
            sys.executable, "-m", "terravision.terravision", "draw",
            "--source", str(graph), "--format", fmt, "--outfile", stem,
        ]  # fmt: skip
        if annotations:
            command += ["--annotate", str(annotations)]
        result = subprocess.run(
            command, cwd=outdir, capture_output=True, text=True, check=False
        )
        output = result.stdout + result.stderr
        drawn = Path(outdir) / f"{stem}.dot.{fmt}"
        if result.returncode != 0 or not drawn.exists():
            raise RuntimeError(output.strip()[-2000:])
        drawn.replace(Path(outdir) / f"{stem}.{fmt}")
        for line in output.splitlines():
            if "WARNING:" in line:
                text = line.split("WARNING:", 1)[1].strip()
                if text not in printed:
                    printed.append(text)
    return printed


def sync_gallery_sizes():
    """Set each gallery image's width and height from the WebP it shows."""
    if not MANIFEST.exists():
        return 0
    sizes = json.loads(MANIFEST.read_text())
    text = GALLERY.read_text()

    def resize(match):
        entry = sizes.get(match.group("stem"))
        if not entry:
            return match.group(0)
        return (
            f"{match.group('head')}width={entry['width']} " f"height={entry['height']}"
        )

    pattern = re.compile(
        r"(?P<head>\(assets/gallery/(?P<stem>[a-z0-9-]+)\.webp\)\{ )"
        r"width=\d+ height=\d+"
    )
    updated, count = pattern.subn(resize, text)
    if updated != text:
        GALLERY.write_text(updated)
    return count


def run_script(name):
    sys.stdout.flush()
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name)], check=False
    ).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="example names (default: all)")
    parser.add_argument(
        "--force", action="store_true", help="render up-to-date examples too"
    )
    args = parser.parse_args()

    names = args.names or stems()
    unknown = sorted(set(names) - set(stems()))
    if unknown:
        print(f"no such example: {', '.join(unknown)}", file=sys.stderr)
        return 1

    failed, warned, rendered = [], 0, 0
    for stem in names:
        errors, found = check(stem)
        if errors:
            failed.append(stem)
            print(f"FAIL  {stem}: does not validate")
            for error in errors:
                print(f"      {error}")
            continue
        if args.force or not is_fresh(stem):
            try:
                printed = render(stem)
            except RuntimeError as error:
                failed.append(stem)
                print(f"FAIL  {stem}: render failed\n{error}")
                continue
            found += [w for w in printed if w not in found]
            rendered += 1
            status = "drew"
        else:
            status = "ok  "
        print(f"{status}  {stem}" + (f"  ({len(found)} warnings)" if found else ""))
        for warning in found:
            print(f"      WARNING: {warning}")
        warned += len(found)

    print(f"\n{rendered} rendered, {len(names) - rendered - len(failed)} up to date, "
          f"{len(failed)} failed, {warned} warnings")  # fmt: skip

    if run_script("make_gallery_images.py") != 0:
        failed.append("make_gallery_images.py")
    print(f"gallery image sizes checked: {sync_gallery_sizes()}")
    if run_script("update_llms_examples.py") != 0:
        failed.append("update_llms_examples.py")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
