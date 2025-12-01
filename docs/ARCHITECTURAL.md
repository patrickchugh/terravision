# TerraVision Multi-Cloud Architecture

## Executive Summary
TerraVision ingests Terraform sources, builds a resource-dependency graph enriched with metadata, and renders architecture diagrams. The current architecture is strongly AWS-centric: resource handling, naming conventions, icon management, annotations, and graph post-processing are largely hard-coded to AWS. This document proposes a clean, extensible multi-provider architecture that introduces a provider abstraction, pluggable resource handlers, provider-aware configuration, and a service mapping layer. Phase 1 delivers Azure and GCP support without breaking existing users. Phase 2 introduces a generic provider framework for other Terraform providers (Kubernetes, Docker, GitHub, etc.).

**Key outcomes:**
- Provider Abstraction Layer decouples cloud-specific logic from core graph building and rendering.
- Provider-specific ResourceHandlers and CloudConfig sets for AWS, Azure, GCP.
- Unified Service Mapping and Translation to normalize Terraform resource types across clouds.
- Provider-aware icon management and class hierarchy in resource_classes/.
- Backwards compatible CLI and data model, with minimal breaking changes gated behind version bump and feature flags.

## Current Architecture Deep Dive

### System Context
- **Inputs**: Terraform files (.tf, .tfvars), optional pre-generated JSON tfgraph, optional annotations YAML, git module sources, Terraform plan and graph.
- **Outputs**: Graph data (JSON), Cloud services list, Rendered diagram (png/svg/pdf).
- **Tools**: terraform, dot (Graphviz), gvpr, git.

### Core Flow
terravision.py (CLI) orchestrates:
1. `preflight_check()` dependencies
2. `compile_tfdata()`:
   - `tfwrapper.tf_initplan(source, varfile, workspace, debug)` → terraform plan/graph JSON
   - `tfwrapper.tf_makegraph(tfdata, debug)` → initial graph dict and metadata from Graphviz/TF
   - `fileparser.read_tfsource(...)` → HCL2 parse modules, variables, locals, outputs
   - `interpreter`: variable resolution, locals extraction, metadata merging
   - `resource_handlers.handle_special_cases(tfdata)` → AWS specific tweaks
   - `graphmaker`: relationship detection, consolidation, variants, multiples, reverse-relations
   - `annotations.add_annotations(tfdata)` → auto annotations (AWS) + user annotations
   - `helpers.sort_graphdict`
3. `drawing.render_diagram(tfdata, ...)`

### Data Structures
**tfdata dict** (canonical container), keys:
- `graphdict`: {node: [deps]}
- `meta_data`: {node: {attributes}}
- `node_list`: [nodes]
- `hidden`: []
- `original_graphdict`, `original_metadata` (snapshots)
- Plus intermediate views: `variable_map`, `all_*` sections parsed from HCL

### Where AWS is integrated today
- **modules/cloud_config.py** contains AWS_* constants:
  - AWS_CONSOLIDATED_NODES, AWS_GROUP_NODES, AWS_EDGE_NODES, DRAW_ORDER, AUTO_ANNOTATIONS, NODE_VARIANTS, REVERSE_ARROW_LIST, FORCED_DEST/ORIGIN, IMPLIED_CONNECTIONS, SHARED_SERVICES, ALWAYS/NEVER DRAW LINE, ACRONYMS_LIST, NAME_REPLACEMENTS.
- **modules/resource_handlers.py**: AWS specific handlers, functions named `aws_handle_*` and general helpers that assume AWS names/types.
- **modules/graphmaker.py**: imports AWS_* constants directly and applies them to generic graph logic; special resource orchestration uses SPECIAL_RESOURCES mapping from cloud_config pointing to resource_handlers functions.
- **modules/interpreter.py**: DATA_REPLACEMENTS include AWS data sources; module var regexes explicitly pattern-match aws_*.
- **helpers.py**: `pretty_name()`, `extract_terraform_resource()`, `consolidated_node_check()`, `check_variant()` use AWS-specific tables.
- **tfwrapper.py**: error message references AWS, Azure, Google, but validation checks existence of AWS only; REVERSE_ARROW_LIST is AWS constant; VPC implied relations use aws_vpc/aws_subnet.
- **resource_classes/aws**: Node subclasses and icons directory (resource_images/aws); generic and onprem classes exist.

