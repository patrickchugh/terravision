#!/usr/bin/env python3
"""Build the skill's example pattern library from TerraVision's own output.

    poetry run python scripts/gen_example_patterns.py

tests/json/expected-*.json hold the graphs TerraVision produces from real
Terraform in tests/fixtures, after all of its rules have decided what to show.
Each pattern below is one of those graphs with its addresses written the way a
person or an agent would write them: module paths and indexes are dropped, so
``module.vpc.aws_subnet.private[0]~1`` becomes ``aws_subnet.private~1``.
Nodes TerraVision never draws (its hide lists, such as route tables, IAM
instance profiles or S3 bucket settings) are removed too, so an agent copying a
pattern does not learn to write types that vanish. Container nodes (VPCs,
subnets, resource groups...) draw as boxes and are kept, and arrows between
drawn nodes are kept even when hidden, because hidden edges still shape the
layout. So the level of detail stays exactly TerraVision's.

Every pattern is rendered before and after and must draw the same nodes (icon,
label and the boxes around it) and the same visible arrows; otherwise the
script stops without writing anything. Rerun it when TerraVision's output
rules change. It writes skills/terravision-cloud-diagrams/examples/patterns/
<name>.tvg.json plus index.json, which diagram_guide serves.
"""

import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "json"
TARGET = ROOT / "skills" / "terravision-cloud-diagrams" / "examples" / "patterns"

# name: (source file in tests/json, one-line description for the catalogue)
PATTERNS = {
    "aws-api-gateway-lambda": (
        "expected-api-gateway-rest-lambda.json",
        "REST API Gateway invoking a Lambda function",
    ),
    "aws-cognito-api-gateway": (
        "expected-cognito-api-gateway.json",
        "API Gateway with a Cognito user pool authoriser and Lambda backends",
    ),
    "aws-dynamodb-streams-lambda": (
        "expected-dynamodb-streams-lambda.json",
        "DynamoDB table streaming changes to Lambda, with Kinesis",
    ),
    "aws-eks": (
        "expected-eks-basic.json",
        "EKS cluster with managed node groups across availability zones, ECR",
    ),
    "aws-ecs-fargate-elasticache": (
        "expected-elasticache-redis.json",
        "ECS on Fargate in private subnets using ElastiCache Redis, ECR",
    ),
    "aws-eventbridge-lambda": (
        "expected-eventbridge-lambda.json",
        "EventBridge rule triggering Lambda",
    ),
    "aws-firehose-lambda": (
        "expected-firehose-lambda.json",
        "Kinesis Data Firehose with Lambda transformation delivering to S3",
    ),
    "aws-glue-s3": (
        "expected-glue-s3.json",
        "Glue crawler and ETL job over an S3 data lake with a Glue catalog",
    ),
    "aws-s3-notification-lambda": (
        "expected-s3-notification-lambda.json",
        "S3 bucket notifications invoking Lambda",
    ),
    "aws-sagemaker-endpoint": (
        "expected-sagemaker-endpoint.json",
        "SageMaker model and endpoint called by Lambda, artefacts in S3",
    ),
    "aws-sagemaker-notebook-vpc": (
        "expected-sagemaker-notebook-vpc.json",
        "SageMaker notebook instance inside a VPC with S3 access",
    ),
    "aws-secretsmanager-rds": (
        "expected-secretsmanager-rds.json",
        "RDS PostgreSQL with credentials in Secrets Manager, rotated by Lambda",
    ),
    "aws-sns-sqs-lambda": (
        "expected-sns-sqs-lambda.json",
        "SNS topic fanning out to SQS queues processed by Lambda",
    ),
    "aws-static-website": (
        "expected-static-website.json",
        "Static website on S3 served through CloudFront",
    ),
    "aws-stepfunctions": (
        "expected-stepfunctions-multi-service.json",
        "Step Functions orchestrating Lambda, DynamoDB and SNS",
    ),
    "aws-waf-alb": (
        "expected-waf-alb.json",
        "Application Load Balancer protected by WAF",
    ),
    "aws-wordpress-ecs": (
        "expected-wordpress.json",
        "WordPress on ECS with EFS, RDS, CloudFront, ALB and autoscaling",
    ),
    "azure-aks": (
        "expected-azure-aks.json",
        "AKS cluster with node pools across zones, ACR and Log Analytics",
    ),
    "azure-appgw-lb": (
        "expected-azure-appgw-lb.json",
        "Application Gateway and load balancer in front of VMs across zones",
    ),
    "azure-vm-vmss": (
        "expected-azure-vm-vmss.json",
        "Virtual machine scale set across zones behind a load balancer",
    ),
    "gcp-gke": (
        "expected-gcp-us4-gke.json",
        "GKE cluster with a node pool and a container registry",
    ),
    "gcp-serverless": (
        "expected-gcp-us6-serverless.json",
        "Cloud Run and Cloud Functions with Pub/Sub and Cloud Storage",
    ),
    "gcp-pubsub-bigquery": (
        "expected-gcp-us7-pubsub.json",
        "Pub/Sub pipeline into BigQuery with Cloud Run and Cloud Storage",
    ),
    "gcp-data-services": (
        "expected-gcp-us9-data.json",
        "Cloud SQL, Spanner, Memorystore and BigQuery used by a VM",
    ),
    "gcp-http-load-balancer": (
        "expected-gcp-us10-lb-http.json",
        "External HTTP load balancer in front of a managed instance group",
    ),
    "gcp-internal-load-balancer": (
        "expected-gcp-us11-lb-internal.json",
        "Internal regional load balancer in front of a managed instance group",
    ),
}

