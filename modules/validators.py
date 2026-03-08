"""Validation functions for TerraVision inputs.

This module provides validation for source paths, plan files, graph files,
and cross-input consistency checks.
"""

import json
import os
import sys
from typing import Any, Dict, List

import click

import modules.helpers as helpers


def validate_source(source: List[str]) -> None:
    """Validate source input before processing.

    Args:
        source: List of source paths

    Raises:
        SystemExit: If source is invalid
    """
    src = source[0]
    if src.endswith(".tf"):
        click.echo(
            click.style(
                "\nERROR: You have passed a .tf file as source. Please pass a folder containing .tf files or a git URL.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit()
    # Check if source looks like a local path (not a URL or JSON file)
    if (
        not src.endswith(".json")
        and not helpers.check_for_domain(src)
        and not src.startswith("git::")
        and not os.path.exists(src)
    ):
        click.echo(
            click.style(
                f"\nERROR: Source directory not found: {src}\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def validate_planfile(planfile: str) -> dict:
    """Load and validate a Terraform plan JSON file.

    Args:
        planfile: Path to the plan JSON file

    Returns:
        Parsed plan data dictionary

    Raises:
        SystemExit: If the file is invalid
    """
    try:
        with open(planfile, "r") as f:
            first_bytes = f.read(4)
            f.seek(0)
            # Detect binary .tfplan file
            if not first_bytes.strip().startswith("{"):
                click.echo(
                    click.style(
                        "\nERROR: File is not valid JSON. If this is a binary .tfplan file, "
                        "convert it with: terraform show -json tfplan.bin > plan.json\n",
                        fg="red",
                        bold=True,
                    )
                )
                sys.exit(1)
            plandata = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(
            click.style(
                f"\nERROR: File is not valid JSON: {e}\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)

    if "resource_changes" not in plandata:
        click.echo(
            click.style(
                "\nERROR: Not a Terraform plan JSON. Missing 'resource_changes' key. "
                "Generate with: terraform show -json tfplan.bin > plan.json\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)

    if len(plandata["resource_changes"]) == 0:
        click.echo(
            click.style(
                "\nERROR: No resources found in plan. The plan contains zero resource changes.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)

    format_version = plandata.get("format_version", "")
    if format_version and not format_version.startswith("1."):
        click.echo(
            click.style(
                f"WARNING: Unrecognized plan format version '{format_version}'. "
                "Proceeding with best-effort processing.",
                fg="yellow",
            )
        )

    return plandata


def validate_consistency(tfdata: Dict[str, Any]) -> None:
    """Validate consistency across plan, graph, and source inputs.

    Performs two lightweight checks per FR-014:
    1. Provider prefix matches across plan resources and source resources
    2. First managed resource in plan exists in graph and source

    Args:
        tfdata: Terraform data dictionary with plan, graph, and source data

    Raises:
        SystemExit: If consistency checks fail
    """
    # Find first managed resource from plan
    first_resource = None
    first_resource_type = None
    for rc in tfdata.get("tf_resources_created", []):
        if rc.get("mode") == "managed":
            first_resource = rc["address"]
            first_resource_type = rc["type"]
            break

    if not first_resource:
        return

    # Check 1: Provider prefix from plan matches source resources
    prefix = first_resource_type.split("_")[0] + "_"
    all_resource = tfdata.get("all_resource", {})
    if all_resource:
        # all_resource keys are file paths; extract actual resource type names
        # from the nested structure: {filepath: [{"aws_vpc": {...}}, ...]}
        resource_type_names = []
        for _filepath, resource_list in all_resource.items():
            if isinstance(resource_list, list):
                for item in resource_list:
                    if isinstance(item, dict):
                        resource_type_names.extend(item.keys())
        source_has_prefix = any(name.startswith(prefix) for name in resource_type_names)
        if not source_has_prefix:
            click.echo(
                click.style(
                    f"\nERROR: Inputs appear to be from different projects. "
                    f"Plan resources use '{prefix}' prefix but source directory "
                    f"contains no matching resource types.\n",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit(1)

    # Check 2: First plan resource exists in graph
    graphdict = tfdata.get("graphdict", {})
    if graphdict:
        resource_in_graph = any(
            first_resource in k or first_resource.split(".")[-1] in k
            for k in graphdict.keys()
        )
        if not resource_in_graph:
            click.echo(
                click.style(
                    f"\nERROR: Inputs appear to be from different projects. "
                    f"Plan resource '{first_resource}' not found in graph.\n",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit(1)


def validate_pregenerated_inputs(
    planfile: str, graphfile: str, source: List[str]
) -> None:
    """Validate that all required inputs are provided for pre-generated mode.

    Args:
        planfile: Path to plan JSON file
        graphfile: Path to graph DOT file
        source: List of source paths

    Raises:
        SystemExit: If required inputs are missing or invalid
    """
    if graphfile and not planfile:
        click.echo(
            click.style(
                "\nERROR: --graphfile requires --planfile.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
    if planfile and not graphfile:
        click.echo(
            click.style(
                "\nERROR: --planfile requires --graphfile and --source.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
    if planfile and (
        not source or source == (".",) or source == ["."] or not source[0]
    ):
        click.echo(
            click.style(
                "\nERROR: --planfile requires --graphfile and --source.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
    if planfile and source[0].endswith(".json"):
        click.echo(
            click.style(
                "\nERROR: --source must be a directory when using --planfile.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
    if planfile and not os.path.isfile(planfile):
        click.echo(
            click.style(
                f"\nERROR: Plan file not found: {planfile}\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
    if graphfile and not os.path.isfile(graphfile):
        click.echo(
            click.style(
                f"\nERROR: Graph file not found: {graphfile}\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit(1)