### Data flow from Terraform → Graph → Diagram
1. Terraform plan and graph produce raw nodes/edges (tfwrapper).
2. Nodes populated to tfdata graphdict/meta_data.
3. HCL2 parsing reduces ambiguity and enriches variables/locals/outputs (fileparser/interpreter).
4. Relationship detection (graphmaker.check_relationship) looks for references in metadata values using regex rules and implied matches based on keywords and provider config constants.
5. Consolidation, variant mapping, numbering (count/for_each), reverse relations, special resource handlers refine graph structure for rendering.
6. Annotations add auto provider edges (AWS) and user-defined changes.
7. Rendering uses resource_classes with icon directories.

## Problems with Current Design for Multi-Cloud
- Tight coupling to AWS constants in graphmaker, helpers, annotations, interpreter, tfwrapper.
- SPECIAL_RESOURCES is AWS keyed; handlers and implied relations explicitly use aws_* prefixes.
- Variant mapping and consolidation rules hard-coded for AWS.
- Icon and class resolution assumes resource_images/aws and resource_classes/aws.
- interpreter's extract_terraform_resource pattern targets aws_* and module.*.aws_...
- tfwrapper's VPC/subnet relations assume aws_vpc/aws_subnet only.
- No Provider Context: the system does not carry provider identity early; cannot switch rules per provider.
- No Service Mapping: provider-agnostic semantic mapping (compute/network/storage/db) absent.
- Tests expect AWS-only flows; no provider-aware fixtures.

## Proposed Architecture (Multi-Provider)

### Goals:
- Isolate provider-specific behaviors behind a Provider Abstraction Layer.
- Normalize Terraform resource identifiers → Provider Resource Types.
- Load provider CloudConfig dynamically.
- Apply provider-specific resource handlers via registry (strategy/factory).
- Make interpreter/data resolution provider aware (data sources & naming).
- Maintain backward compatibility for AWS; default provider remains AWS if not auto-detected.

### High-level Design

```mermaid
flowchart TD
  CLI[terravision.py CLI] --> TFWrapper
  TFWrapper --> FileParser
  FileParser --> Interpreter
  Interpreter --> GraphMaker
  GraphMaker --> ProviderRuntime
  ProviderRuntime -->|CloudConfig| ProviderConfig
  ProviderRuntime -->|Handlers| ResourceHandlers
  GraphMaker --> Annotations
  Annotations --> ProviderConfig
  GraphMaker --> Drawing
  Drawing --> ResourceClasses
```

### Provider Abstraction Layer

**ProviderRuntime** (new module: `modules/provider_runtime.py`)
- Holds ProviderContext: provider_id ("aws", "azurerm", "google", etc.), ProviderConfig (CloudConfig), ResourceHandlerRegistry, ServiceMapping.
- Resolves provider for each node using tfdata, providers declared in TF, or resource prefix.
- Exposes interfaces used by graphmaker/interpreter/annotations:
  - `get_config()`: returns provider-specific constants (group nodes, variants, annotations, arrow rules...)
  - `get_handler_for(resource_type)`: returns callable for special processing.
  - `map_variant(resource_type, metadata)`: returns variant type based on provider rule.
  - `consolidate(resource_type)`: returns consolidated node type if applicable.
  - `implied_connections(param)`: provider-specific implied connections.

### CloudConfig Refactor
Split `modules/cloud_config.py` into `modules/cloud_config/`:
- `aws.py`
- `azure.py`
- `gcp.py`
- `common.py` (shared enums, shape, interface types)

