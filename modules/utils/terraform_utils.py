"""Terraform-specific utility functions for TerraVision.

This module provides utilities for working with Terraform variables,
variable files, and data extraction from Terraform configurations.
"""

import os
from typing import Any, Dict


def getvar(
    variable_name: str, all_variables_dict: Dict[str, Any], default: Any = "NOTFOUND"
) -> Any:
    """Retrieve a Terraform variable value from environment or variables dictionary.

    Supports both direct variable lookups and nested access using dotted paths and
    list indices. When a variable cannot be resolved, returns ``default`` (defaults
    to ``"NOTFOUND"`` for backwards compatibility).

    Args:
        variable_name: Name or dotted path of the variable to retrieve (without
            leading ``var.`` prefix).
        all_variables_dict: Dictionary containing Terraform variables or nested
            data structures to traverse.
        default: Value returned when the variable cannot be resolved.

    Returns:
        Resolved variable value or ``default`` when not found.

    Raises:
        TerraformParsingError: If the access path syntax is invalid (e.g., missing
            closing bracket or non-numeric list index).
    """
    from modules.exceptions import TerraformParsingError

    if not variable_name:
        return default

    env_var = os.getenv(f"TF_VAR_{variable_name}")
    if env_var is not None:
        return env_var

    simple_lookup = "." not in variable_name and "[" not in variable_name
    if simple_lookup and isinstance(all_variables_dict, dict):
        if variable_name in all_variables_dict:
            return all_variables_dict[variable_name]
        for key in all_variables_dict:
            if key.lower() == variable_name.lower():
                return all_variables_dict[key]
        return default

    tokens = []
    path = variable_name
    idx = 0
    while idx < len(path):
        char = path[idx]
        if char == "[":
            end_idx = path.find("]", idx)
            if end_idx == -1:
                raise TerraformParsingError(
                    "Invalid access path: missing closing bracket",
                    context={"path": variable_name},
                )
            tokens.append(path[idx : end_idx + 1])
            idx = end_idx + 1
        elif char == ".":
            idx += 1
        else:
            start_idx = idx
            while idx < len(path) and path[idx] not in ".[]":
                idx += 1
            tokens.append(path[start_idx:idx])

    current: Any = all_variables_dict
    for token in tokens:
        if not token:
            return default
        if token.startswith("[") and token.endswith("]"):
            if not isinstance(current, list):
                return default
            index_str = token[1:-1]
            if not index_str.isdigit():
                raise TerraformParsingError(
                    "List index must be numeric",
                    context={"path": variable_name, "token": token},
                )
            index = int(index_str)
            if index >= len(current):
                return default
            current = current[index]
        else:
            if not isinstance(current, dict):
                return default
            if token in current:
                current = current[token]
            else:
                lowered = {key.lower(): key for key in current.keys()}
                match = lowered.get(token.lower())
                if match is None:
                    return default
                current = current[match]

    return current


def tfvar_read(filepath: str) -> Dict[str, Any]:
    """Read and parse a Terraform variable file (.tfvars).

    Args:
        filepath: Path to .tfvars file (HCL or JSON format)

    Returns:
        dict: Parsed variable definitions

    Raises:
        FileNotFoundError: If file does not exist
        TerraformParsingError: If file cannot be parsed
    """
    import json
    from contextlib import suppress
    from pathlib import Path

    from modules.exceptions import TerraformParsingError

    if not Path(filepath).exists():
        raise FileNotFoundError(f"Variable file not found: {filepath}")

    # Try parsing as JSON first
    with suppress(json.JSONDecodeError):
        with open(filepath, "r") as f:
            return json.load(f)

    # Try parsing as HCL2
    try:
        import hcl2  # type: ignore

        with open(filepath, "r") as f:
            parsed_data = hcl2.load(f)  # type: ignore
            # HCL2 parser returns nested dicts - flatten variable values
            if isinstance(parsed_data, dict):
                return {
                    k: v[0] if isinstance(v, list) and len(v) == 1 else v
                    for k, v in parsed_data.items()
                }
            return parsed_data
    except Exception as e:
        raise TerraformParsingError(
            f"Failed to parse variable file: {filepath}",
            context={"error": str(e), "filepath": filepath},
        )
