# TerraVision Code Review

## Executive Summary
TerraVision is a Terraform-to-architecture-diagram generator with a CLI entrypoint, a pipeline that parses Terraform plans/graphs, enriches relationships, and renders AWS-centric diagrams. The system is production-leaning but exhibits significant AWS-specific coupling, ad-hoc error handling (many sys.exit with user-facing click.echo), type annotation gaps, and several correctness bugs in core logic. Extensibility to Azure/GCP is currently blocked by pervasive AWS-config constants and imports throughout modules, particularly drawing, graphmaker, helpers, resource_handlers, and cloud_config. Performance-wise, most algorithms are linear-to-quadratic on Python lists/dicts; acceptable for small-to-medium graphs but may degrade with large infrastructures. Testing covers core modules but has gaps for critical error paths, multi-cloud abstraction, provider-agnostic rendering, and performance edge cases.

## Critical Issues (blocking Azure/GCP support)

### 1) Hard-coded AWS-centric configuration and imports
- **Files**: modules/cloud_config.py (entire file), modules/drawing.py (lines 21–47, 52–63, 84–94), modules/graphmaker.py (lines 18–29), modules/helpers.py (lines 22–30), modules/resource_handlers.py (lines 14–22, 223), terravision.py (implicit through compile_tfdata flow).
- **Severity**: Critical
- **Description**: The system relies entirely on AWS_* constants for draw order, node variants, annotations, reverse arrows, shared services, disconnect lists, and resource handlers. Drawing imports specific AWS resource classes via wildcard imports; no provider abstraction exists.
- **Impact**: Prevents introducing Azure/GCP without pervasive refactors. Any new provider would require duplicating large parts of drawing/graph logic and configs.
- **Recommendation**:
  - Introduce a ProviderRegistry abstraction with interfaces:
    - ProviderConfig: consolidated nodes, group nodes, draw order, variants, reverse arrows, shared services, auto annotations, edge rules.
    - ProviderRenderer: resource class lookup, group canvas creation, edge creation rules.
    - ResourceHandlers: per-provider handler functions discovered via registry.
  - Refactor modules to depend on ProviderConfig interfaces rather than AWS constants:
    - Replace direct imports with provider = registry.get(current_provider); use provider.config.*
    - Load provider from CLI option (--provider=aws|azure|gcp) default aws.
  - Example (drawing.py):
    - Before: `OUTER_NODES = cloud_config.AWS_OUTER_NODES`
    - After: `provider = registry.get(provider_name); OUTER_NODES = provider.config.OUTER_NODES`
- **Priority for Azure/GCP extension**: Blocks extension entirely until abstracted.

### 2) Drawing module's wildcard imports and tight coupling to AWS resource classes
- **File**: modules/drawing.py lines 19–47, 50, 84–87
- **Severity**: Critical
- **Description**: Imports all AWS packages via `from resource_classes.aws.* import *`; relies on AWSgroup class and class name matching for resource types.
- **Impact**: Prevents provider-agnostic behavior; causes namespace bloat/collisions; increases maintenance burden and test complexity.
- **Recommendation**:
  - Replace wildcard imports with dynamic class resolution via a ProviderRenderer or ResourceClassFactory that maps resource_type -> class.
  - Use a minimal shared interface for Node, Cluster, Canvas, Edge objects (provider-agnostic).
  - Encapsulate AWSgroup in provider renderer; drawing should call provider_renderer.create_cloud_group().
- **Priority for Azure/GCP extension**: High blocker.

### 3) Cloud configuration constants are provider-specific with no extension points
- **File**: modules/cloud_config.py (entire file content is AWS-specific)
- **Severity**: Critical
- **Description**: All config is AWS_*; no Azure/GCP equivalents or schema to plug in.
- **Impact**: No path to multi-cloud without duplicating or branching logic per provider across modules.
- **Recommendation**:
  - Define a provider-neutral schema (dataclasses or TypedDict) for config parameters and load provider-specific YAML/JSON files at runtime (e.g., configs/providers/aws.yaml, azure.yaml, gcp.yaml).
  - Implement a ConfigLoader with validation and caching.
- **Priority for Azure/GCP extension**: High blocker.

## High Priority Issues

### 1) Incorrect list operation in annotations.modify_nodes
- **File**: modules/annotations.py lines 165–166
- **Severity**: High
- **Description**: Uses `graphdict[startnode].delete(connection)` on a Python list which has no delete method.
- **Impact**: Raises AttributeError and fails user-defined disconnect operations.
- **Recommendation**:
  - Replace with safe removal:
    ```python
    if connection in graphdict[startnode]:
        graphdict[startnode].remove(connection)
    ```
  - Add defensive checks for missing keys and wildcard resolution.