Each provider file exports:
- CONSOLIDATED_NODES, GROUP_NODES, EDGE_NODES, DRAW_ORDER, AUTO_ANNOTATIONS, NODE_VARIANTS, REVERSE_ARROW_LIST, FORCED_DEST/ORIGIN, IMPLIED_CONNECTIONS, SHARED_SERVICES, ALWAYS/NEVER DRAW LINE, ACRONYMS_LIST, NAME_REPLACEMENTS.

### Service Mapping and Translation

**New module**: `modules/service_mapping.py`
- Map Terraform resource prefix → Provider resource domain + canonical category:
  - `aws_lb` → network.lb
  - `azurerm_lb` → network.lb
  - `google_compute_backend_service` → network.lb
- Expose functions:
  - `detect_provider(resource_name)` → "aws" | "azurerm" | "google" | other
  - `canonical_category(resource_type)` → "compute" | "network" | "storage" | "database" | "security" | "management" | "devtools" | etc.
  - `canonical_resource(resource_type)` → normalized alias for diagram semantics.
- Used by graphmaker and drawing to ensure consistent layout/grouping and naming.

### Resource Class Hierarchy and Factory

Extend `resource_classes/`:
- Add `azure/` and `gcp/` sibling packages with `__init__.py` similar to aws/generic/onprem.
- Introduce a **ResourceNodeFactory** (new module: `modules/node_factory.py`) that:
  - Given provider_id and canonical_category, selects appropriate Node subclass (resource_classes.<provider>.<category> and associated icon dir).
  - Fallback to resource_classes/generic when specific icon is missing.

### Provider-specific Resource Handlers

Split `modules/resource_handlers.py` into provider packages:
- `resource_handlers/__init__.py`: registry and dispatch
- `resource_handlers/aws.py`: move existing aws_* functions
- `resource_handlers/azure.py`: new
- `resource_handlers/gcp.py`: new

SPECIAL_RESOURCES mapping moves to provider CloudConfig files. ProviderRuntime resolves and invokes correct handler.

### Interpreter Provider Awareness

- `interpreter.extract_terraform_resource()` generalized:
  - Regex for any provider prefix: `(aws|azurerm|google|kubernetes|…)_` + name
  - Module pattern similarly generalized.
- DATA_REPLACEMENTS becomes provider-specific; ProviderRuntime supplies replacements for known data sources or passes through.

### Annotations Provider Awareness

- `annotations.AUTO_ANNOTATIONS` sourced from `ProviderRuntime.get_config().AUTO_ANNOTATIONS`
- Logic remains same, but driven by provider-specific configuration.

### tfwrapper Improvements

**Provider detection:**
- Read Terraform plan's resource_changes[].type and module/provider blocks to collect providers in use.
- Validate at least one supported provider exists; remove hard-coded AWS-only check.

**VPC/Subnet implied relations** made provider-aware:
- For Azure: virtual_network and subnet; for GCP: network and subnetwork.
- Move implied relation logic to provider handlers (e.g., network topology helper functions per provider).

### Icon/Image Management

- `resource_images/<provider>` mirroring AWS structure
- Use ResourceNodeFactory to bind resource to image path via Node subclass property `_icon_dir`.

## Phase 1 - Azure Integration Plan

### Azure Service Mappings
- **Compute**: azurerm_linux_virtual_machine, azurerm_windows_virtual_machine → compute.vm
- **Network**: azurerm_virtual_network, azurerm_subnet, azurerm_lb, azurerm_public_ip, azurerm_application_gateway → network.*
- **Storage**: azurerm_storage_account, azurerm_managed_disk → storage.*
- **Database**: azurerm_mysql_flexible_server, azurerm_postgresql_flexible_server, azurerm_sql_server → database.*
- **Security/Identity**: azurerm_network_security_group, azurerm_key_vault → security.*
- **Management/Observability**: azurerm_log_analytics_workspace, azurerm_monitor_* → management.*
- **Edge/CDN/DNS**: azurerm_frontdoor, azurerm_cdn_*, azurerm_dns_* → edge.*

