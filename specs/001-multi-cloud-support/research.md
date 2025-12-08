# Research Document: Multi-Cloud Provider Support

**Feature**: Multi-Cloud Provider Support (GCP & Azure)
**Date**: 2025-12-07
**Research Phase**: Phase 0

## Executive Summary

This research explores the architectural changes required to add GCP and Azure support to TerraVision. The codebase currently has AWS-exclusive logic but Azure and GCP resource classes already exist. Key findings:

1. **Provider detection does not exist** - need to implement resource prefix scanning
2. **Configuration is AWS-hardcoded** - need provider-specific config files
3. **Resource classes for Azure/GCP exist but are not imported** - need dynamic imports
4. **Resource handlers are AWS-specific** - need provider-agnostic dispatching
5. **Single output file hardcoded** - need multi-provider output generation
6. **AI prompts are AWS-only** - need provider-specific prompts

## Research Questions & Findings

### 1. Provider Detection Strategy

**Research Question**: How should TerraVision detect which cloud provider(s) are used in a Terraform project?

**Current State**:
- **No provider detection logic exists** (terravision/modules/fileparser.py:367)
- AWS resources assumed throughout: `if "aws_" in line`
- Resource type extraction from Terraform graph but no provider awareness

**Options Evaluated**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A. Provider Block Parsing | Parse `provider "google"` / `provider "azurerm"` blocks from .tf files | Explicit, standard Terraform syntax | Doesn't handle implicit provider inheritance from modules |
| B. Resource Prefix Scanning | Scan all resources in tfdata for prefixes (aws_, google_, azurerm_) | Catches all resources regardless of provider block location | Requires maintaining prefix mapping |
| C. Hybrid Approach | Provider blocks + resource prefix fallback | Most reliable, handles edge cases | More complex implementation |

**Decision**: **Option C - Hybrid Approach**

**Rationale**:
- Provider blocks give explicit intent
- Resource prefix scanning handles inherited providers and validates blocks
- Matches Terraform's own resolution logic
- Handles edge cases (provider aliases, inherited from parent modules)

**Implementation Location**: New module `provider_detector.py`

**API Design**:
```python
def detect_providers(tfdata: Dict[str, Any]) -> List[str]:
    """Detect cloud providers from Terraform data.

    Returns: List of provider names: ['aws', 'azure', 'gcp']
    """

def get_primary_provider(providers: List[str]) -> str:
    """Determine primary provider (most resources).

    Returns: 'aws' | 'azure' | 'gcp'
    """
```

**Resource Prefix Mapping**:
```python
PROVIDER_PREFIXES = {
    'aws_': 'aws',
    'azurerm_': 'azure',
    'google_': 'gcp',
    'azuread_': 'azure',  # Azure AD resources
    'azurestack_': 'azure',
    'azapi_': 'azure',
}
```

---

### 2. Configuration Architecture Pattern

**Research Question**: How should provider-specific configurations be structured and loaded?

**Current State**:
- Single monolithic `cloud_config.py` with 317 lines of AWS-specific config
- Imported by 6 modules: terravision.py, graphmaker.py, resource_handlers.py, drawing.py, helpers.py, tfwrapper.py
- Contains 26 configuration variables (AWS_CONSOLIDATED_NODES, AWS_GROUP_NODES, AWS_REFINEMENT_PROMPT, etc.)

**Options Evaluated**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A. Single File with Nested Dicts | Keep cloud_config.py, nest configs: `CONFIG = {'aws': {...}, 'azure': {...}}` | Minimal file changes, centralized | Becomes very large (900+ lines), hard to maintain |
| B. Separate Files, Manual Import | cloud_config_aws.py, cloud_config_azure.py, cloud_config_gcp.py | Clear separation, easy to find provider logic | Requires changing all import statements |
| C. Factory Pattern | Config loader class with provider-specific modules | Most flexible, testable | More abstraction overhead |

**Decision**: **Option B - Separate Files (No Shim)**

**Rationale**:
- Clear provider separation (200-300 lines per file)
- Aligns with constitution's "simplicity" principle
- Easy to extend with new providers
- Cleaner architecture without shim layer
- All imports updated to use dynamic config loader

