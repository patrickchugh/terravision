"""Run limits: a run that has gone wrong stops with an error, not a stall.

Issue #294: a count read wrongly multiplied a 164-node graph towards 18,000
nodes and the draw never finished. TV_MAX_NODES stops that before the copies
are made, and TV_TIMEOUT_MINUTES stops any graph-building step that runs on.
"""

import time

import pytest

from modules import graphmaker, helpers


def _tfdata(counts):
    graphdict = {name: [] for name in counts}
    meta_data = {name: {"count": count} for name, count in counts.items()}
    return {"graphdict": graphdict, "meta_data": meta_data}


def test_node_budget_allows_normal_graphs(monkeypatch):
    monkeypatch.delenv("TV_MAX_NODES", raising=False)
    helpers.check_node_budget({"aws_instance.web": 3}, _tfdata({}), "copying")


def test_node_budget_stops_runaway_copies(monkeypatch):
    monkeypatch.setenv("TV_MAX_NODES", "100")
    tfdata = _tfdata({f"aws_s3_bucket.b{i}": 150 for i in range(3)})
    with pytest.raises(helpers.TerravisionError) as err:
        graphmaker.handle_count_resources(list(tfdata["graphdict"]), tfdata)
    message = str(err.value)
    assert "453 nodes" in message and "TV_MAX_NODES" in message
    assert "aws_s3_bucket.b0: 150" in message and "tfdata.json" in message
    assert err.value.tfdata is tfdata
    assert not any("~" in node for node in tfdata["graphdict"])


def test_node_budget_zero_means_no_limit(monkeypatch):
    monkeypatch.setenv("TV_MAX_NODES", "0")
    helpers.check_node_budget({"aws_instance.web": 10**6}, _tfdata({}), "copying")


def test_time_limit_stops_a_step_that_runs_on(monkeypatch):
    monkeypatch.setenv("TV_TIMEOUT_MINUTES", "0.002")  # 0.12 seconds
    progress = {"step": "create_multiple_resources", "tfdata": {"graphdict": {}}}
    with pytest.raises(helpers.TerravisionError) as err:
        with helpers.time_limit(progress):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                pass
    assert "create_multiple_resources" in str(err.value)
    assert "TV_TIMEOUT_MINUTES" in str(err.value)
    assert err.value.tfdata == {"graphdict": {}}


def test_time_limit_leaves_quick_steps_and_ctrl_c_alone(monkeypatch):
    monkeypatch.setenv("TV_TIMEOUT_MINUTES", "1")
    with helpers.time_limit({"step": "quick"}):
        pass
    with pytest.raises(KeyboardInterrupt):
        with helpers.time_limit({"step": "quick"}):
            raise KeyboardInterrupt


def test_time_limit_zero_means_no_limit(monkeypatch):
    monkeypatch.setenv("TV_TIMEOUT_MINUTES", "0")
    limit = helpers.time_limit({})
    with limit:
        pass
    assert limit.timer is None
