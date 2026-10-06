"""Every node type in the expected outputs has an icon or is hidden on purpose.

A type with no icon class is drawn as a blank generic box with a "no icon"
warning. Plumbing (permissions, policies, settings) belongs on the provider's
HIDE_NODES list with a reason; a real service needs an icon. This fails when
a fixture brings in a type that is neither, so the gap is noticed.
"""

import glob
import importlib.util
import json
from pathlib import Path

import pytest

from modules import helpers
from modules.config import cloud_config_aws, cloud_config_azure, cloud_config_gcp

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "gen_node_types", ROOT / "scripts" / "gen_node_types.py"
)
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
DRAWABLE = _gen.collect()
HIDDEN = (
    set(cloud_config_aws.AWS_HIDE_NODES)
    | set(getattr(cloud_config_azure, "AZURE_HIDE_NODES", []))
    | set(getattr(cloud_config_gcp, "GCP_HIDE_NODES", []))
)

EXPECTED = sorted(
    glob.glob(str(ROOT / "tests" / "json" / "expected-*.json"))
    + glob.glob(str(ROOT / "tests" / "json" / "*-expected.json"))
)


def _types(graph):
    names = set(graph) | {t for targets in graph.values() for t in targets}
    return {helpers.get_no_module_name(n).split(".")[0] for n in names}


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: Path(p).name)
def test_every_node_type_has_an_icon_or_is_hidden(path):
    graph = json.loads(Path(path).read_text())
    missing = sorted(
        t
        for t in _types(graph)
        if t not in DRAWABLE
        and t not in HIDDEN
        and not t.startswith(("null_", "random_", "time_"))
    )
    assert not missing, (
        f"No icon for {missing}: add an icon class, or put plumbing on the "
        "provider's HIDE_NODES list with a reason."
    )