**Implementation**:
```python
# modules/cloud_config_aws.py (renamed from cloud_config.py)
AWS_CONSOLIDATED_NODES = [...]
AWS_GROUP_NODES = [...]
# ... all AWS config

# modules/cloud_config_azure.py (new)
AZURE_CONSOLIDATED_NODES = [...]
AZURE_GROUP_NODES = [...]
# ... all Azure config

# modules/cloud_config_gcp.py (new)
GCP_CONSOLIDATED_NODES = [...]
GCP_GROUP_NODES = [...]
# ... all GCP config

# modules/config_loader.py (new)
def load_config(provider: str):
    """Load provider-specific configuration."""
    if provider == 'aws':
        import modules.cloud_config_aws as config
    elif provider == 'azure':
        import modules.cloud_config_azure as config
    elif provider == 'gcp':
        import modules.cloud_config_gcp as config
    return config
```

**Breaking Change**: Existing code with `import modules.cloud_config` must be updated to use `config_loader.load_config(provider)`. All internal TerraVision modules will be updated in this feature.

**Configuration Variables to Replicate Per Provider**:
- CONSOLIDATED_NODES (grouping rules)
- GROUP_NODES (hierarchy: VPC → Subnet → SG for AWS; Resource Group → VNet → Subnet for Azure)
- EDGE_NODES, OUTER_NODES (placement rules)
- DRAW_ORDER (node rendering sequence)
- AUTO_ANNOTATIONS (automatic relationship rules)
- NODE_VARIANTS (resource type variations: ALB/NLB, FARGATE/EC2)
- REVERSE_ARROW_LIST (connection direction)
- IMPLIED_CONNECTIONS (keyword-based auto-linking)
- SPECIAL_RESOURCES (handler function mapping)
- SHARED_SERVICES (shared resource identification)
- ALWAYS_DRAW_LINE, NEVER_DRAW_LINE (edge visibility)
- ACRONYMS_LIST (display name formatting)
- NAME_REPLACEMENTS (label mapping)
- REFINEMENT_PROMPT, DOCUMENTATION_PROMPT (LLM prompts)

---

### 3. Resource Handler Refactoring Strategy

**Research Question**: How should AWS-specific resource handlers be refactored to support multiple providers?

**Current State**:
- Single `resource_handlers.py` with 1,032 lines of AWS-specific handler functions
- 15 handler functions (aws_handle_autoscaling, aws_handle_cloudfront_pregraph, aws_handle_subnet_azs, etc.)
- Invoked via dynamic dispatch from graphmaker.py using SPECIAL_RESOURCES mapping

**Options Evaluated**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A. Single File with Provider Conditionals | Add `if provider == 'azure'` branches | Minimal restructuring | Unmanage able, violates SRP |
| B. Separate Handler Files | resource_handlers_aws.py, resource_handlers_azure.py, resource_handlers_gcp.py | Clear separation, testable | Need dispatch mechanism |
| C. Class-Based Handlers | ProviderHandler base class with provider subclasses | Most flexible, OOP | Overkill for current needs |

**Decision**: **Option B - Separate Handler Files with Provider-Aware Dispatch**

**Rationale**:
- Matches configuration file pattern
- Each provider has unique handler requirements (Azure resource groups ≠ AWS VPCs)
- Easy to maintain provider-specific logic
- Testable in isolation

**Implementation Pattern**:
```python
# modules/resource_handlers_aws.py
def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """AWS-specific special case handling."""
    tfdata["graphdict"] = link_sqs_queue_policy(tfdata["graphdict"])
    # ... AWS logic
    return tfdata

def aws_handle_autoscaling(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    # ... AWS autoscaling logic

# modules/resource_handlers_azure.py
def handle_special_cases(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Azure-specific special case handling."""
    tfdata["graphdict"] = link_resource_groups(tfdata["graphdict"])
    # ... Azure logic
    return tfdata

def azure_handle_resource_groups(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    # ... Azure resource group hierarchy logic

# modules/resource_handlers.py (dispatcher)
def handle_special_cases(tfdata: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Provider-aware special case handling dispatcher."""
    if provider == 'aws':
        from modules.resource_handlers_aws import handle_special_cases as aws_handle
        return aws_handle(tfdata)
    elif provider == 'azure':
        from modules.resource_handlers_azure import handle_special_cases as azure_handle
        return azure_handle(tfdata)
    elif provider == 'gcp':
        from modules.resource_handlers_gcp import handle_special_cases as gcp_handle
        return gcp_handle(tfdata)
```

