"""Plan-based resolution of Terraform module output references.

When the static HCL interpolation in interpreter.py cannot resolve a
``module.X.Y`` reference, this module uses the ``terraform plan`` JSON
output (``tfdata["plandata"]``) as a source of truth.

Strategy:
1. Parse ``module.A.B...Y`` into (module_path, output_name).
2. Navigate ``configuration.root_module.module_calls`` down module_path
   to find the output definition (``expression.constant_value`` or
   ``expression.references``).
3. For references, resolve the first resource reference against
   ``planned_values.root_module.child_modules[address=...].resources``
   to obtain the final resolved attribute value.
4. For nested ``module.X.Y`` references inside an output expression,
   recurse with the fully-qualified absolute path.
"""

from typing import Any, Dict, List, Optional, Set


# HCL built-in function names that can false-positive as module attributes
# when the regex in interpreter.py over-matches (see issue #190).
_HCL_FUNCTION_NAMES = frozenset(
    {
        "tomap",
        "tolist",
        "toset",
        "tostring",
        "tonumber",
        "tobool",
        "flatten",
        "for",
        "if",
        "lookup",
        "merge",
        "length",
        "concat",
        "element",
        "upper",
        "lower",
        "trim",
        "trimspace",
        "join",
        "split",
        "format",
        "formatlist",
        "contains",
        "keys",
        "values",
        "coalesce",
        "try",
        "compact",
        "distinct",
        "reverse",
        "sort",
        "slice",
        "abs",
        "ceil",
        "floor",
        "max",
        "min",
        "range",
        "cidrhost",
        "cidrnetmask",
        "cidrsubnet",
        "cidrsubnets",
        "jsonencode",
        "jsondecode",
        "yamlencode",
        "yamldecode",
    }
)


def is_hcl_function_suffix(module_var: str) -> bool:
    """Return True if the final segment of ``module_var`` is an HCL built-in.

    Used to suppress false-positive warnings like
    ``module.transit_gateway_attachments.tomap`` where ``tomap`` is a
    function call, not a module output.
    """
    # Strip index notation: "module.X[0].foo" -> last segment "foo"
    last = module_var.rsplit(".", 1)[-1]
    last = last.split("[")[0]
    return last in _HCL_FUNCTION_NAMES


def resolve_module_ref_from_plan(
    module_var: str,
    tfdata: Dict[str, Any],
    prefer: str = "address",
    _visited: Optional[Set[str]] = None,
) -> Optional[str]:
    """Resolve ``module.X.Y`` (or nested ``module.A.B.Y``) via plan data.

    Args:
        module_var: Flat module reference like ``"module.vpc.vpc_id"``.
        tfdata: Terraform data dict with ``plandata`` populated.
        prefer: ``"address"`` (default) returns the fully-qualified
            resource address (e.g. ``module.vpc.aws_vpc.main``) so
            downstream graph code can establish edges. ``"value"``
            returns the resolved attribute value (e.g.
            ``"172.68.0.0/16"``) for display/label use.
        _visited: Internal cycle-detection set; do not pass externally.

    Returns:
        Resolved string, or None if unresolvable.
    """
    if _visited is None:
        _visited = set()
    if module_var in _visited:
        return None
    _visited = _visited | {module_var}

    plan = tfdata.get("plandata") or {}
    config_root = (plan.get("configuration") or {}).get("root_module") or {}
    planned = plan.get("planned_values") or {}

    parts = module_var.split(".")
    if len(parts) < 3 or parts[0] != "module":
        return None

    current_config = config_root
    module_path_parts: List[str] = []
    i = 1
    while i < len(parts) - 1:
        name = parts[i].split("[")[0]
        mc = current_config.get("module_calls") or {}
        if name not in mc:
            break
        current_config = mc[name].get("module") or {}
        module_path_parts.append(parts[i])
        i += 1

    if i >= len(parts):
        return None

    output_name = parts[i]
    outputs = current_config.get("outputs") or {}
    if output_name not in outputs:
        return None

    expr = outputs[output_name].get("expression") or {}

    if "constant_value" in expr:
        val = expr["constant_value"]
        return None if val is None else str(val)

    refs = expr.get("references") or []
    if not refs:
        return None

    module_address = (
        "module." + ".".join(module_path_parts) if module_path_parts else ""
    )

    for ref in refs:
        resolved = _resolve_reference(
            ref, module_address, planned, tfdata, prefer, _visited
        )
        if resolved is not None:
            return resolved

    return None


def resolve_module_ref_to_value(
    module_var: str, tfdata: Dict[str, Any]
) -> Optional[str]:
    """Convenience wrapper: resolve ``module.X.Y`` to its string value."""
    return resolve_module_ref_from_plan(module_var, tfdata, prefer="value")


def _resolve_reference(
    ref: str,
    module_address: str,
    planned_values: Dict[str, Any],
    tfdata: Dict[str, Any],
    prefer: str,
    visited: Set[str],
) -> Optional[str]:
    """Resolve a single reference from an output's ``references`` list."""
    if ref.startswith("module."):
        rel = ref[len("module.") :]
        abs_ref = f"{module_address}.{rel}" if module_address else ref
        return resolve_module_ref_from_plan(abs_ref, tfdata, prefer, visited)

    parts = ref.split(".")
    if len(parts) < 2:
        return None

    resource_type = parts[0]
    resource_name = parts[1]
    attr = parts[2] if len(parts) >= 3 else None

    target_addr = (
        f"{module_address}.{resource_type}.{resource_name}"
        if module_address
        else f"{resource_type}.{resource_name}"
    )

    # Address-preferred mode: return target address even if values are empty.
    # Graph code (add_relations) needs the address to create edges; a
    # computed-after-apply null in planned_values shouldn't block that.
    if prefer == "address":
        resources = _find_module_resources(module_address, planned_values)
        for r in resources:
            if r.get("address") == target_addr:
                return target_addr
        # Resource not found in planned_values — still return the address;
        # it's a valid reference even if the plan didn't surface the resource.
        return target_addr

    # Value-preferred mode: return the resolved attribute value.
    resources = _find_module_resources(module_address, planned_values)
    for r in resources:
        if r.get("address") != target_addr:
            continue
        values = r.get("values") or {}
        if attr:
            val = values.get(attr)
            if val is not None:
                return str(val)
        # Either no attr requested, or attr was null (known-after-apply).
        # Try common identifying attrs as fallback.
        for candidate in ("id", "arn", "name", "cidr_block"):
            if candidate in values and values[candidate] is not None:
                return str(values[candidate])
        return None
    return None


def _find_module_resources(
    module_address: str, planned_values: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Return the resources list for ``module_address`` in planned_values."""
    root = planned_values.get("root_module") or {}
    if not module_address:
        return root.get("resources") or []

    def walk(node: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        for cm in node.get("child_modules") or []:
            if cm.get("address") == module_address:
                return cm.get("resources") or []
            sub = walk(cm)
            if sub is not None:
                return sub
        return None

    return walk(root) or []
