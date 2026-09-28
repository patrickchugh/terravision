"""EKS worker patterns: Karpenter, managed node groups, Fargate, self-managed.

AWS provider 6.x plans compute_config as "known after apply" (True) on every
cluster. That renamed a Karpenter cluster to the auto-mode variant, which left
the per-subnet copies orphaned and the control plane pointing at nothing.
Whole-diagram coverage is in the expected-eks-*.json snapshots.
"""

import copy

from modules.helpers import check_variant
from modules.resource_handlers_aws import handle_eks_cluster_grouping
from modules.resource_transformers import expand_to_numbered_instances

AWS = {"provider_detection": {"primary_provider": "aws", "providers": ["aws"]}}


def _cluster(compute_config):
    return {"plan": {"name": "c", "compute_config": compute_config}}


def test_known_after_apply_compute_config_is_not_auto_mode():
    assert check_variant("aws_eks_cluster.main", _cluster(True), AWS) is False


def test_empty_compute_config_is_not_auto_mode():
    assert check_variant("aws_eks_cluster.main", _cluster([]), AWS) is False


def test_enabled_compute_config_is_auto_mode():
    config = [{"enabled": True, "node_pools": ["general-purpose", "system"]}]
    assert (
        check_variant("aws_eks_cluster.main", _cluster(config), AWS)
        == "aws_eks_cluster_auto"
    )


def test_variant_values_still_match():
    metadata = {"plan": {"load_balancer_type": "application", "internal": True}}
    assert check_variant("aws_lb.web", metadata, AWS) == "aws_alb"


def _karpenter_tfdata():
    cluster = "aws_eks_cluster.main"
    queue = "aws_sqs_queue.karpenter_interruption"
    graphdict = {
        cluster: [],
        "aws_subnet.private_1": [cluster],
        "aws_subnet.private_2": [cluster],
        "aws_iam_role.karpenter_node": ["aws_iam_instance_profile.karpenter_node"],
        "aws_iam_instance_profile.karpenter_node": [],
        queue: [],
    }
    return {
        **AWS,
        "graphdict": graphdict,
        "meta_data": {k: {} for k in graphdict},
        # Terraform's edge runs from the event target to the queue it targets
        "original_graphdict": {
            **copy.deepcopy(graphdict),
            "aws_cloudwatch_event_target.spot_interruption": [queue],
        },
    }


def test_karpenter_cluster_links_control_plane_to_each_subnet():
    graph = handle_eks_cluster_grouping(_karpenter_tfdata())["graphdict"]
    assert graph["aws_account.eks_control_plane_main"] == ["aws_eks_cluster.main"]
    assert graph["aws_eks_cluster.main"] == [
        "aws_eks_cluster.main~1",
        "aws_eks_cluster.main~2",
    ]
    assert "aws_eks_cluster.main~1" in graph["aws_subnet.private_1"]
    assert "aws_eks_cluster.main~2" in graph["aws_subnet.private_2"]


def test_interruption_queue_feeds_each_karpenter_node():
    graph = handle_eks_cluster_grouping(_karpenter_tfdata())["graphdict"]
    assert graph["aws_sqs_queue.karpenter_interruption"] == [
        "tv_karpenter.karpenter~1",
        "tv_karpenter.karpenter~2",
    ]


def test_oidc_provider_has_an_icon():
    from resource_classes.aws import security

    assert security.aws_iam_openid_connect_provider is security.IAMAWSSts


def _node_group_tfdata(inherit_connections=True):
    group = "aws_eks_node_group.main"
    graphdict = {
        "aws_subnet.a": [group],
        "aws_subnet.b": [group],
        "aws_eks_cluster.main": [group],
        "aws_iam_role.node": [group],
        group: ["aws_eks_cluster.main"],
    }
    meta = {k: {} for k in graphdict}
    meta["aws_subnet.a"]["id"] = "subnet-a"
    meta["aws_subnet.b"]["id"] = "subnet-b"
    meta[group]["subnet_ids"] = ["subnet-a", "subnet-b"]
    tfdata = {**AWS, "graphdict": graphdict, "meta_data": meta}
    return expand_to_numbered_instances(
        tfdata, "aws_eks_node_group", inherit_connections=inherit_connections
    )["graphdict"]


def test_expansion_repoints_references_to_every_instance():
    graph = _node_group_tfdata()
    assert "aws_eks_node_group.main" not in graph
    for parent in ("aws_eks_cluster.main", "aws_iam_role.node"):
        assert graph[parent] == [
            "aws_eks_node_group.main~1",
            "aws_eks_node_group.main~2",
        ]
    assert graph["aws_subnet.a"] == ["aws_eks_node_group.main~1"]
    assert graph["aws_subnet.b"] == ["aws_eks_node_group.main~2"]


def test_visual_only_expansion_leaves_references_for_later_matching():
    graph = _node_group_tfdata(inherit_connections=False)
    assert graph["aws_iam_role.node"] == ["aws_eks_node_group.main"]


def _self_managed_tfdata(tag_only=False):
    cluster = "aws_eks_cluster.main"
    graphdict = {
        cluster: [] if tag_only else ["aws_launch_template.node~1"],
        "aws_subnet.private_1": [cluster, "aws_autoscaling_group.node~1"],
        "aws_subnet.private_2": [cluster, "aws_autoscaling_group.node~2"],
        "aws_autoscaling_group.node~1": [],
        "aws_autoscaling_group.node~2": [],
        "aws_launch_template.node~1": ["aws_autoscaling_group.node~1"],
    }
    meta = {k: {} for k in graphdict}
    meta[cluster]["name"] = "prod"
    if tag_only:
        for asg in ("aws_autoscaling_group.node~1", "aws_autoscaling_group.node~2"):
            meta[asg]["tag"] = [{"key": "kubernetes.io/cluster/prod"}]
    original = {
        cluster: [] if tag_only else ["aws_launch_template.node"],
        "aws_launch_template.node": ["aws_autoscaling_group.node"],
    }
    return {
        **AWS,
        "graphdict": graphdict,
        "meta_data": meta,
        "original_graphdict": original,
    }


def test_self_managed_nodes_are_not_mistaken_for_karpenter():
    for tag_only in (False, True):
        graph = handle_eks_cluster_grouping(_self_managed_tfdata(tag_only))["graphdict"]
        assert "aws_eks_cluster.main~1" not in graph
        assert not any(k.startswith("tv_karpenter") for k in graph)
        assert graph["aws_eks_cluster.main"] == [
            "aws_autoscaling_group.node~1",
            "aws_autoscaling_group.node~2",
        ]
        assert "aws_eks_cluster.main" not in graph["aws_subnet.private_1"]