### Azure-specific Resource Handlers
Handlers to implement:
- `azure_handle_vnet_subnets(tfdata)`: link subnets to vnet (CIDR overlap optional).
- `azure_handle_nsg(tfdata)`: resolve NSG relationships similar to AWS SG.
- `azure_handle_lb(tfdata)`: variants (Standard vs Basic, Application Gateway).
- `azure_handle_keyvault(tfdata)`: link references by secrets and certificate usage.
- `azure_handle_frontdoor_cdn(tfdata)`: origin/route linkage.

### Azure Icon Integration
- Add `resource_images/azure/*` categories; ensure icon names map to canonical categories and resource types.

### Azure Terraform Naming Conventions
- Provider prefix: `azurerm_*`
- Module references: `module.<name>.azurerm_<type>.<resource>`
- Data sources: `data.azurerm_*`

## Phase 1 - GCP Integration Plan

### GCP Service Mappings
- **Compute**: google_compute_instance, google_compute_instance_group → compute.*
- **Network**: google_compute_network, google_compute_subnetwork, google_compute_backend_service, google_compute_forwarding_rule, google_compute_target_http(s)_proxy → network.*
- **Storage**: google_storage_bucket, google_compute_disk → storage.*
- **Database**: google_sql_database_instance → database.*
- **Security**: google_compute_firewall, google_kms_key_ring, google_kms_crypto_key → security.*
- **Edge/DNS**: google_dns_managed_zone, google_compute_global_forwarding_rule → edge.*
- **Observability**: google_logging_*, google_monitoring_* → management.*

### GCP-specific Resource Handlers
- `gcp_handle_network_subnets(tfdata)`: connect subnet to network (CIDR optional).
- `gcp_handle_firewall(tfdata)`: reverse relationships similar to SG.
- `gcp_handle_lb(tfdata)`: consolidate L7/L4 components into canonical LB node.
- `gcp_handle_cloud_dns(tfdata)`: link domain references.

### GCP Icon Integration
- Add `resource_images/gcp/*` categories.

### GCP Terraform Naming Conventions
- Provider prefix: `google_*`
- Module references: `module.<name>.google_<type>.<resource>`
- Data sources: `data.google_*`

## Phase 2 - Generic Provider Framework

### Plugin Architecture for New Providers

**New package**: `providers/` with registry (`providers/__init__.py`)

**ProviderDescriptor**:
```python
@dataclass
class ProviderDescriptor:
    id: str
    resource_prefixes: tuple[str, ...]
    cloud_config_module: str
    handler_module: str
```

**ProviderContext** loads descriptors, registers them, and dispatches.

### Provider Registration and Discovery
Auto-detect provider via:
- Terraform plan: `resource_changes[*].type` prefix
- HCL provider blocks from fileparser.iterative_parse (optional)

Multi-provider support: track node-level provider_id based on resource prefix; allow mixed graphs.

### Resource Definition Schema
**CloudConfig schema** (common types):
- CONSOLIDATED_NODES: [{prefix: {resource_name, import_location, vpc/network flag, edge_service flag}}]
- GROUP_NODES: [prefixes]
- EDGE_NODES: [prefixes]
- DRAW_ORDER: [[list or nested arrays]]
- AUTO_ANNOTATIONS: [{prefix: {link: [nodes], delete: [prefix], arrow: "forward"/"reverse"}}]
- NODE_VARIANTS: {prefix: {match_keyword: variant_prefix}}
- ARROW RULES: REVERSE_ARROW_LIST, FORCED_DEST, FORCED_ORIGIN
- IMPLIED_CONNECTIONS: {keyword: target_prefix}
- SHARED_SERVICES: [prefixes]
- NAME_REPLACEMENTS, ACRONYMS_LIST.

### Auto-detection of Provider from Terraform Code
- Prefer resource prefix identification.
- Fallback to declared provider names in HCL (fileparser).
- Persist provider_id per node in `tfdata.meta_data[node]["provider"]`.

