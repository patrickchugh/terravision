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
    "aurora-mariadb-instance": "rds_mariadb_instance",
    "aurora-mysql-instance": "rds_mysql_instance",
    "aurora-oracle-instance": "rds_oracle_instance",
    "aurora-postgresql-instance": "rds_postgresql_instance",
    "aurora-sql-server-instance": "rds_sql_server_instance",
    "budgets": "budgets_2",
    "cloudsearch": "cloudsearch2",
    "cloudwatch": "cloudwatch_2",
    "cloudwatch-alarm": "alarm",
    "codeconnections": "codestar",
    "data-firehose": "kinesis_data_firehose",
    "direct-connect-gateway": "gateway",
    "documentdb": "documentdb_with_mongodb_compatibility",
    "dynamodb-dynamodb-accelerator": "dynamodb_dax",
    "dynamodb-table": "table",
    "ec2-ami": "ami",
    "ec2-elastic-ip-address": "elastic_ip_address",
    "ec2-instance": "instance2",
    "ec2-instances": "instances",
    "ec2-spot-instance": "spot_instance",
    "efs": "elastic_file_system",
    "elastic-container-registry": "ecr",
    "elastic-container-service": "ecs",
    "elastic-disaster-recovery": "cloudendure_disaster_recovery",
    "elastic-file-system-file-system": "file_system",
    "elastic-kubernetes-service": "eks",
    "elastic-load-balancing-application-load-balancer": "application_load_balancer",
    "elastic-load-balancing-classic-load-balancer": "classic_load_balancer",
    "elastic-load-balancing-network-load-balancer": "network_load_balancer",
    "fsx-for-wfs": "fsx_for_windows_file_server",
    "gamelift-servers": "gamelift_2",
    "iam-identity-center": "single_sign_on",
    "identity-access-management-iam-access-analyzer": "access_analyzer",
    "identity-access-management-permissions": "permissions",
    "identity-access-management-role": "role",
    "identity-access-management-sts": "sts",
    "iot-greengrass": "greengrass",
    "iot-policy": "policy",
    "iot-topic": "topic",
    "managed-grafana": "managed_service_for_grafana",
    "managed-streaming-for-apache-kafka": "managed_streaming_for_kafka",
    "memorydb": "elasticache_for_redis",
    "opensearch-service": "opensearch_service_index",
    "quantum-ledger-database-qldb": "quantum_ledger_database",
    "quick": "quicksight",
    "rekognition": "rekognition_2",
    "robomaker-simulator": "simulator",
    "sagemaker-ai": "sagemaker",
    "server": "traditional_server",
    "sagemaker-ai-model": "sagemaker_model",
    "sagemaker-ai-notebook": "sagemaker_notebook",
    "simple-notification-service": "sns",
    "simple-queue-service": "sqs",
    "simple-storage-service": "s3",
    "simple-storage-service-general-access-points": "general_access_points",
    "simple-storage-service-glacier": "glacier",
    "simple-storage-service-object": "object",
    "systems-manager-parameter-store": "parameter_store",
    "vpc-customer-gateway": "customer_gateway",
    "vpc-elastic-network-interface": "elastic_network_interface",
    "vpc-endpoints": "endpoint",
    "vpc-flow-logs": "flow_logs",
    "vpc-internet-gateway": "internet_gateway",
    "vpc-nat-gateway": "nat_gateway",
    "vpc-network-access-control-list": "network_access_control_list",
    "vpc-peering-connection": "peering",
    "route-53-route-table": "route_table",
    "vpc-vpn-gateway": "vpn_gateway",
}
AZURE_ALIASES = {
    "ai-machine-learning/ai-studio.png": "ai_machine_learning/AI_Studio.svg",
    "ai-machine-learning/bot-services.png": "ai_machine_learning/Bot_Services.svg",
    "ai-machine-learning/cognitive-search.png": "general/Search.svg",
    "ai-machine-learning/cognitive-services.png": "ai_machine_learning/Cognitive_Services.svg",
    "ai-machine-learning/machine-learning.png": "ai_machine_learning/Machine_Learning.svg",
    "analytics/data-factories.png": "databases/Data_Factory.svg",
    "compute/azure-spring-apps.png": "compute/Azure_Spring_Cloud.svg",
    "compute/cloud-services-classic.png": "compute/Cloud_Services_Classic.svg",
    "compute/disks-snapshots.png": "compute/Disks_Snapshots.svg",
    "compute/vm-scale-sets.png": "compute/VM_Scale_Sets.svg",
    "databases/data-factories.png": "databases/Data_Factory.svg",
    "general/storage-queue.png": "general/Storage_Queue.svg",
    "general/table.png": "general/Table.svg",
    "identity/entra-domain-services.png": "identity/Azure_AD_Domain_Services.svg",
    "terravision/active-directory.png": "identity/Azure_Active_Directory.svg",
    "identity/users.png": "identity/Users.svg",
    "integration/azure-data-catalog.png": "integration/Azure_Data_Catalog.svg",
    "integration/azure-service-bus.png": "general/Service_Bus.svg",
    "integration/data-factories.png": "databases/Data_Factory.svg",
    "management-governance/automation-accounts.png": "management_governance/Automation_Accounts.svg",
    "management-governance/monitor.png": "management_governance/Monitor.svg",
    "management-governance/policy.png": "management_governance/Policy.svg",
    "migrate/azure-migrate.png": "migrate/Azure_Migrate.svg",
    "migration/azure-database-migration-services.png": "databases/Azure_Database_Migration_Services.svg",
    "networking/application-gateways.png": "networking/Application_Gateways.svg",
    "networking/cdn-profiles.png": "app_services/CDN_Profiles.svg",
    "networking/connections.png": "networking/Connections.svg",
    "networking/ddos-protection-plans.png": "networking/DDoS_Protection_Plans.svg",
    "networking/dns-zones.png": "networking/DNS_Zones.svg",
    "networking/expressroute-circuits.png": "networking/ExpressRoute_Circuits.svg",
    "networking/firewalls.png": "networking/Firewalls.svg",
    "networking/front-door-and-cdn-profiles.png": "networking/Front_Doors.svg",
    "networking/load-balancers.png": "networking/Load_Balancers.svg",
    "networking/local-network-gateways.png": "networking/Local_Network_Gateways.svg",
    "networking/network-interfaces.png": "networking/Network_Interfaces.svg",
    "networking/network-security-groups.png": "networking/Network_Security_Groups.svg",
    "networking/network-watcher.png": "networking/Network_Watcher.svg",
    "networking/public-ip-addresses.png": "networking/Public_IP_Addresses.svg",
    "networking/traffic-manager-profiles.png": "networking/Traffic_Manager_Profiles.svg",
    "networking/virtual-network-gateways.png": "networking/Virtual_Network_Gateways.svg",
    "networking/virtual-router.png": "networking/Virtual_Router.svg",
    "networking/virtual-wans.png": "networking/Virtual_WANs.svg",
    "networking/web-application-firewall-policies-waf.png": "networking/Web_Application_Firewall_Policies_WAF.svg",
    "other/azure-managed-grafana.png": "other/Grafana.svg",
    "other/azure-vmware-solution.png": "azure_vmware_solution/AVS.svg",
    "other/capacity-reservation-groups.png": "other/Reserved_Capacity_Groups.svg",
    "other/container-apps-environments.png": "other/Container_App_Environments.svg",
    "other/microsoft-dev-box.png": "other/MS_Dev_Box.svg",
    "other/network-managers.png": "other/Azure_Network_Manager.svg",
    "other/private-endpoints.png": "networking/Private_Endpoint.svg",
    "other/worker-container-app.png": "other/Worker_Container_App.svg",
    "security/microsoft-defender-for-cloud.png": "security/Security_Center.svg",
    "storage/azure-netapp-files.png": "storage/Azure_NetApp_Files.svg",
    "terravision/azure-purview-accounts.png": "databases/Azure_Purview_Accounts.svg",
    "terravision/data-lake-storage.png": "storage/Data_Lake_Storage_Gen1.svg",
    "terravision/dns-private-zones.png": "networking/DNS_Zones.svg",
    "web/azure-media-service.png": "web/Azure_Media_Service.svg",
    "web/front-door-and-cdn-profiles.png": "networking/Front_Doors.svg",
}
# TerraVision's GCP category icons have shorter names than draw.io's gcp3.
GCP_ALIASES = {}


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
            # Neutral icons borrowed from resource_images/generic/ or onprem/
            # (an on-site server or database) stay embedded: a draw.io
            # stencil for them would claim a provider's service
            if not cls._icon_dir.startswith(f"resource_images/{provider}/"):
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
            # Since draw.io 32.0.1 the style after the file name also carries
            # connection points: 'X.svg;points=[[...]];'
            r"createVertexTemplateEntry\(s \+ '([^';]+\.svg);[^']*',\s*r \* ([\d.]+),"
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
