"""Variants read the one attribute that says which kind a resource is.

An aws_lb is an ALB, NLB or Gateway Load Balancer by its load_balancer_type;
a google_compute_disk is Hyperdisk by its type. Reading that attribute, rather
than searching all of the metadata for a keyword, keeps a subnet called
"network" from turning an ALB into an NLB.
"""

import pytest

from modules import helpers

AWS = {"provider_detection": {"primary_provider": "aws"}}
GCP = {"provider_detection": {"primary_provider": "gcp"}}


@pytest.mark.parametrize(
    "lb_type, variant",
    [("gateway", "aws_gwlb"), ("network", "aws_nlb"), ("application", "aws_alb")],
)
def test_load_balancer_kind_comes_from_its_type(lb_type, variant):
    views = {"plan": {"load_balancer_type": lb_type}, "hcl": {}}
    assert helpers.check_variant("aws_lb.web", views, AWS) == variant


def test_other_attributes_do_not_decide_the_kind():
    views = {
        "plan": {"load_balancer_type": "application", "subnets": ["network-a"]},
        "hcl": {},
    }
    assert helpers.check_variant("aws_lb.web", views, AWS) == "aws_alb"


def test_unset_or_unresolved_type_is_terraforms_default():
    """The HCL may only say ${var.load_balancer_type}; unset means application."""
    for views in (
        {"plan": {}, "hcl": {"load_balancer_type": "${var.load_balancer_type}"}},
        {"plan": {"load_balancer_type": True}, "hcl": {}},
    ):
        assert helpers.check_variant("aws_lb.web", views, AWS) == "aws_alb"


def test_quoted_hcl_values_are_read():
    views = {"plan": None, "hcl": {"load_balancer_type": '"gateway" '}}
    assert helpers.check_variant("aws_lb.inspection", views, AWS) == "aws_gwlb"


def test_only_the_exact_type_takes_its_variants():
    """aws_lb_listener starts with aws_lb but is not a load balancer."""
    views = {"plan": {"load_balancer_type": "gateway"}, "hcl": {}}
    assert helpers.check_variant("aws_lb_listener.web", views, AWS) is False


def test_hyperdisk_has_its_own_icon():
    views = {"plan": {"type": "hyperdisk-balanced"}, "hcl": {}}
    assert (
        helpers.check_variant("google_compute_disk.data", views, GCP)
        == "google_compute_disk_hyperdisk"
    )
    standard = {"plan": {"type": "pd-ssd"}, "hcl": {}}
    assert helpers.check_variant("google_compute_disk.data", standard, GCP) is False