**Provider-Specific Handler Requirements**:

| Provider | Unique Handlers Needed |
|----------|------------------------|
| **AWS** | Autoscaling targets, CloudFront origins, EFS mount targets, RDS subnet groups, Security group relationships, VPC endpoints |
| **Azure** | Resource group hierarchy, VNet/Subnet relationships, Network Security Groups, Application Gateways, Storage account connections |
| **GCP** | Project/folder hierarchy, VPC/subnet relationships, Firewall rules, GKE cluster relationships, Cloud Functions triggers |

---

### 4. Resource Class Dynamic Import Strategy

**Research Question**: How should resource classes be dynamically imported based on detected provider?

**Current State**:
- `drawing.py` (Lines 20-47) statically imports AWS resource classes only
- Azure and GCP classes exist in `resource_classes/azure/` and `resource_classes/gcp/` but are never imported
- Class lookup uses `getattr(sys.modules[__name__], resource_type)` assuming all classes are in namespace

**Current Import Pattern** (drawing.py:20-47):
```python
from resource_classes.aws.analytics import *
from resource_classes.aws.ar import *
# ... 27 AWS category imports
from resource_classes.aws.storage import *
from resource_classes.aws.general import *
# Azure and GCP NOT imported!
```

**Options Evaluated**:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A. Import All Providers Always | Import AWS + Azure + GCP at startup | Simple, no conditional logic | Slower startup, unnecessary memory |
| B. Dynamic Import After Detection | Detect provider → import only needed classes | Faster startup, less memory | More complex, import during execution |
| C. Lazy Loading Per Resource | Import class only when needed | Minimum overhead | Many import statements during execution |

**Decision**: **Option B - Dynamic Import After Provider Detection**

**Rationale**:
- Most projects are single-cloud (per spec assumptions)
- Import cost paid once at detection time, not per-resource
- Cleaner namespace (only relevant provider classes loaded)
- Aligns with provider detection flow

**Implementation Pattern**:
```python
# drawing.py (refactored)
def import_provider_resources(providers: List[str]):
    """Dynamically import resource classes for detected providers."""
    for provider in providers:
        if provider == 'aws':
            from resource_classes.aws.analytics import *
            from resource_classes.aws.compute import *
            # ... all AWS categories
        elif provider == 'azure':
            from resource_classes.azure.compute import *
            from resource_classes.azure.database import *
            # ... all Azure categories
        elif provider == 'gcp':
            from resource_classes.gcp.compute import *
            from resource_classes.gcp.analytics import *
            # ... all GCP categories

# In drawing pipeline:
providers = provider_detector.detect_providers(tfdata)
import_provider_resources(providers)
```

**Class Lookup Enhancement**:
```python
# Current: getattr(sys.modules[__name__], resource_type)
# Problem: Assumes class name matches resource type exactly

# Enhanced with fallback:
def get_resource_class(resource_type: str, provider: str):
    """Get resource class with provider-aware fallback."""
    try:
        return getattr(sys.modules['__main__'], resource_type)
    except AttributeError:
        # Try generic class for unsupported resources
        from resource_classes.generic import Compute, Storage, Network
        if 'compute' in resource_type or 'instance' in resource_type:
            return Compute
        elif 'storage' in resource_type or 'bucket' in resource_type:
            return Storage
        else:
            return Network
```

**Alias Resolution** (Azure and GCP classes already define aliases):
```python
# gcp/analytics.py:61-71
google_bigquery_dataset = Bigquery
google_bigquery_table = Bigquery

# azure/compute.py defines aliases too
azurerm_virtual_machine = VirtualMachine
azurerm_linux_virtual_machine = LinuxVirtualMachine
```

---

### 5. Multi-Provider Output File Strategy

**Research Question**: For projects with multiple providers, how should output files be generated?

**Current State**:
- Single output file: `--outfile architecture` → `architecture.png`
- Hardcoded AWS cloud boundary: `cloudGroup = AWSgroup()` (drawing.py:485)
- No multi-provider output logic

**Options Evaluated**:

| Option | Output Behavior | Pros | Cons |
|--------|-----------------|------|------|
| A. Separate Files Per Provider | architecture-aws.png, architecture-azure.png, architecture-gcp.png | Each diagram follows provider conventions, easy to implement | Multiple files, no unified view |
| B. Unified Multi-Cloud Diagram | architecture.png with all providers | Single comprehensive view | Complex cross-cloud visual design, ambiguous grouping |
| C. Provider Flag Option | --provider aws generates only AWS portion | User control, explicit | Requires multiple runs for multi-cloud |

