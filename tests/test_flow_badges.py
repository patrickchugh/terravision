"""Tests for numbered-flow badges and the flow legend node.

Covers: HTML badge xlabel generation, continuous step numbering
across multiple flows in one diagram, multi-badge combination when a
node appears in more than one flow, edge-form badge rendering for
"source -> target" steps, and the HTML-table legend node placement.
"""

import pytest

from modules.annotations import compute_flow_step_numbers
from modules.drawing import generate_badge_xlabel, generate_legend_html


# ---------------------------------------------------------------------------
# T027 — badge HTML generator
# ---------------------------------------------------------------------------


def _fill(image):
    """The circle's colour: the most common opaque pixel.

    Sampling a single pixel is not enough: where the number lands depends
    on the fonts Graphviz finds, which differ between machines.
    """
    from collections import Counter

    opaque = [p[:3] for p in image.getdata() if p[3] == 255]
    return Counter(opaque).most_common(1)[0][0]


def _badge_png(xlabel):
    """The circle image a badge xlabel points at, and the cell's size."""
    import re

    from PIL import Image

    src = re.search(r'<IMG SRC="([^"]+)"', xlabel).group(1)
    width = int(re.search(r'WIDTH="(\d+)"', xlabel).group(1))
    return Image.open(src).convert("RGBA"), width


class TestBadgeXlabelGeneration:
    """T027: badges are circles with the step numbers, drawn as images.

    Graphviz can only round a table cell into a rounded square, so each
    badge is a circle image rendered by Graphviz and cached.
    """

    def test_single_step_badge_is_a_circle(self):
        image, width = _badge_png(generate_badge_xlabel([1]))
        w, h = image.size
        assert abs(w - h) <= 2
        assert _fill(image) == (0xE7, 0x4C, 0x3C)
        # Transparent near the corner, where a rounded square is still filled.
        assert image.getpixel((int(w * 0.12), int(h * 0.12)))[3] == 0
        assert width == 44

    def test_multi_step_badge_is_one_circle_per_step(self):
        xlabel = generate_badge_xlabel([1, 5, 12])
        assert xlabel.count("<IMG SRC=") == 3
        assert xlabel.count('WIDTH="44"') == 3

    def test_custom_color(self):
        image, _ = _badge_png(generate_badge_xlabel([3], color="#3498DB"))
        assert _fill(image) == (0x34, 0x98, 0xDB)

    def test_each_text_gets_its_own_image(self):
        first = generate_badge_xlabel([2, 4, 7])
        assert first == generate_badge_xlabel([2, 4, 7])  # cached
        assert first != generate_badge_xlabel([2, 4, 8])

    def test_unsafe_color_falls_back_to_the_default(self):
        image, _ = _badge_png(generate_badge_xlabel([1], color='red" shape=box'))
        assert _fill(image) == (0xE7, 0x4C, 0x3C)


# ---------------------------------------------------------------------------
# T028 — continuous numbering across multiple flows
# ---------------------------------------------------------------------------