- **Priority for Azure/GCP extension**: Medium (functional correctness across providers).

### 2) Potential mutation while iterating in annotations.add_annotations forward-delete loop
- **File**: modules/annotations.py lines 64–71
- **Severity**: High
- **Description**: Iterating graphdict[node] and removing elements from the same list inside the loop.
- **Impact**: May skip elements or raise during iteration; non-deterministic annotation results.
- **Recommendation**:
  - Iterate over a copy: `for conn in list(graphdict[node]): ...`
  - Or build a filtered list comprehensively.
- **Priority for Azure/GCP extension**: Medium.

### 3) Unhandled None returns in drawing.handle_nodes/handle_group
- **File**: modules/drawing.py lines 151–156 (return when resource_type not in avl_classes), later code assumes returned Node/Cluster exists.
- **Severity**: High
- **Description**: Functions may return None; callers proceed to use attributes (e.g., connectedNode._id) causing AttributeError.
- **Impact**: Runtime failures when encountering unknown resource types (likely in Azure/GCP).
- **Recommendation**:
  - Enforce explicit Optional[Node] return typing and guard at call sites; return a tuple (Optional[Node], drawn_resources). Validate before use.
- **Priority for Azure/GCP extension**: High (robustness across providers).

### 4) Graphmaker.reverse_relations incorrect key usage
- **File**: modules/graphmaker.py lines 67–70
- **Severity**: High
- **Description**: Removing from tfdata["graphdict"][node] where node is set to helpers.get_no_module_name(n), but keys in graphdict are the original names; removing may fail or corrupt structure.
- **Impact**: Relation reversal may not work or can KeyError; diagram correctness impacted.
- **Recommendation**:
  - Use consistent variable names; when removing c from n's connections use `tfdata["graphdict"][n].remove(c)` (not "[node]"), and ensure n key exists – don't strip module names for dictionary keys.
  - Add unit tests for reverse_relations with module-prefixed nodes.
- **Priority for Azure/GCP extension**: Medium.

### 5) tfwrapper.tf_makegraph: provider check is AWS-only
- **File**: modules/tfwrapper.py lines 451–459
- **Severity**: High
- **Description**: Verifies presence of 'aws_' only; errors if none present even if Azure/GCP intended.
- **Impact**: Blocks multi-cloud usage; premature exit for non-AWS graphs.
- **Recommendation**:
  - Replace with generic check for any known provider prefixes discovered from ProviderRegistry; or accept non-cloud resources.
- **Priority for Azure/GCP extension**: High blocker.

### 6) Unsafe os.system call and temporary file management in drawing.render_diagram
- **File**: modules/drawing.py lines 523–534
- **Severity**: High (Security/Robustness)
- **Description**: Uses os.system to run gvpr without validation and constructs paths unsafely; removes files blindly.
- **Impact**: Command injection risk if paths are not sanitized; brittle on different OS; no error handling for gvpr failure; possible file-not-found on cleanup.
- **Recommendation**:
  - Replace os.system with subprocess.run([...], check=True) and proper quoting; verify files exist before deletion; handle exceptions.
- **Priority for Azure/GCP extension**: Low (security hygiene).

## Medium Priority Issues

### 1) Excessive wildcard imports, circular dependencies
- **Files**: modules/drawing.py, modules/gitlibs.py (`from modules.helpers import *`), resource_classes packages
- **Severity**: Medium
- **Description**: Wildcard imports complicate static analysis, testing, and maintainability.
- **Impact**: Namespace collisions; harder type checking; fragile when adding providers.
- **Recommendation**:
  - Replace wildcard with explicit imports; or dynamic resolution through a registry.
- **Priority for Azure/GCP extension**: Medium.

### 2) Error handling via print/click.echo + sys.exit scattered
- **Files**: terravision.py (multiple), modules/fileparser.py (lines 115–117), modules/helpers.py (replace_variables lines 503–513), interpreter.py (replace_local_values lines 245–248, replace_var_values lines 443–448), tfwrapper.py (many exits)
- **Severity**: Medium
- **Description**: Many functions perform sys.exit, mixing CLI and library layers, making it hard to reuse programmatically and to test.
- **Impact**: Poor separation of concerns; untestable branches; brittle control flow.
- **Recommendation**:
  - Raise custom exceptions (e.g., TerraVisionError, ProviderConfigError) at library level; handle in CLI to present user-friendly messages.