**Decision**: **Option A - Separate Files Per Provider (with optional unified view future enhancement)**

**Rationale**:
- Matches user clarification: "usually each terraform project will be only for one cloud provider and if in rare cases there are multi cloud providers in the source then a separate diagram per provider should be generated"
- Each provider diagram follows its own architectural conventions (AWS VPC grouping ≠ Azure Resource Group grouping)
- Simpler implementation for MVP
- Leaves door open for Option B as future enhancement with `--unified` flag

**Implementation Pattern**:
```python
# Filename generation (terravision.py)
def generate_output_filename(base_filename: str, provider: str, providers: List[str]) -> str:
    """Generate provider-specific output filename."""
    if len(providers) == 1:
        # Single provider: use base filename
        return base_filename  # "architecture"
    else:
        # Multi-provider: add provider suffix
        return f"{base_filename}-{provider}"  # "architecture-aws", "architecture-azure"

# Drawing coordination
providers = detect_providers(tfdata)
for provider in providers:
    # Filter tfdata to resources for this provider
    provider_tfdata = filter_by_provider(tfdata, provider)

    # Load provider-specific config
    config = load_config(provider)

    # Generate diagram
    filename = generate_output_filename(outfile, provider, providers)
    drawing.render_diagram(provider_tfdata, show, simplified, filename, format, source, provider)
```

**Provider-Specific Cloud Boundaries**:
```python
# drawing.py
def get_cloud_group(provider: str):
    """Get provider-specific cloud boundary group."""
    if provider == 'aws':
        return AWSgroup()
    elif provider == 'azure':
        return Azuregroup()  # Create if doesn't exist
    elif provider == 'gcp':
        return GCPgroup()   # Create if doesn't exist
```

**Output Messaging** (terravision.py):
```
# Single provider:
Output file: architecture.png

# Multi-provider:
Detected 2 providers: aws, azure
Output files:
  AWS: architecture-aws.png
  Azure: architecture-azure.png
```

---

### 6. AI Prompt Customization for Each Provider

**Research Question**: How should provider-specific AI prompts be designed and selected?

**Current State**:
- AWS_REFINEMENT_PROMPT hardcoded in cloud_config.py (Lines 277-299)
- Prompt references AWS-specific concepts: VPC, Subnet, AZ, Security Groups, "tv_aws_internet"
- No Azure or GCP equivalents

**Provider-Specific Architectural Patterns**:

| Provider | Hierarchy Pattern | Key Grouping Concepts |
|----------|-------------------|----------------------|
| **AWS** | VPC → AZ → Subnet → Security Group → Resource | VPC isolation, AZ redundancy, SG network rules |
| **Azure** | Resource Group → VNet → Subnet → NSG → Resource | Resource Group lifecycle management, VNet segmentation, NSG security |
| **GCP** | Project → VPC → Region → Subnet → Firewall → Resource | Project isolation, global VPC, regional subnets, firewall rules |

**Prompt Template Strategy**:

**Azure Refinement Prompt** (to be created):
```python
AZURE_REFINEMENT_PROMPT = """
You are an Azure architecture diagram refinement expert. Analyze this Terraform resource graph and improve the layout following Azure best practices:

Azure Hierarchy Rules:
1. Resource Groups are the top-level organizational unit - group related resources together
2. VNets (Virtual Networks) contain Subnets - place VNets inside Resource Groups
3. Network Security Groups (NSGs) should contain resources they protect
4. Application Gateways, Load Balancers should be clearly connected to backend pools
5. Storage Accounts should show connections to resources that use them

Azure Naming Conventions:
- Resources start with azurerm_ prefix
- Use Azure-approved icons and terminology
- Resource Groups depicted as: azurerm_resource_group.{name}

Special Azure Resources:
- azure_resource_group.shared_services - group for shared infrastructure
- tv_azure_internet - external internet boundary
- azurerm_application_gateway - place at VNet edge with backend pool connections

Output Requirements:
- Return corrected JSON graph with improved grouping
- Maintain all original resources and connections
- Add missing implicit relationships (e.g., VM → NSG, VM → VNet)
- Fix any misplaced resources according to Azure hierarchy

Current graph:
{graph_json}
"""
```