### Priority Provider List and Effort Estimation

1. **Kubernetes** (kubernetes_*): medium
2. **Docker** (docker_*): low-medium
3. **GitHub** (github_*): low
4. **Cloudflare** (cloudflare_*): medium
5. **Datadog** (datadog_*): medium
6. **HashiCorp Vault** (vault_*): medium
7. **Helm** (helm_release, helm_chart): low-medium
8. **PostgreSQL** (postgresql_*): low
9. **AzureAD** (azuread_*): medium (identity-specific)
10. **AWS EKS** (extending current): low (already covered by AWS)

**Effort drivers:**
- Quality of CloudConfig mapping and icons
- Handler complexity for network/security semantics
- Tests and fixtures across providers

## API/Interface Specifications

### New Interfaces

**modules/provider_runtime.py**
```python
class ProviderContext:
    def __init__(self, descriptors: Dict[str, ProviderDescriptor])
    def detect_provider_for_node(node: str) -> str
    def get_config(provider_id: str) -> CloudConfig
    def get_handler(provider_id: str, resource_prefix: str) -> Callable[[tfdata], tfdata]
    def consolidate(provider_id: str, resource_type: str) -> Optional[str]
    def map_variant(provider_id: str, resource_type: str, metadata: dict) -> Optional[str]
    def implied_connections(provider_id: str, param: str) -> List[str]
```

**modules/service_mapping.py**
```python
def detect_provider(resource_name: str) -> str
def canonical_category(resource_type: str) -> str
def canonical_resource(resource_type: str) -> str
```

**modules/node_factory.py**
```python
def get_node_class(provider_id: str, category: str) -> Type[Node]
def get_icon_dir(provider_id: str) -> str
```

### Refactor Signatures
- `graphmaker` functions accept ProviderContext or provider_id:
  - `add_relations(tfdata, provider_ctx)`
  - `consolidate_nodes(tfdata, provider_ctx)`
  - `handle_variants(tfdata, provider_ctx)`
  - `handle_special_resources(tfdata, provider_ctx)`
  - `reverse_relations(tfdata, provider_ctx)`
- `interpreter.find_replace_values(varstring, module, tfdata, provider_ctx)`
- `annotations.add_annotations(tfdata, provider_ctx)`
- `tfwrapper.tf_makegraph(tfdata, provider_ctx)`

## Data Structure Specifications

### tfdata additions:
- `tfdata["providers"]`: Set[str] detected from plan/HCL.
- `tfdata["node_provider_map"]`: {node: provider_id}
- `tfdata["provider_ctx"]`: ProviderContext reference (non-serializable for runtime only).

### meta_data additions:
- `meta_data[node]["provider"]`: provider_id
- `meta_data[node]["category"]`: canonical category (compute/network/storage/etc.) where applicable.

## Step-by-step Implementation Guide

### 1. Introduce ProviderContext
- Create `modules/provider_runtime.py` with ProviderDescriptor/ProviderContext.
- Initialize ProviderContext in `compile_tfdata()` after `tfwrapper.tf_makegraph()`, using `tfdata["tf_resources_created"]` to collect providers.
- Populate `tfdata["providers"]` and `tfdata["node_provider_map"]` by scanning node_list and prefixes.

### 2. CloudConfig refactor
- Move AWS_* constants to `modules/cloud_config/aws.py` unchanged.
- Create `modules/cloud_config/common.py` with dataclasses or TypedDicts for config contract.
- Build `modules/cloud_config/azure.py` and `gcp.py` with initial minimal sets: GROUP_NODES, EDGE_NODES, DRAW_ORDER, NODE_VARIANTS, AUTO_ANNOTATIONS, IMPLIED_CONNECTIONS, CONSOLIDATED_NODES, SHARED_SERVICES, NAME_REPLACEMENTS.

