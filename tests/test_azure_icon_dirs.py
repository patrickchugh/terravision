"""
Regression tests that every Azure resource class points at an icon that exists.

``resource_classes/azure/databases.py`` declared ``resource_images/azure/database``
while its icons ship under ``resource_images/azure/databases``, so 41 of its 45
classes resolved to a missing file. Nothing warned about it: the alias resolved,
so the renderer believed it had an icon and drew an empty node.

``modules.drawing`` loads every module in the package into one namespace, so the
alphabetically last module wins. That made ``databases.py`` override the working
aliases in ``database.py``, and broke azurerm_redis_cache and
azurerm_postgresql_flexible_server for anyone using them.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

import resource_classes.azure as azure_classes

REPO_ROOT = Path(azure_classes.__file__).parents[2]


def _icon_classes():
    """Every class in resource_classes.azure that declares an icon."""
    found = []
    package_path = Path(azure_classes.__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
        module = importlib.import_module(f"resource_classes.azure.{module_name}")
        for name, obj in vars(module).items():
            if inspect.isclass(obj) and getattr(obj, "_icon", None):
                found.append(pytest.param(obj, id=f"{module_name}.{name}"))
    return found


ICON_CLASSES = _icon_classes()


def test_azure_icon_classes_were_discovered():
    assert ICON_CLASSES, "no icon classes found; the package layout changed"


@pytest.mark.parametrize("icon_class", ICON_CLASSES)
def test_icon_file_exists(icon_class):
    icon = REPO_ROOT / icon_class._icon_dir / icon_class._icon
    assert icon.is_file(), f"{icon_class.__name__} points at missing icon {icon}"