**GCP Refinement Prompt** (to be created):
```python
GCP_REFINEMENT_PROMPT = """
You are a Google Cloud Platform architecture diagram refinement expert. Analyze this Terraform resource graph and improve the layout following GCP best practices:

GCP Hierarchy Rules:
1. Projects are the top-level isolation boundary
2. VPCs are global - span all regions
3. Subnets are regional - place inside VPC but grouped by region
4. Firewall Rules apply to VPC level - show as VPC-level nodes
5. GKE Clusters should clearly show node pools and networking

GCP Naming Conventions:
- Resources start with google_ prefix
- Use GCP-approved icons and terminology
- Projects depicted as: google_project.{name}

Special GCP Resources:
- google_compute_network - global VPC
- google_compute_subnetwork - regional subnet
- google_compute_firewall - VPC-level security
- tv_gcp_internet - external internet boundary

Output Requirements:
- Return corrected JSON graph with improved grouping
- Maintain all original resources and connections
- Add missing implicit relationships (e.g., Instance → Subnet, Instance → Firewall)
- Fix any misplaced resources according to GCP hierarchy

Current graph:
{graph_json}
"""
```

**Prompt Selection Logic**:
```python
# terravision.py refactored
def _get_refinement_prompt(provider: str) -> str:
    """Get provider-specific refinement prompt."""
    config = load_config(provider)
    return config.REFINEMENT_PROMPT

def _refine_with_llm(tfdata, aibackend, debug, provider):
    """Refine diagram with provider-specific LLM prompt."""
    prompt = _get_refinement_prompt(provider)
    # ... rest of LLM invocation with provider-specific prompt
```

---

## Implementation Decisions Summary

| Component | Decision | Implementation Location |
|-----------|----------|------------------------|
| **Provider Detection** | Hybrid: Provider blocks + resource prefix scanning | New: `modules/provider_detector.py` |
| **Configuration** | Separate files per provider | New: `modules/cloud_config_azure.py`, `modules/cloud_config_gcp.py`; Refactor: `modules/cloud_config.py` → AWS shim |
| **Resource Handlers** | Separate handler files with dispatcher | New: `modules/resource_handlers_azure.py`, `modules/resource_handlers_gcp.py`; Refactor: `modules/resource_handlers.py` → dispatcher |
| **Resource Classes** | Dynamic import after provider detection | Modify: `modules/drawing.py` |
| **Output Files** | Separate file per provider for multi-cloud projects | Modify: `terravision.py`, `modules/drawing.py` |
| **AI Prompts** | Provider-specific prompts in provider configs | Add: AZURE_REFINEMENT_PROMPT, GCP_REFINEMENT_PROMPT to respective configs |

---

## Alternatives Considered and Rejected

### 1. Unified Configuration Dictionary

**Rejected Approach**: Single `cloud_config.py` with nested dictionaries:
```python
CONFIG = {
    'aws': {'CONSOLIDATED_NODES': [...], 'GROUP_NODES': [...], ...},
    'azure': {'CONSOLIDATED_NODES': [...], 'GROUP_NODES': [...], ...},
    'gcp': {'CONSOLIDATED_NODES': [...], 'GROUP_NODES': [...], ...}
}
```

**Why Rejected**:
- Would create 900+ line file (300 lines × 3 providers)
- Hard to navigate and maintain
- All providers loaded even if only one used
- Doesn't follow "simplicity" principle from constitution

---

### 2. Class-Based Handler Architecture

**Rejected Approach**: Abstract base class with provider subclasses:
```python
class ResourceHandler:
    def handle_special_cases(self, tfdata): pass
    def handle_autoscaling(self, tfdata): pass

class AWSHandler(ResourceHandler): ...
class AzureHandler(ResourceHandler): ...
class GCPHandler(ResourceHandler): ...
```

**Why Rejected**:
- Over-engineered for current needs
- Each provider has different special resources (AWS autoscaling ≠ Azure scale sets ≠ GCP MIGs)
- Not all handlers have equivalents across providers
- Functional approach simpler for this use case

---

### 3. Unified Multi-Cloud Diagrams

**Rejected Approach** (for MVP): Generate single diagram with all providers:
```
[AWS VPC]    [Azure Resource Group]    [GCP Project]
   |              |                        |
  EC2          VM                      Compute
```