### 3. ResourceHandlers refactor
- Move AWS handlers to `resource_handlers/aws.py`.
- Create `resource_handlers/__init__.py` with registry: `get_handler(provider_id, resource_prefix)`.
- Implement base azure/gcp handlers: vnet/subnet, NSG/firewall, LB variants, DNS/CDN mapping.

### 4. Update graphmaker to be provider-aware
- Replace imports of AWS_* with `provider_ctx.get_config(current_provider_id_for_node)`.
- Where lists are applied (e.g., GROUP_NODES), resolve per node/provider.
- SPECIAL_RESOURCES dispatch via `provider_ctx.get_handler`.

### 5. Update interpreter and helpers
- `interpreter.extract_terraform_resource`: support `(aws|azurerm|google)_` patterns; module pattern generalized.
- DATA_REPLACEMENTS provided by `provider_ctx.get_config().DATA_REPLACEMENTS` (optional).
- `helpers.pretty_name`: use provider-specific NAME_REPLACEMENTS and ACRONYMS_LIST via provider_ctx using node's provider_id.
- `consolidated_node_check`: route to provider-specific CONSOLIDATED_NODES.
- `check_variant`: provider-specific NODE_VARIANTS.

### 6. Update annotations
- Use `provider_ctx.get_config(provider_for_node).AUTO_ANNOTATIONS` per node.

### 7. Update tfwrapper implied relations
- Replace `add_vpc_implied_relations()` with provider dispatch:
  - For each provider in `tfdata["providers"]`, call handler like `aws_handle_vpc_subnets` / `azure_handle_vnet_subnets` / `gcp_handle_network_subnets`.

### 8. Resource classes and icons
- Add `resource_classes/azure/__init__.py`; define `_Azure(Node)` with `_provider="azurerm"` and icon dir `resource_images/azure`.
- Add `resource_classes/gcp/__init__.py`; define `_GCP(Node)` with `_provider="google"` and icon dir `resource_images/gcp`.
- Add basic category modules (compute, network, storage, database, security, management).
- Populate `resource_images/azure` and `resource_images/gcp` with at least core icons; fallback to generic when missing.

### 9. Tests
- Add provider detection unit tests.
- Update existing tests to run with provider_ctx; keep AWS fixtures.
- Add Azure/GCP fixtures and test graphmaker flows.
- Integration tests across sample Terraform for Azure/GCP.

## Testing Strategy

### Unit tests:
- Provider detection from resource prefixes and HCL providers.
- CloudConfig loading and handler dispatch per provider.
- Interpreter variable resolution with provider-specific data sources.
- Graphmaker relationship detection using provider-specific IMPLIED_CONNECTIONS, GROUP_NODES, variants, consolidation.
- Annotations application per provider AUTO_ANNOTATIONS.

### Integration tests:
- Sample Azure vnet/subnet + VM + NSG project → expected graph JSON.
- Sample GCP network/subnetwork + instance + firewall + load balancer → expected graph JSON.
- Mixed provider project (e.g., AWS + Cloudflare) validates multi-provider node_provider_map correctness and rendering.

### Visual validation:
- Render diagrams for sample Azure and GCP projects; verify grouping, edge direction, variants.

## Migration Guide for Existing Users

- No CLI changes; existing flags continue to work.
- AWS-only projects behave as before; minor label/icon differences may occur due to improved name replacements.
- If users have custom annotations YAML referencing AWS-only nodes, they continue to work. For Azure/GCP projects, adopt provider-specific resource names in annotations.
- Document the new ability to pass pre-generated tfgraph JSON from any provider.
- Version bump to 0.9; note deprecation: `modules.cloud_config.py` direct AWS_* imports will be removed in 1.0. Use ProviderContext for internal extension development.

## Acceptance Criteria

- **Azure**: Minimal viable support for vnet/subnet, VM, NSG, LB, DNS icons and handlers; correct grouping and relations.
- **GCP**: Minimal viable support for network/subnetwork, instance, firewall, LB, DNS icons and handlers; correct grouping and relations.
- Graphmaker and interpreter no longer import AWS_* directly; they operate through ProviderContext.
- Annotations apply provider-specific AUTO_ANNOTATIONS.
- Tests added for provider detection, graph correctness on Azure/GCP samples.
- Documentation generated with diagrams and implementation specifics.

