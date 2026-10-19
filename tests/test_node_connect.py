"""Node.connect() rejects anything that is not a Node and an Edge."""

import pytest

from resource_classes import Edge, Node


def _node():
    # A Node without a diagram context: connect() checks its arguments first
    return Node.__new__(Node)


def test_connect_rejects_a_target_that_is_not_a_node():
    with pytest.raises(ValueError, match="is not a valid Node"):
        _node().connect("not a node", Edge.__new__(Edge))


def test_connect_rejects_an_edge_that_is_not_an_edge():
    with pytest.raises(ValueError, match="is not a valid Edge"):
        _node().connect(_node(), "not an edge")
