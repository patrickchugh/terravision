"""A pre-generated plan draws without Terraform installed (issue #268).

--planfile with --graphfile reads the plan from its files and never runs
Terraform, as the docs promise, so the startup check must not ask for it.
"""

import shutil

import pytest

from modules import helpers
from terravision.terravision import preflight_check

_real_which = shutil.which


@pytest.fixture
def no_terraform(monkeypatch):
    def which(name, *args, **kwargs):
        if name in ("terraform", "tofu"):
            return None
        return _real_which(name, *args, **kwargs)

    monkeypatch.setattr(helpers.shutil, "which", which)
    monkeypatch.setattr(helpers.os.path, "isfile", lambda path: False)


@pytest.mark.parametrize(
    "source, planfile, expected",
    [
        ("./infra", "", True),
        ("./infra", "plan.json", False),
        ("architecture.tvg.json", "", False),
        ("tfdata.json", "", False),
    ],
)
def test_needs_terraform(source, planfile, expected):
    assert helpers.needs_terraform(source, planfile) is expected


def test_preflight_passes_without_terraform_for_a_planfile(no_terraform):
    preflight_check(None, needs_terraform=helpers.needs_terraform("./infra", "p.json"))


def test_preflight_still_requires_terraform_for_a_source_folder(no_terraform):
    with pytest.raises(SystemExit) as err:
        preflight_check(None, needs_terraform=helpers.needs_terraform("./infra"))
    assert err.value.code == 1
