#!/usr/bin/env python3
"""Map every TerraVision icon to its draw.io stencil, where draw.io has one.

The draw.io export draws a resource with draw.io's own shape when there is
one, so the diagram stays editable with draw.io's libraries, and otherwise
embeds TerraVision's icon as an image. This script builds the icon -> shape
tables by matching icon files, not resource type names: TerraVision's Azure
and GCP icons come from the same official sets draw.io ships, and a type is
covered as soon as it uses an icon that is.

Matching, per icon file, in order:
  1. the file name equals a draw.io name, ignoring case and punctuation;
  2. the same after a plural, singular or "azure"/"amazon" prefix variant;
  3. a hand-checked alias below, for renamed products and other names.
Every result is checked against draw.io's library before it is written.

Usage (needs network access to GitHub):

    poetry run python scripts/generate_drawio_icon_shapes.py

Writes:
  modules/config/drawio_library.py      draw.io's Azure images and GCP stencils
  modules/config/drawio_icon_shapes.py  icon file -> draw.io shape, per cloud
"""

import importlib
import json
import pkgutil
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DRAWIO = "jgraph/drawio"
BRANCH = "dev"
RAW = f"https://raw.githubusercontent.com/{DRAWIO}/{BRANCH}/src/main/webapp"
TREE_API = f"https://api.github.com/repos/{DRAWIO}/git/trees/{BRANCH}?recursive=1"

# Icon files (<folder>/<file>) whose draw.io equivalent has another name.
# Each was checked by eye against draw.io's library.
AWS_ALIASES = {
    "amazon-managed-grafana": "managed_service_for_grafana",
    "amazon-managed-prometheus": "managed_service_for_prometheus",
    "amazon-managed-workflows-apache-airflow": "managed_workflows_for_apache_airflow",
    "amazon-opensearch-service": "opensearch_service_index",
    "amazon-devops-guru": "devops_guru",
    "budgets": "budgets_2",
    "certificate-authority": "private_certificate_authority",
    "cloudsearch": "cloudsearch2",
    "cloudwatch": "cloudwatch_2",
    "documentdb-mongodb-compatibility": "documentdb_with_mongodb_compatibility",
    "ec2-ami": "ami",
    "ec2-container-registry": "ecr",
    "ec2-instance": "instance2",
    "ec2-spot-instance": "spot_instance",
    "elastic-file-system-efs": "elastic_file_system",
    "elastic-file-system-efs-file-system": "file_system",
    "gamelift": "gamelift_2",
    "identity-and-access-management-iam-access-analyzer": "access_analyzer",
    "iot-policy": "policy",
    "iot-topic": "topic",
    "keyspaces-managed-apache-cassandra-service": "keyspaces",
    "nacl": "network_access_control_list",
    "quantum-ledger-database-qldb": "quantum_ledger_database",
    "rekognition": "rekognition_2",
    "simple-email-service-ses": "simple_email_service",
    "simple-storage-service-s3": "s3",
    "systems-manager-app-config": "app_config",
    "vpc-elastic-network-interface": "elastic_network_interface",
    "ec2-elastic-ip-address": "elastic_ip_address",
    "ec2-instances": "instances",
    "elastic-container-service": "ecs",
    "elastic-kubernetes-service": "eks",
    "dynamodb-table": "table",
    "simple-notification-service-sns": "sns",
    "simple-queue-service-sqs": "sqs",
    "iot-greengrass": "greengrass",
    "cloudwatch-alarm": "alarm",
    "systems-manager-parameter-store": "parameter_store",
    "elb-application-load-balancer": "application_load_balancer",
    "elb-classic-load-balancer": "classic_load_balancer",
    "elb-network-load-balancer": "network_load_balancer",
    "vpc-customer-gateway": "customer_gateway",
    "vpc-flow-logs": "flow_logs",
    "vpc-peering": "peering",
    "robomaker-simulator": "simulator",
    "identity-and-access-management-iam-aws-sts": "sts",
    "identity-and-access-management-iam-permissions": "permissions",
    "identity-and-access-management-iam-role": "role",
    "identity-and-access-management-iam": "identity_and_access_management",
    "elastic-block-store-ebs": "elastic_block_store",
    "s3-access-points": "general_access_points",
    "s3-glacier": "glacier",
    "simple-storage-service-s3-object": "object",
}
AZURE_ALIASES = {
    "appservices/cognitive-search.png": "app_services/Search_Services.svg",
    "aimachinelearning/cognitive-search.png": "app_services/Search_Services.svg",
    "compute/azure-spring-apps.png": "compute/Azure_Spring_Cloud.svg",
    "compute/cloud-services.png": "compute/Cloud_Services_Classic.svg",
    "compute/container-apps.png": "other/Worker_Container_App.svg",
    "compute/disk-snapshots.png": "compute/Disks_Snapshots.svg",
    "database/cache-for-redis.png": "databases/Cache_Redis.svg",
    "database/database-for-mariadb-servers.png": "databases/Azure_Database_MariaDB_Server.svg",
    "database/database-for-mysql-servers.png": "databases/Azure_Database_MySQL_Server.svg",
    "database/database-for-postgresql-servers.png": "databases/Azure_Database_PostgreSQL_Server.svg",
    "database/elastic-database-pools.png": "databases/SQL_Elastic_Pools.svg",
    "analytics/data-factories.png": "databases/Data_Factory.svg",
    "databases/data-factories.png": "databases/Data_Factory.svg",
    "integration/data-factories.png": "databases/Data_Factory.svg",
    "general/usericon.png": "identity/Users.svg",
    "migration/migration-projects.png": "migrate/Azure_Migrate.svg",
    "network/dns-private-zones.png": "networking/DNS_Zones.svg",
    "network/network-security-groups-classic.png": "networking/Network_Security_Groups.svg",
    "other/azure-managed-grafana.png": "other/Grafana.svg",
    "other/azure-vmware-solution.png": "azure_vmware_solution/AVS.svg",
    "other/capacity-reservation-groups.png": "other/Reserved_Capacity_Groups.svg",
    "other/container-apps-environments.png": "other/Container_App_Environments.svg",
    "other/microsoft-dev-box.png": "other/MS_Dev_Box.svg",
    "other/network-managers.png": "other/Azure_Network_Manager.svg",
    "storage/data-lake-storage.png": "storage/Data_Lake_Storage_Gen1.svg",
    "storage/queues-storage.png": "general/Storage_Queue.svg",
    "storage/table-storage.png": "general/Table.svg",
    "web/front-door-and-cdn-profiles.png": "networking/Front_Doors.svg",
    "web/media-services.png": "web/Azure_Media_Service.svg",
}
# TerraVision's GCP category icons have shorter names than draw.io's gcp3.
GCP_ALIASES = {
    "ai-ml": "aimachinelearning",
    "analytics": "dataanalytics",
    "integration": "integrationservices",
    "management": "managementtools",
    "maps": "mapsgeospatial",
    "media": "mediaservices",
    "security": "securityidentity",
    "serverless": "serverlesscomputing",
}