## Code Examples

### ProviderDescriptor and ProviderContext

```python
# modules/provider_runtime.py
from typing import Callable, Dict, Optional
from dataclasses import dataclass

@dataclass
class ProviderDescriptor:
    id: str
    resource_prefixes: tuple[str, ...]
    cloud_config_module: str
    handler_module: str

class ProviderContext:
    def __init__(self, descriptors: Dict[str, ProviderDescriptor]):
        self.descriptors = descriptors
        self.configs = {}   # provider_id -> loaded module
        self.handlers = {}  # provider_id -> handler module
        
    def detect_provider_for_node(self, node: str) -> Optional[str]:
        for pid, d in self.descriptors.items():
            if any(node.startswith(pfx) or (".%s" % pfx in node) for pfx in d.resource_prefixes):
                return pid
        return None
        
    def get_config(self, provider_id: str):
        if provider_id not in self.configs:
            self.configs[provider_id] = __import__(
                f"modules.cloud_config.{provider_id}", 
                fromlist=['*']
            )
        return self.configs[provider_id]
        
    def get_handler(self, provider_id: str) -> object:
        if provider_id not in self.handlers:
            self.handlers[provider_id] = __import__(
                f"resource_handlers.{provider_id}", 
                fromlist=['*']
            )
        return self.handlers[provider_id]
```

### Service Mapping

```python
# modules/service_mapping.py
def detect_provider(resource_name: str) -> str:
    if resource_name.startswith("aws_"): 
        return "aws"
    if resource_name.startswith("azurerm_"): 
        return "azurerm"
    if resource_name.startswith("google_"): 
        return "google"
    return "generic"

def canonical_category(resource_type: str) -> str:
    rt = resource_type.split(".")[0]
    if any(k in rt for k in ("_lb","_backend_service","_forwarding_rule","frontdoor","application_gateway")):
        return "network"
    if any(k in rt for k in ("_vpc","_subnet","_virtual_network","_subnetwork","_network")):
        return "network"
    if any(k in rt for k in ("_instance","virtual_machine","compute_instance")):
        return "compute"
    return "general"
```

### GraphMaker Provider-Aware Usage

```python
# modules/graphmaker.py
def handle_special_resources(tfdata: Dict[str, Any], provider_ctx) -> Dict[str, Any]:
    for node in tfdata["node_list"]:
        provider_id = tfdata["meta_data"][node].get("provider") or provider_ctx.detect_provider_for_node(node)
        if not provider_id: 
            continue
        cfg = provider_ctx.get_config(provider_id)
        for resource_prefix, handler_name in cfg.SPECIAL_RESOURCES.items():
            if helpers.get_no_module_name(node).startswith(resource_prefix):
                handler_mod = provider_ctx.get_handler(provider_id)
                tfdata = getattr(handler_mod, handler_name)(tfdata)
    return tfdata
```

### Azure Handler Example

```python
# resource_handlers/azure.py
def azure_handle_vnet_subnets(tfdata):
    vnets = [k for k in tfdata["graphdict"] if k.startswith("azurerm_virtual_network.")]
    subnets = [k for k in tfdata["graphdict"] if k.startswith("azurerm_subnet.")]
    for vnet in vnets:
        for subnet in subnets:
            if subnet not in tfdata["graphdict"][vnet]:
                tfdata["graphdict"][vnet].append(subnet)
    return tfdata
```

## Conclusion

This architectural design provides a comprehensive, actionable roadmap for extending TerraVision to support Azure, GCP, and other Terraform providers through a clean provider abstraction layer. The proposed changes maintain backward compatibility while enabling extensible multi-cloud support through well-defined interfaces, provider-specific configurations, and a pluggable handler system.