- **Priority for Azure/GCP extension**: Medium.

### 3) Type hints incomplete/inaccurate; Optional handling gaps
- **Files**: modules/helpers.py (numerous functions returning Optional[str] but return None implicitly), drawing, graphmaker (Generator types ok but many Any)
- **Severity**: Medium
- **Description**: Functions like get_no_module_name can return None; callers assume str.
- **Impact**: Hidden bugs; static analysis ineffective; increased runtime errors.
- **Recommendation**:
  - Add precise typing, enforce non-None returns or check at call sites; enable mypy in CI with strict mode.
- **Priority for Azure/GCP extension**: Medium.

### 4) Data mutation while iterating dictionaries/lists
- **Files**: modules/graphmaker.py (consolidate_nodes loops and deletes while iterating, lines 302–359), resource_handlers methods similar patterns.
- **Severity**: Medium
- **Description**: Modifying dict/list during iteration leads to skipped elements or inconsistent state.
- **Impact**: Non-deterministic graph building; rendering inconsistencies.
- **Recommendation**:
  - Iterate over list(dict(...)) or copy before mutating; add unit tests for these flows.
- **Priority for Azure/GCP extension**: Low.

### 5) Potential KeyError in drawing.get_edge_labels when metadata missing
- **File**: modules/drawing.py lines 99–110
- **Severity**: Medium
- **Description**: Access tfdata["meta_data"][origin_resource] without guarding for existence.
- **Impact**: Crash on missing metadata.
- **Recommendation**:
  - Use `tfdata["meta_data"].get(origin_resource, {})` and guard for None.
- **Priority for Azure/GCP extension**: Medium.

### 6) Inconsistent suffix handling and "~" semantics across modules
- **Files**: modules/graphmaker.py, resource_handlers.py, helpers.py
- **Severity**: Medium
- **Description**: Multiple implementations for numbered resources; not centralized; edge cases around for_each vs count vs desired_count.
- **Impact**: Hard to maintain; bugs in complex graphs.
- **Recommendation**:
  - Centralize suffix logic in a ResourceInstanceManager utility with clear API; unify counting across modules.
- **Priority for Azure/GCP extension**: Medium.

## Low Priority Issues

### 1) Minor naming/style issues (PEP8, imports order, duplicate strings)
- **Files**: multiple; e.g., helpers.py duplicate comments lines 894–896
- **Severity**: Low
- **Impact**: Style consistency and readability.
- **Recommendation**:
  - Run black/isort/mypy; enforce pre-commit hooks in CI.
- **Priority for Azure/GCP extension**: Low.

### 2) Dead code and commented alt implementations
- **File**: modules/graphmaker.py lines 495–546 (commented alternate needs_multiple)
- **Severity**: Low
- **Impact**: Confusion; maintenance overhead.
- **Recommendation**:
  - Remove or document rationale; keep single source of truth.
- **Priority for Azure/GCP extension**: Low.

### 3) Redundant conversions and inefficient patterns
- **Files**: many places convert lists/dicts repeatedly (e.g., `list(dict(...))`)
- **Severity**: Low
- **Impact**: Minor performance hit; noise.
- **Recommendation**:
  - Optimize conversions; avoid creating new lists unless required.
- **Priority for Azure/GCP extension**: Low.

## Refactoring Recommendations for Multi-Provider Support

### 1) Introduce Provider Abstraction Layer
- Create interfaces:
  - **ProviderConfig** (dataclass): consolidated_nodes, group_nodes, draw_order, node_variants, reverse_arrow_list, shared_services, auto_annotations, edge_visibility_rules, disconnect_list, implied_connections.
  - **ProviderRenderer**: methods create_cloud_group(), resolve_class(resource_type), edge_visibility(origin, dest, tfdata), ok_to_connect(...)
  - **ProviderResourceHandlers**: mapping from resource prefixes to handler functions (pre/post graph).
- Implement a ProviderRegistry with registration/lookup:
  - `registry.register('aws', AwsProviderConfig, AwsRenderer, AwsHandlers)`
  - `registry.register('azure', AzureProviderConfig, AzureRenderer, AzureHandlers)`
  - `registry.register('gcp', GcpProviderConfig, GcpRenderer, GcpHandlers)`
- CLI addition: --provider with default aws; propagate through compile_tfdata and into modules.

