#!/usr/bin/env python3
"""Build the Claude Desktop extension (.mcpb) and the skill .zip for a release.

    python scripts/build_mcpb.py                       # dist/terravision-<version>.mcpb
    python scripts/build_mcpb.py --local-wheel dist/terravision-X.whl
    python scripts/build_mcpb.py --git-ref my-branch

The extension in mcpb/ uses the uv runtime: Claude Desktop installs
``terravision[mcp]`` from PyPI with uv and runs it, so the bundle pins the
exact version in pyproject.toml. For testing a release before it is on
PyPI, ``--local-wheel`` points the bundle at a locally built wheel (this
machine only) and ``--git-ref`` at a pushed branch or tag on GitHub (any
machine with Git).

The skill zip is the skills/terravision-cloud-diagrams folder, for apps that
take uploaded skills but do not run the MCP server. The extension itself needs
no skill: the server serves the same guidance through diagram_guide.

Needs Node.js: the bundle is validated and packed with the official
``@anthropic-ai/mcpb`` CLI through npx.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCPB_CLI = "@anthropic-ai/mcpb@2"
SKILL = ROOT / "skills" / "terravision-cloud-diagrams"


def release_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def mcpb(*args: str) -> None:
    subprocess.run(["npx", "--yes", MCPB_CLI, *args], check=True)


def build_bundle(
    version: str, dist: Path, local_wheel: Path = None, git_ref: str = None
) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "terravision"
        shutil.copytree(ROOT / "mcpb", stage)
        for name in ("manifest.json", "pyproject.toml"):
            path = stage / name
            path.write_text(path.read_text().replace("__VERSION__", version))
        source = None
        if local_wheel:
            source = local_wheel.resolve().as_uri()
        elif git_ref:
            source = f"git+https://github.com/patrickchugh/terravision@{git_ref}"
        if source:
            pyproject = stage / "pyproject.toml"
            pyproject.write_text(
                pyproject.read_text().replace(
                    f'"terravision[mcp]=={version}"',
                    f'"terravision[mcp] @ {source}"',
                )
            )
        mcpb("validate", str(stage / "manifest.json"))
        out = dist / f"terravision-{version}.mcpb"
        mcpb("pack", str(stage), str(out))
    return out


def build_skill_zip(version: str, dist: Path) -> Path:
    out = dist / f"terravision-cloud-diagrams-skill-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                zf.write(path, path.relative_to(SKILL.parent))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--local-wheel",
        type=Path,
        help="install TerraVision from this wheel instead of PyPI (testing only)",
    )
    parser.add_argument(
        "--git-ref",
        help="install TerraVision from this GitHub branch or tag (testing only)",
    )
    args = parser.parse_args()
    version = release_version()
    args.dist.mkdir(parents=True, exist_ok=True)
    for built in (
        build_bundle(version, args.dist, args.local_wheel, args.git_ref),
        build_skill_zip(version, args.dist),
    ):
        print(
            f"built {built.relative_to(ROOT) if built.is_relative_to(ROOT) else built}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