def fetch(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def icons_in_use(provider: str, prefixes: Tuple[str, ...]) -> Dict[str, list]:
    """Icon file (<folder>/<file>) -> the resource types drawn with it."""
    from resource_classes import Cluster

    icons: Dict[str, list] = {}
    pkg = importlib.import_module(f"resource_classes.{provider}")
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"resource_classes.{provider}.{mod_info.name}")
        for name, cls in vars(mod).items():
            if not (name.startswith(prefixes) and isinstance(cls, type)):
                continue
            if issubclass(cls, Cluster) or not getattr(cls, "_icon", None):
                continue
            key = f"{Path(cls._icon_dir).name}/{cls._icon}"
            icons.setdefault(key, []).append(name)
    return icons


def variants(key: str):
    yield key
    yield key + "s"
    yield key.rstrip("s")
    for prefix in ("azure", "amazon", "aws"):
        yield prefix + key
        if key.startswith(prefix):
            yield key[len(prefix) :]


def match(icons, library: Dict[str, str], aliases: Dict[str, str], alias_by):
    """Return ({icon: shape}, [icons without a draw.io shape])."""
    found, missing = {}, []
    for icon in sorted(icons):
        stem = Path(icon).stem
        alias = aliases.get(icon if alias_by == "path" else stem)
        if alias:
            if alias not in library.values():
                raise SystemExit(f"alias for {icon} names {alias}, not in draw.io")
            found[icon] = alias
            continue
        hit = next((library[v] for v in variants(norm(stem)) if v in library), None)
        if hit:
            found[icon] = hit
        else:
            missing.append(icon)
    return found, missing