### 2) Decouple Drawing from Provider-Specific Classes
- Replace wildcard imports with factory lookups.
- Drawing should operate on abstract Node/Cluster/Canvas interfaces; provider renderer implements class construction.

### 3) Move Config to External YAML/JSON
- Create configs/providers/aws.yaml, azure.yaml, gcp.yaml describing draw rules and mappings.
- Loader validates and caches; enables updating configs without code changes.

### 4) Centralize Graph Operations
- Implement GraphService with well-defined operations:
  - add_relation(origin, dest), reverse_relation(...), consolidate_nodes(...), apply_variants(...), create_multiples(...).
- Allows provider-specific plug-ins to extend behavior.

### 5) Error Handling and Exceptions
- Define TerraVisionError hierarchy:
  - DependencyError, TerraformError, ParsingError, ProviderError, ConfigurationError, VariableResolutionError
- Library functions raise; CLI catches and formats output.

### 6) Testing Refactor
- Add unit tests per provider abstraction:
  - ProviderRegistry: registration, retrieval.
  - Drawing: class resolution and fallback behavior.
  - Graphmaker: consolidation and reversal with module-prefixed names.
- Integration tests for Azure/GCP sample graphs.

## Testing Recommendations

### Increase coverage on:
- **annotations.modify_nodes/modify_metadata**: add tests for wildcard add/connect/disconnect/remove (including the current bug on delete).
- **tfwrapper**: error paths for terraform init/plan/graph conversions; simulate failures via mocking.
- **interpreter**: variable resolution fixpoint convergence; module outputs; data/local replacements.
- **resource_handlers**: autoscaling, cloudfront, security group handlers with representative HCL metadata; avoid literal_eval with safe parsing.
- **drawing**: guard Optional returns; edge deduplication; post-processing pipeline with gvpr.
- **Multi-cloud tests**: build minimal Azure and GCP configs and resource_class stubs; verify render pipeline works with provider=azure/gcp.

### Performance tests:
- Large graph (1k+ nodes) to measure time for add_relations, consolidate_nodes, create_multiple_resources; optimize hot paths.

### Slow tests marker:
- Keep `-m "not slow"` default; create targeted slow tests for graph operations.

## Code Quality Metrics (current qualitative assessment)
- **Type hint coverage**: moderate; many Any and Optional not enforced.
- **Cyclomatic complexity**: high in graphmaker/resource_handlers functions (multi-branch nested loops).
- **Duplication**: moderate (duplicate add_multiples_to_parents; scattered suffix logic).
- **Test coverage**: partial for core modules; missing for CLI and error handling; missing for provider abstraction.
- **Security hygiene**: moderate; os.system usage; literal_eval; bare excepts.

## Actionable Tasks Backlog

### P0 (Blockers for Azure/GCP):
- Implement ProviderRegistry and ProviderConfig interfaces; refactor modules to consume provider config (owner: platform; estimate: 3–4 days).
- Refactor drawing.py to remove wildcard imports; integrate ProviderRenderer (owner: platform; 2 days).
- Extract AWS config from cloud_config.py to configs/providers/aws.yaml; add loader and schema validation (owner: platform; 1–2 days).
- Update tfwrapper provider checks to be provider-agnostic (owner: platform; 0.5 day).

### P1 (Correctness/Robustness):
- Fix annotations.modify_nodes disconnect bug (owner: core; 0.25 day).
- Guard Optional returns in drawing.handle_nodes/group and dedupe edges via sets (owner: core; 1 day).
- Correct graphmaker.reverse_relations key usage and add tests (owner: core; 1 day).
- Replace os.system in drawing.render_diagram with subprocess.run and safe cleanup (owner: core; 0.5 day).
- Replace literal_eval in resource_handlers with safe parsing and type guards (owner: core; 1 day).

### P2 (Maintainability/Performance):
- Centralize multiple-instance logic; remove duplicate functions (owner: core; 1 day).
- Introduce TerraformRunner utility for standardized subprocess handling (owner: platform; 1 day).
- Transition ipaddr -> ipaddress with guards (owner: core; 0.5 day).
- Migrate library-level exit() into exceptions; update CLI handling (owner: platform; 1.5 days).
- Enforce typing with mypy and fix Optionals (owner: platform; 1 day).

## Conclusion
TerraVision achieves AWS-focused diagram generation but requires architectural refactoring for multi-cloud support, improved error handling, and several correctness fixes. By introducing provider abstractions, centralizing graph logic, and enforcing robust typing and exceptions, the codebase can become maintainable, secure, and extensible to Azure and GCP.
