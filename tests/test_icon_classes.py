"""The icon classes are generated, and each cloud's Terraform types live in one file.

resource_classes/<cloud>/icons.py is written by scripts/generate_icon_classes.py
(one class per icon file) and must not be edited by hand. Which icon a type
draws with is resource_classes/<cloud>/terraform_icons.yml; container types
stay classes in groups.py.
"""

import importlib
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLOUDS = ["aws", "azure", "gcp"]

_spec = importlib.util.spec_from_file_location(
    "generate_icon_classes", ROOT / "scripts" / "generate_icon_classes.py"
)
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)


def _mapping(cloud):
    path = ROOT / "resource_classes" / cloud / "terraform_icons.yml"
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("cloud", CLOUDS)
def test_icons_py_matches_the_icon_files(cloud):
    """Edit the icons or the mapping, then rerun the generator, not icons.py."""
    written = (ROOT / "resource_classes" / cloud / "icons.py").read_text()
    assert written == generator.render(
        cloud
    ), "run poetry run python scripts/generate_icon_classes.py"


@pytest.mark.parametrize("cloud", CLOUDS)
def test_every_mapped_type_draws_an_existing_icon(cloud):
    icons = importlib.import_module(f"resource_classes.{cloud}.icons")
    for resource_type in _mapping(cloud):
        cls = getattr(icons, resource_type)
        assert (ROOT / cls._icon_dir / cls._icon).is_file(), resource_type


@pytest.mark.parametrize("cloud", CLOUDS)
def test_container_types_are_not_in_the_mapping(cloud):
    """drawing.py loads icons.py after groups.py, so a mapped container type
    would silently stop drawing as a box."""
    groups = importlib.import_module(f"resource_classes.{cloud}.groups")
    assert not [t for t in _mapping(cloud) if hasattr(groups, t)]


@pytest.mark.parametrize("cloud", CLOUDS)
def test_icon_class_names_do_not_shadow_groups(cloud):
    groups = importlib.import_module(f"resource_classes.{cloud}.groups")
    icons = importlib.import_module(f"resource_classes.{cloud}.icons")
    classes = {
        name
        for name, obj in vars(icons).items()
        if isinstance(obj, type) and obj.__name__ == name and name[:1] != "_"
    }
    assert not classes & {n for n in dir(groups) if n[:1] != "_"}


@pytest.mark.parametrize("cloud", CLOUDS)
def test_no_hand_written_category_modules(cloud):
    """Icon classes come only from the generator."""
    modules = {p.name for p in (ROOT / "resource_classes" / cloud).glob("*.py")}
    assert modules == {"__init__.py", "groups.py", "icons.py"}