def main() -> None:
    from modules.config.drawio_aws4_shapes import (
        AWS4_DIRECT_SHAPE_NAMES,
        AWS4_RESICON_NAMES,
    )

    print("Fetching draw.io's library ...")
    tree = json.loads(fetch(TREE_API))["tree"]
    azure_svgs = sorted(
        e["path"].split("/webapp/", 1)[1]
        for e in tree
        if "/img/lib/azure2/" in e["path"] and e["path"].endswith(".svg")
    )
    gcp3_js = fetch(f"{RAW}/js/diagramly/sidebar/Sidebar-GCP3.js")
    gcp3 = dict(re.findall(r"'([a-z0-9_]+);fillColor=(#[0-9a-fA-F]{6})'", gcp3_js))

    # The size each shape gets when dragged from draw.io's palette, so
    # exported icons match icons a user adds afterwards
    aws_js = fetch(f"{RAW}/js/diagramly/sidebar/Sidebar-AWS4.js")
    aws_sizes = {
        name: (float(w), float(h))
        for name, w, h in re.findall(
            r"createVertexTemplateEntry\(n \+ '([a-z0-9_]+);',\s*s \* ([\d.]+),"
            r"\s*s \* ([\d.]+)",
            aws_js,
        )
    }
    azure_js = fetch(f"{RAW}/js/diagramly/sidebar/Sidebar-Azure2.js")
    azure_sizes = {
        name: (round(400 * float(w)), round(400 * float(h)))
        for name, w, h in re.findall(
            r"createVertexTemplateEntry\(s \+ '([^']+\.svg);',\s*r \* ([\d.]+),"
            r"\s*r \* ([\d.]+)",
            azure_js,
        )
    }
    gcp3_sizes = {
        name: (round(0.5 * float(w), 1), round(0.5 * float(h), 1))
        for name, w, h in re.findall(
            r"n \+ '([a-z0-9_]+);fillColor=#[0-9a-fA-F]{6}',\s*s \* ([\d.]+),"
            r"\s*s \* ([\d.]+)",
            gcp3_js,
        )
    }
    print(f"  {len(azure_svgs)} Azure images, {len(gcp3)} GCP (gcp3) stencils")

    aws_library = {
        norm(n): f"mxgraph.aws4.{n}"
        for n in sorted(set(AWS4_DIRECT_SHAPE_NAMES) | set(AWS4_RESICON_NAMES))
    }
    azure_library = {}
    for path in azure_svgs:
        azure_library.setdefault(norm(Path(path).stem), path)
    gcp_library = {norm(n): n for n in gcp3}

    aws_aliases = {k: f"mxgraph.aws4.{v}" for k, v in AWS_ALIASES.items()}
    azure_aliases = {k: f"img/lib/azure2/{v}" for k, v in AZURE_ALIASES.items()}

    results = {}
    for provider, prefixes, library, aliases, alias_by in (
        ("aws", ("aws_", "tv_aws_"), aws_library, aws_aliases, "stem"),
        (
            "azure",
            ("azurerm_", "tv_azurerm_", "tv_azure_"),
            azure_library,
            azure_aliases,
            "path",
        ),
        ("gcp", ("google_", "tv_gcp_"), gcp_library, GCP_ALIASES, "stem"),
    ):
        icons = icons_in_use(provider, prefixes)
        found, missing = match(icons, library, aliases, alias_by)
        results[provider] = found
        types = sum(len(v) for v in icons.values())
        covered = sum(len(icons[i]) for i in found)
        print(
            f"  {provider}: {len(found)}/{len(icons)} icons have a draw.io shape "
            f"({covered}/{types} resource types); embedded as images: {missing}"
        )

    config = REPO_ROOT / "modules" / "config"
    (config / "drawio_library.py").write_text(
        '"""draw.io\'s Azure images and GCP stencils, for checking the maps.\n\n'
        "Generated by scripts/generate_drawio_icon_shapes.py from jgraph/drawio.\n"
        '"""\n\n'
        "AZURE2_SVGS = frozenset(\n    [\n"
        + "".join(f'        "{p}",\n' for p in azure_svgs)
        + "    ]\n)\n\n"
        "# gcp3 stencil name -> the fill draw.io's sidebar gives it\n"
        "GCP3_SHAPES = {\n"
        + "".join(f'    "{n}": "{f}",\n' for n, f in sorted(gcp3.items()))
        + "}\n\n"
        "# The size (width, height) a shape gets when dragged from draw.io's\n"
        "# palette. AWS service icons (resourceIcon) are all 78x78.\n"
        "AWS4_PALETTE_SIZES = {\n"
        + "".join(f'    "{n}": {v},\n' for n, v in sorted(aws_sizes.items()))
        + "}\n\n"
        "# Keyed by file name; the palette lists each image once per folder\n"
        "AZURE2_PALETTE_SIZES = {\n"
        + "".join(f'    "{n}": {v},\n' for n, v in sorted(azure_sizes.items()))
        + "}\n\n"
        "GCP3_PALETTE_SIZES = {\n"
        + "".join(f'    "{n}": {v},\n' for n, v in sorted(gcp3_sizes.items()))
        + "}\n"
    )
    lines = [
        '"""TerraVision icon file -> draw.io shape, per cloud.',
        "",
        "Generated by scripts/generate_drawio_icon_shapes.py. Keys are",
        "<icon folder>/<icon file>. The draw.io export uses a resource type's",
        "own entry in drawio_shape_map_<cloud>.py first, then its icon's entry",
        "here, and otherwise embeds the icon as an image.",
        '"""',
        "",
    ]
    for provider, var in (
        ("aws", "DRAWIO_ICON_SHAPES_AWS"),
        ("azure", "DRAWIO_ICON_SHAPES_AZURE"),
        ("gcp", "DRAWIO_ICON_SHAPES_GCP"),
    ):
        lines.append(f"{var} = {{")
        lines += [f'    "{k}": "{v}",' for k, v in sorted(results[provider].items())]
        lines += ["}", ""]
    (config / "drawio_icon_shapes.py").write_text("\n".join(lines))
    print("Wrote modules/config/drawio_library.py and drawio_icon_shapes.py")


if __name__ == "__main__":
    main()