class TestContinuousNumbering:
    """T028: compute_flow_step_numbers assigns continuous numbers across flows."""

    def test_two_flows_continuous(self):
        flows = {
            "auth-flow": {
                "description": "Authentication flow",
                "steps": [
                    {"resource": "aws_api_gateway_rest_api.api", "detail": "Step A1"},
                    {"resource": "aws_lambda_function.auth", "detail": "Step A2"},
                    {"resource": "aws_dynamodb_table.users", "detail": "Step A3"},
                    {"resource": "aws_lambda_function.auth", "detail": "Step A4"},
                ],
            },
            "data-flow": {
                "description": "Data ingestion",
                "steps": [
                    {"resource": "aws_sqs_queue.ingest", "detail": "Step B1"},
                    {"resource": "aws_lambda_function.process", "detail": "Step B2"},
                    {"resource": "aws_s3_bucket.output", "detail": "Step B3"},
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)

        # Flow A has 4 steps (1-4), flow B has 3 steps (5-7)
        assert node_badges["aws_api_gateway_rest_api.api"] == [1]
        assert sorted(node_badges["aws_lambda_function.auth"]) == [2, 4]
        assert node_badges["aws_dynamodb_table.users"] == [3]
        assert node_badges["aws_sqs_queue.ingest"] == [5]
        assert node_badges["aws_lambda_function.process"] == [6]
        assert node_badges["aws_s3_bucket.output"] == [7]

        # Legend should have 7 entries total
        assert len(legend_entries) == 7
        assert legend_entries[0]["step_number"] == 1
        assert legend_entries[0]["flow_name"] == "auth-flow"
        assert legend_entries[6]["step_number"] == 7
        assert legend_entries[6]["flow_name"] == "data-flow"


# ---------------------------------------------------------------------------
# T029 — multi-badge on shared node
# ---------------------------------------------------------------------------


class TestMultiBadge:
    """T029: a node in two flows gets one xlabel with both step numbers."""

    def test_shared_node_gets_combined_badge(self):
        flows = {
            "flow-a": {
                "description": "Flow A",
                "steps": [
                    {"resource": "aws_lambda_function.shared", "detail": "Start"},
                ],
            },
            "flow-b": {
                "description": "Flow B",
                "steps": [
                    {"resource": "aws_sqs_queue.q", "detail": "Queue"},
                    {"resource": "aws_lambda_function.shared", "detail": "End"},
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)

        # "shared" appears as step 1 in flow-a and step 3 in flow-b
        assert sorted(node_badges["aws_lambda_function.shared"]) == [1, 3]

        # The xlabel for the shared node should contain "1, 3"
        xlabel = generate_badge_xlabel(
            sorted(node_badges["aws_lambda_function.shared"])
        )
        assert xlabel == generate_badge_xlabel([1, 3])


# ---------------------------------------------------------------------------
# T030 — edge-badge syntax
# ---------------------------------------------------------------------------


class TestEdgeBadge:
    """T030: 'resource: src -> tgt' puts xlabel on the edge, not a node."""

    def test_edge_step_creates_edge_badge(self):
        flows = {
            "api-flow": {
                "description": "API request flow",
                "steps": [
                    {
                        "resource": "aws_lambda_function.api -> aws_dynamodb_table.orders",
                        "detail": "Write order",
                    },
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)

        # Should NOT appear in node_badges
        assert "aws_lambda_function.api" not in node_badges
        assert "aws_dynamodb_table.orders" not in node_badges

        # Should appear in edge_badges keyed by tuple
        edge_key = ("aws_lambda_function.api", "aws_dynamodb_table.orders")
        assert edge_key in edge_badges
        assert edge_badges[edge_key] == [1]

    def test_edge_and_node_mixed(self):
        flows = {
            "mixed": {
                "description": "Mixed flow",
                "steps": [
                    {"resource": "aws_api_gateway_rest_api.api", "detail": "Request"},
                    {
                        "resource": "aws_api_gateway_rest_api.api -> aws_lambda_function.fn",
                        "detail": "Invoke",
                    },
                    {"resource": "aws_lambda_function.fn", "detail": "Process"},
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)

        assert node_badges["aws_api_gateway_rest_api.api"] == [1]
        assert (
            "aws_api_gateway_rest_api.api",
            "aws_lambda_function.fn",
        ) in edge_badges
        assert edge_badges[
            ("aws_api_gateway_rest_api.api", "aws_lambda_function.fn")
        ] == [2]
        assert node_badges["aws_lambda_function.fn"] == [3]


# ---------------------------------------------------------------------------
# T031 — integration: full fixture produces correct xlabels + legend
# ---------------------------------------------------------------------------


class TestFlowBadgeIntegration:
    """T031: full flows fixture produces correct xlabels and legend structure."""

    def test_full_fixture(self):
        flows = {
            "user-request": {
                "description": "User request flow",
                "color": "#E74C3C",
                "steps": [
                    {
                        "resource": "aws_api_gateway_rest_api.api",
                        "xlabel": "Request",
                        "detail": "User sends HTTPS request",
                    },
                    {
                        "resource": "aws_api_gateway_rest_api.api -> aws_lambda_function.handler",
                        "xlabel": "Invoke",
                        "detail": "API GW invokes Lambda",
                    },
                    {
                        "resource": "aws_lambda_function.handler",
                        "xlabel": "Process",
                        "detail": "Lambda processes the request",
                    },
                    {
                        "resource": "aws_dynamodb_table.data",
                        "xlabel": "Store",
                        "detail": "Write to DynamoDB",
                    },
                ],
            },
            "async-processing": {
                "description": "Async processing pipeline",
                "color": "#3498DB",
                "steps": [
                    {
                        "resource": "aws_sqs_queue.tasks",
                        "xlabel": "Enqueue",
                        "detail": "Message enqueued",
                    },
                    {
                        "resource": "aws_lambda_function.handler",
                        "xlabel": "Poll",
                        "detail": "Lambda polls SQS",
                    },
                    {
                        "resource": "aws_s3_bucket.results",
                        "xlabel": "Upload",
                        "detail": "Results stored in S3",
                    },
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)

        # Verify continuous numbering: flow 1 has 4 steps (1-4), flow 2 has 3 (5-7)
        assert node_badges["aws_api_gateway_rest_api.api"] == [1]
        edge_key = (
            "aws_api_gateway_rest_api.api",
            "aws_lambda_function.handler",
        )
        assert edge_key in edge_badges
        assert edge_badges[edge_key] == [2]
        # Lambda handler appears in step 3 AND step 6
        assert sorted(node_badges["aws_lambda_function.handler"]) == [3, 6]
        assert node_badges["aws_dynamodb_table.data"] == [4]
        assert node_badges["aws_sqs_queue.tasks"] == [5]
        assert node_badges["aws_s3_bucket.results"] == [7]

        # Legend entries
        assert len(legend_entries) == 7
        # Check first and last
        assert legend_entries[0]["step_number"] == 1
        assert legend_entries[0]["flow_name"] == "user-request"
        assert legend_entries[0]["xlabel"] == "Request"
        assert legend_entries[0]["detail"] == "User sends HTTPS request"
        assert legend_entries[0]["color"] == "#E74C3C"

        assert legend_entries[6]["step_number"] == 7
        assert legend_entries[6]["flow_name"] == "async-processing"
        assert legend_entries[6]["xlabel"] == "Upload"
        assert legend_entries[6]["detail"] == "Results stored in S3"
        assert legend_entries[6]["color"] == "#3498DB"

    def test_legend_html_output(self):
        legend_entries = [
            {
                "step_number": 1,
                "flow_name": "user-request",
                "description": "User request flow",
                "xlabel": "Request",
                "detail": "User sends HTTPS request",
                "color": "#E74C3C",
            },
            {
                "step_number": 2,
                "flow_name": "user-request",
                "description": "User request flow",
                "xlabel": "Process",
                "detail": "Lambda processes the request",
                "color": "#E74C3C",
            },
        ]

        html = generate_legend_html(legend_entries)

        # Should be wrapped in angle brackets for graphviz HTML label
        assert html.startswith("<")
        assert html.endswith(">")
        # Should contain flow name as header
        assert "<B>Flow: user-request</B>" in html
        # Should contain a circle badge per step
        assert html.count("<IMG SRC=") == 2
        # Should contain detail text
        assert "User sends HTTPS request" in html
        assert "Lambda processes the request" in html

    def test_default_color_when_not_specified(self):
        flows = {
            "simple": {
                "description": "Simple flow",
                "steps": [
                    {"resource": "aws_s3_bucket.data", "detail": "Store data"},
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)
        # Default color should be #E74C3C
        assert legend_entries[0]["color"] == "#E74C3C"

    def test_empty_flows_returns_empty(self):
        node_badges, edge_badges, legend_entries = compute_flow_step_numbers({})
        assert node_badges == {}
        assert edge_badges == {}
        assert legend_entries == []

    def test_flow_with_no_steps_skipped(self):
        flows = {
            "empty-flow": {
                "description": "No steps",
                "steps": [],
            },
            "real-flow": {
                "description": "Has steps",
                "steps": [
                    {"resource": "aws_s3_bucket.data", "detail": "Store"},
                ],
            },
        }

        node_badges, edge_badges, legend_entries = compute_flow_step_numbers(flows)
        # Empty flow is skipped; real flow starts at 1
        assert node_badges["aws_s3_bucket.data"] == [1]
        assert len(legend_entries) == 1
        assert legend_entries[0]["step_number"] == 1


def test_legend_escapes_flow_text():
    """Free text with < > & must not break the Graphviz HTML label."""
    html = generate_legend_html(
        [
            {
                "step_number": 1,
                "flow_name": "R&D <flow>",
                "xlabel": "a<b",
                "detail": "Client -> ALB & back",
                "color": "#E74C3C",
            }
        ]
    )
    assert "Flow: R&amp;D &lt;flow&gt;" in html
    assert "a&lt;b" in html
    assert "Client -&gt; ALB &amp; back" in html