**Why Rejected**:
- Complex visual design (how to show cross-cloud connections?)
- Provider grouping concepts don't align (VPC ≠ Resource Group ≠ Project)
- User explicitly requested separate diagrams: "usually each terraform project will be only for one cloud provider and if in rare cases there are multi cloud providers in the source then a separate diagram per provider should be generated"
- Can be added as future enhancement with `--unified` flag

---

## Best Practices from Similar Tools

### Terraform Graph (`terraform graph`)
- Outputs DOT format, provider-agnostic
- Resource types contain provider prefix (aws_, azurerm_, google_)
- **Lesson**: Resource prefixes are reliable provider indicators

### Diagrams (Python library)
- Separate modules per provider: `diagrams.aws`, `diagrams.azure`, `diagrams.gcp`
- Lazy imports - only load needed provider
- **Lesson**: Provider-specific modules keep code organized

### AWS Well-Architected Tool
- Provider-specific best practices and patterns
- Architecture reviews use provider-specific rules
- **Lesson**: AI prompts should encode provider conventions

### Cloudcraft, Lucidscale (Commercial alternatives)
- Separate diagrams per cloud provider
- Provider-specific icon libraries
- Cross-cloud connections shown via external integrations
- **Lesson**: Separate diagrams are industry standard for multi-cloud

---

## Technical Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Breaking AWS users** | HIGH | MEDIUM | Update all internal imports to use config_loader; comprehensive regression tests; clear migration notes |
| **Incomplete Azure/GCP icon coverage** | MEDIUM | HIGH | Fallback to generic icons; document unsupported resources; prioritize 50 core services |
| **Performance degradation** | MEDIUM | LOW | Lazy provider detection; cache provider results; profile critical paths |
| **Provider detection failures** | HIGH | MEDIUM | Hybrid detection (blocks + prefixes); explicit error messages; fallback to AWS default |
| **Cross-cloud resource references** | LOW | LOW | Rare in practice per user; document limitation; consider in future unified diagram |

---

## Open Questions for Planning Phase

1. **Icon Library Completeness**: Should Azure/GCP launch as "Beta" with 30-50 resources or wait for 200+ "production-ready" status per constitution RC-003?
   - **Recommendation**: Launch as beta with clear documentation of supported resources

2. **Backward Compatibility**: Should old `import cloud_config` continue working or require updating imports?
   - **Decision**: No shim - `cloud_config.py` renamed to `cloud_config_aws.py`, all imports updated to use `config_loader.load_config(provider)`
   - **Breaking Change**: External code importing `modules.cloud_config` will need to update, but TerraVision is primarily a CLI tool (not a library), so external usage is minimal

3. **Provider Detection Caching**: Should provider detection result be cached in tfdata to avoid re-detection?
   - **Recommendation**: Yes, add `tfdata["detected_providers"]` and `tfdata["primary_provider"]`

4. **Generic Icon Fallback**: When Azure/GCP resource has no specific icon, use generic icon or skip rendering?
   - **Recommendation**: Fallback to generic icons (Compute, Storage, Network) with warning message

5. **Multi-Output Messaging**: For multi-cloud projects, show progress per provider or consolidated summary?
   - **Recommendation**: Show "Detected 2 providers" upfront, then "Generating AWS diagram...", "Generating Azure diagram..."

---

## Next Steps (Phase 1: Design & Contracts)

Based on this research, Phase 1 should produce:

1. **Data Model** (`data-model.md`):
   - ProviderDetectionResult entity
   - ProviderConfiguration entity
   - ResourceHandlerRegistry entity

2. **Contracts** (`contracts/`):
   - Provider Detection API contract
   - Configuration Loader API contract
   - Resource Handler Dispatcher API contract

3. **Quickstart Guide** (`quickstart.md`):
   - How to generate Azure diagrams
   - How to generate GCP diagrams
   - Multi-cloud project handling

---

## References

- TerraVision codebase exploration (2025-12-07)
- Terraform Provider Documentation: https://registry.terraform.io/browse/providers
- Azure Terraform Provider: https://registry.terraform.io/providers/hashicorp/azurerm
- GCP Terraform Provider: https://registry.terraform.io/providers/hashicorp/google
- TerraVision Constitution v1.0.0 (Principle V: Multi-Cloud & Provider Agnostic Design)