_MODULE_PATH = re.compile(r"^(module\.([A-Za-z0-9_-]+)(\[[^\]]+\])?\.)+")
_INDEX = re.compile(r"\[([^\]]*)\]")


def simple_address(address: str) -> str:
    """Drop module paths and indexes, keeping the type, name and ~N copy."""
    copy = ""
    match = re.search(r"~\d+$", address)
    if match:
        copy, address = match.group(0), address[: match.start()]
    address = _INDEX.sub("", _MODULE_PATH.sub("", address))
    return address + copy


def normalise(graph: dict) -> tuple:
    """Rewrite every address; stop if two distinct addresses would collide.

    Returns the rewritten graph and the old-to-new address map.
    """
    addresses = list(dict.fromkeys([*graph, *(t for v in graph.values() for t in v)]))
    renamed = {a: simple_address(a) for a in addresses}
    clashes = Counter(renamed.values())
    duplicates = sorted(n for n, count in clashes.items() if count > 1)
    if duplicates:
        raise SystemExit(f"addresses would collide after simplifying: {duplicates}")
    rewritten = {
        renamed[node]: [renamed[t] for t in targets] for node, targets in graph.items()
    }
    return rewritten, renamed


def container_types() -> set:
    """Types drawn as boxes rather than nodes, from every provider's config."""
    sys.path.insert(0, str(ROOT))
    from modules.config import cloud_config_aws, cloud_config_azure, cloud_config_gcp

    return {
        *cloud_config_aws.AWS_GROUP_NODES,
        *cloud_config_azure.AZURE_GROUP_NODES,
        *cloud_config_gcp.GCP_GROUP_NODES,
    }


def prune(graph: dict, keep: set, containers: set) -> dict:
    """Drop nodes that are not drawn, keeping containers and drawn nodes."""

    def kept(address: str) -> bool:
        return address in keep or address.split(".")[0] in containers

    return {
        node: [t for t in targets if kept(t)]
        for node, targets in graph.items()
        if kept(node)
    }


def _node_key(obj: dict) -> tuple:
    """Icon and visible text of a node, whether its label is plain or HTML."""
    label = obj.get("label", "")
    image = obj.get("image") or (re.search(r'src="([^"]+)"', label) or [None, ""])[1]
    text = " ".join(re.sub(r"<[^>]+>", " ", label).split())
    return Path(image).name, text


def drawn(graph: dict) -> tuple:
    """What TerraVision actually draws for this graph, independent of node ids.

    Renders to DOT, then has Graphviz export that graph as JSON, which decodes
    every attribute and lists each cluster's members. Returns the drawn nodes
    (icon, text and the boxes around each), the visible edges between them,
    and the addresses of the drawn nodes.
    """
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "g.tvg.json"
        source.write_text(json.dumps(graph))
        subprocess.run(
            ["terravision", "draw", "--source", str(source), "--format", "dot",
             "--outfile", str(Path(tmp) / "g")],
            cwd=tmp, check=True, capture_output=True,
        )  # fmt: skip
        exported = subprocess.run(
            ["neato", "-n2", "-Tjson0", str(Path(tmp) / "g.dot.dot")],
            check=True, capture_output=True, text=True,
        )  # fmt: skip
    data = json.loads(exported.stdout)
    objects = data.get("objects", [])
    boxes = {}
    for obj in objects:
        name = obj.get("name", "")
        if name.startswith("cluster"):
            for member in obj.get("nodes", []):
                boxes.setdefault(member, []).append(re.sub(r"\.\d+$", "", name))
    keys, names = {}, set()
    for obj in objects:
        address = obj.get("tf_resource_name")
        if address is not None and "nodes" not in obj:
            gvid = obj["_gvid"]
            keys[gvid] = (*_node_key(obj), tuple(sorted(boxes.get(gvid, []))))
            names.add(address)
    edges = Counter(
        (keys.get(e["tail"]), keys.get(e["head"]))
        for e in data.get("edges", [])
        if e.get("style") != "invis"
    )
    return Counter(keys.values()), edges, names


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    index = []
    containers = container_types()
    for name, (source, description) in PATTERNS.items():
        original = json.loads((SOURCE / source).read_text())
        nodes, edges, names = drawn(original)
        simplified, renamed = normalise(original)
        simplified = prune(
            simplified, {renamed[a] for a in names if a in renamed}, containers
        )
        if drawn(simplified)[:2] != (nodes, edges):
            raise SystemExit(f"{name}: the simplified graph draws differently")
        dropped = len(renamed) - len(
            set(simplified) | {t for v in simplified.values() for t in v}
        )
        (TARGET / f"{name}.tvg.json").write_text(
            json.dumps(simplified, indent=2, sort_keys=True) + "\n"
        )
        provider = name.split("-", 1)[0]
        index.append({"name": name, "provider": provider, "description": description})
        print(
            f"{name}: {len(simplified)} keys, {dropped} undrawn nodes removed, "
            f"draws the same as {source}"
        )
    (TARGET / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {len(index)} patterns to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
