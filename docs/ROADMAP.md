# TerraVision Multi-Cloud Product Roadmap

## Executive Summary

TerraVision's vision is to become the definitive "Terraform-to-Architecture" generator for heterogeneous infrastructure stacks (AWS, Azure, GCP, on‑prem, and emerging providers) operating as a reliable, extensible, CI/CD-friendly developer tool. Moving from an AWS-only alpha (v0.8) to a multi-cloud baseline (v1.0+) requires decoupling provider-specific logic, fixing correctness blockers, and instituting a durable provider framework that lowers cost of adding new ecosystems.

### Strategic Objectives
1. Deliver first-class Azure and GCP support without regressing existing AWS users.
2. Establish a Provider Abstraction Layer enabling future providers (Kubernetes, Cloudflare, Datadog, etc.) with minimal code churn.
3. Improve robustness and maintainability by addressing critical/high issues in code review (e.g., provider coupling, incorrect list operations, unsafe executions).
4. Increase user trust through better error handling (exceptions over sys.exit) and test coverage (including multi-provider cases).
5. Provide a migration and deprecation path from direct AWS constants (0.8) to provider-config-driven architecture (≥0.9).
6. Introduce measurable KPIs around adoption, quality, performance, and community engagement.

### Key Milestones Overview
- **v0.9** (Foundation Release / Azure & GCP Alpha): ProviderRegistry + ProviderContext, extraction of AWS constants, minimal Azure/GCP resource set, correctness blockers resolved.
- **v1.0** (Multi-Cloud Beta / General Availability for Core Clouds): Stable Azure & GCP with core networking, compute, storage, security, and load balancing semantics; deprecations enforced; improved test suite & error model.
- **v1.1** (Provider Framework Expansion / Performance & Extensibility): Introduce plugin-style ProviderDescriptor model for third-party providers (Kubernetes priority), performance optimization for large graphs (≥1k nodes).
- **v1.2** (Ecosystem Growth / Advanced Mapping & Observability): Add 2–3 additional providers (Cloudflare, Datadog, Vault), enhance service mapping & canonical categorization, diagram annotation enhancements across providers.

---

## Release Plan

### Capacity & Planning Assumptions
- Sprint length: 2 weeks.
- Engineering allocation (illustrative): 2 Core engineers + 1 Platform engineer.
- Velocity assumption: ~40–45 story points per sprint (aggregate).
- Buffer: 20% reserved for unplanned issues (defects, integration friction).

---

### Release 0.9 (Target 4–5 weeks / 2–3 sprints)
**Version:** 0.9.0  
**Theme:** Multi-Cloud Foundation & Critical Decoupling

**Features (User-Facing):**
- CLI gains `--provider` flag (default aws).
- Alpha Azure & GCP basic diagram generation (compute + network + storage + security minimal set).
- Export graphdata works cross-provider.

**Technical Work:**
- Implement ProviderRegistry & ProviderContext (CODEREVIEW.md P0 blockers, ARCHITECTURAL.md Provider Abstraction Layer).
- Refactor cloud_config into `modules/cloud_config/{aws,azure,gcp,common}.py`.
- Introduce `service_mapping.py` for provider detection and canonical categorization.
- Refactor drawing to dynamic class resolution (remove wildcard AWS imports).
- Tfwrapper provider-agnostic check (currently AWS-only validation).

**Bug Fixes (Critical/High):**
- Fix annotations.modify_nodes list deletion bug (line 165: `list.delete()` → `list.remove()`).
- Guard Optional returns in drawing.handle_nodes/group (prevent AttributeError on None).
- Reverse_relations key usage fix (use original node names, not stripped).
- Ensure provider_id in meta_data for each node.

**Success Metrics (Exit Criteria):**
- Azure & GCP sample Terraform projects render successfully (≥5 canonical resources each).
- 0.9 test coverage ≥ +15% over baseline for new provider code paths.
- AWS diagram parity (no >5% regression in existing test expectations).
- All P0 blocker issues resolved.

**Migration Notes:**
- Direct AWS_* imports deprecated—warn in logs when detected.
- Existing AWS-only flows unchanged; provider default remains AWS.

**Dependencies:**
- ProviderContext before refactoring graphmaker/drawing.
- Config extraction before handler dispatch modifications.

**Risks:**
- Hidden coupling in helpers.py may delay abstraction.
- Insufficient icon mapping may degrade early Azure/GCP user perception.
- Time overrun if test fixture creation is underestimated.

**Risk Mitigation:**
- Parallelize icon stub creation & config loading in Sprint 1.
- Add generic fallback icons (resource_classes/generic) early.
- Add feature flag for provider=azure,gcp to avoid impacting AWS stability.

**Rollback Plan:**
- If Azure/GCP instability detected, retain provider flag undocumented (soft launch) and ship foundation only.

---

### Release 1.0 (Target 6–8 weeks post 0.9 / 3–4 sprints)
**Version:** 1.0.0  
**Theme:** Multi-Cloud GA (Azure & GCP Core)

**Features:**
- Expanded Azure: Application Gateway, FrontDoor/CDN, Key Vault, SQL/Postgres/Maria DB.
- Expanded GCP: Backend services consolidation, firewall semantics, SQL Database, DNS zones.
- Stable provider-aware annotations (AUTO_ANNOTATIONS per provider).
- Canonical category labeling (compute/network/storage/security/database/management) surfaced in exported JSON.

**Technical Work:**
- ResourceHandlers split into provider packages (resource_handlers/{aws,azure,gcp}.py).
- Interpreter generalized resource extraction regex (support all provider prefixes).
- Exception hierarchy (TerraVisionError, ProviderError, etc.) replacing sys.exit.
- Deduplicate variant logic & consolidated nodes behind provider APIs.
- Mypy strict mode integration.

**Bug Fixes / Debt:**
- Unsafe os.system replacement with subprocess.run (security/robustness).
- Mutation while iterating in annotations.add_annotations (use list copy).
- KeyError guard in drawing.get_edge_labels (use .get()).
- Centralize suffix/multiple-instance logic.

**Success Metrics:**
- ≥30% of new downloads invoke `--provider azure` or `--provider gcp` within 60 days of release.
- Test coverage: +25% vs 0.8 baseline; multi-provider integration tests passing.
- Diagram generation time for 500-node mixed provider project ≤ 15s on reference hardware.
- Crash rate (unhandled exceptions) <1% of runs (instrument via optional telemetry flag).

**Migration Notes:**
- Remove deprecated direct AWS constant imports; provide adapter shim until 1.1 with deprecation banner.
- Document annotation syntax differences where resource naming diverges.

**Dependencies:**
- 0.9 foundation stable, config modules validated.

**Risks:**
- Complexity in multi-provider special handlers concurrency.
- Increased maintenance cost if error handling refactor introduces regressions.
- Insufficient test data for complex Azure/GCP load balancer topologies.

**Mitigation:**
- Add synthetic Terraform examples for edge cases pre-release.
- Staged beta (public pre-release tag 1.0.0-rc1) for 2 weeks.

---

### Release 1.1 (Target 6 weeks post 1.0 / 3 sprints)
**Version:** 1.1.0  
**Theme:** Provider Framework & Performance Optimization

**Features:**
- ProviderDescriptor & plugin registration system.
- Kubernetes provider (kubernetes_* minimal set) + generic cluster icon mapping.
- Performance enhancements: graph operations refactored (GraphService abstraction).
- Configurable service mapping overrides (user-supplied mapping file).

**Technical Work:**
- GraphService centralization for consolidate_nodes, reverse_relations, multiples creation.
- TerraformRunner utility replacing scattered subprocess patterns.
- Memory footprint profiling & caching of provider configs.

**Bug Fixes / Debt:**
- Replace literal_eval usages (security concern).
- Eliminate wildcard imports globally.
- Complete transition from sys.exit to exceptions.

**Success Metrics:**
- Kubernetes diagrams stable: cluster + deployments + services + config maps sample.
- Large graph (1k+ nodes) generation time improved by ≥25% vs 1.0 benchmark.
- CPU utilization peak reduced or stable (<80% single core during graph build for 1k nodes).
- Plugin development guide published; ≥2 external PRs adding provider descriptors within 60 days.

**Migration Notes:**
- Full removal of legacy AWS-only branches; configuration lives solely in provider modules/YAML.
- Users may opt into experimental providers via `--provider list` output.

**Risks:**
- Plugin security concerns (arbitrary code through handler modules).
- Performance regressions from abstraction layering.

**Mitigation:**
- Sandboxed dynamic import with explicit allowlist.
- Benchmark suite integrated into CI gating merges.

---

### Release 1.2 (Target 6–8 weeks post 1.1 / 3–4 sprints)
**Version:** 1.2.0  
**Theme:** Ecosystem Expansion & Advanced Mapping

**Features:**
- Add 2–3 providers: Cloudflare (dns/security), Datadog (observability), Vault (secrets).
- Enhanced cross-provider canonical aggregation dashboards (service usage summary JSON).
- Advanced annotation expansion: cross-provider relationship hints (e.g., DNS → CDN → origin chain).
- Diagram layout improvements: category-based clustering across providers.

**Technical Work:**
- Extend canonical_category taxonomy.
- Implement provider-level implied connection DSL (extensible config).
- Add "mixed graph" correctness checks.

**Bug Fixes / Debt:**
- Clean dead/commented code.
- Optimize redundant conversions.
- Style & naming polish.

**Success Metrics:**
- Mixed provider adoption: ≥10% of diagrams contain ≥2 provider families.
- Support issues related to multi-provider <10% of total opened issues.
- Community contributions: ≥5 provider-related PRs merged.

**Migration Notes:**
- Introduce optional telemetry (opt-in) for anonymized provider adoption metrics.

**Risks:**
- Icon coverage gaps for new providers.
- Increasing configuration complexity reduces maintainability.

**Mitigation:**
- Provide automated icon fallback logic & validation script.
- Configuration schema lint tool integrated into pre-commit.

---

## Detailed Feature Breakdown

### Feature: Provider Abstraction Layer
**User Stories:**
- As a user, I want to generate diagrams for Azure and GCP without changing my existing AWS workflow so that I can adopt multi-cloud gradually.
- As a contributor, I want a documented provider registration interface so that I can add new providers without modifying core modules.

**Acceptance Criteria:**
- No direct AWS_* imports remain in graphmaker, helpers, drawing.
- ProviderContext supplies config and handler dispatch; all nodes tagged with provider_id.

**Technical Requirements:**
- Implement ProviderDescriptor & ProviderContext (ARCHITECTURAL.md lines 299–307, 428–469).
- Refactor tfwrapper detection (CODEREVIEW.md lines 93–99).

**Effort Estimate:** L (Large) ~ 20 points  
**Priority:** P0

---

### Feature: Azure Support (Phase 1)
**User Stories:**
- As an Azure-focused engineer, I want vnet/subnet, VM, NSG, LB resources diagrammed so that I can visualize core infrastructure topology.

**Acceptance Criteria:**
- Resources mapped per Phase 1 list (ARCHITECTURAL.md Azure Service Mappings).
- NSG relationships visible; LB consolidated variant icon appears.

**Technical Requirements:**
- azure.py config; azure handlers (ARCHITECTURAL.md Azure-specific Resource Handlers).
- Resource images azure/.

**Effort Estimate:** M (~12 points)  
**Priority:** P0

---

### Feature: GCP Support (Phase 1)
**User Stories:**
- As a GCP engineer, I want network/subnetwork, instances, firewall, and load balancing visualized so that I can understand dependencies.

**Acceptance Criteria:**
- Handlers for network_subnets, firewall, LB consolidation (ARCHITECTURAL.md GCP-specific Resource Handlers).

**Technical Requirements:**
- gcp.py config; gcp handlers, icon set.

**Effort Estimate:** M (~12 points)  
**Priority:** P0

---

### Feature: Provider Framework (Phase 2 / Plugin System)
**User Stories:**
- As an integrator, I want to add third-party providers (Cloudflare, Datadog) via descriptor + handler modules without changing core code.

**Acceptance Criteria:**
- ProviderDescriptor registration & dynamic import; mixed provider graph supported.

**Technical Requirements:**
- providers/ package; descriptor schema (ARCHITECTURAL.md Phase 2 - Generic Provider Framework).

**Effort Estimate:** L (~18 points)  
**Priority:** P1 (after GA stabilization)

---

### Feature: Kubernetes Provider (1.1)
**User Stories:**
- As a platform engineer, I want Kubernetes resources (cluster, deployments, services) rendered so that I can combine cloud + cluster view.

**Acceptance Criteria:**
- Basic K8s resource prefix mapping; cluster grouping; fallback icons if specialized missing.

**Effort Estimate:** M (~10 points)  
**Priority:** P1

---

### Feature: Performance Optimization
**User Stories:**
- As a user with large Terraform, I want diagrams generated in under 20s for 1000+ resources so that I can use TerraVision in CI.

**Acceptance Criteria:**
- Profiling identifies top 3 hotspots; ≥25% improvement.

**Technical Requirements:**
- GraphService centralization and iteration safety (CODEREVIEW.md refactoring recommendations).

**Effort Estimate:** M (~8 points)  
**Priority:** P2 (after stability)

---

## Technical Debt & Bug Fix Schedule

| Issue | Lines (CODEREVIEW.md) | Severity | Scheduled Release | Rationale |
|-------|-----------------------|----------|-------------------|-----------|
| Hard-coded AWS config | Critical Issues #1 | Critical | 0.9 | Blocks multi-cloud |
| Wildcard imports drawing | Critical Issues #2 | Critical | 0.9 | Must generalize renderer |
| tfwrapper provider check | High Priority #5 | High | 0.9 | Prevents Azure/GCP detection |
| modify_nodes delete bug | High Priority #1 | High | 0.9 | Correctness across providers |
| Optional returns drawing | High Priority #3 | High | 0.9 | Avoid None attribute errors |
| reverse_relations key bug | High Priority #4 | High | 0.9 | Relation integrity |
| annotations mutation loop | High Priority #2 | High | 1.0 | Stability improvement after foundation |
| unsafe os.system | High Priority #6 | High (security) | 1.0 | Introduce subprocess + error handling |
| wildcard imports (other) | Medium Priority #1 | Medium | 1.1 | After core abstraction stable |
| sys.exit scattered | Medium Priority #2 | Medium | 1.0–1.1 phased | Avoid regressions during 0.9 |
| typing gaps / mypy | Medium Priority #3 | Medium | 1.0 | Improve reliability |
| suffix logic centralization | Medium Priority #6 | Medium | 1.0–1.1 | Shared across providers |
| literal_eval replacement | P1 Task (Correctness) | Medium | 1.1 | Security/perf not blocking early GA |
| dead code removal | Low Priority #2 | Low | 1.2 | Defer—no functional impact |
| redundant conversions | Low Priority #3 | Low | 1.2 | Perf micro-optimization |

**Justification:** P0/P1 issues that block or destabilize provider abstraction are front-loaded into 0.9; secondary robustness and security issues follow once foundational architecture is confirmed stable.

---

## Backwards Compatibility & Migration Strategy

1. **0.8 → 0.9:**
   - Maintain AWS behavior; new provider code behind ProviderContext.
   - Log warnings when direct AWS_* imports detected in downstream (extension) code.

2. **0.9 → 1.0:**
   - Deprecate direct imports entirely; publish migration guide describing new config access patterns (provider_ctx.get_config(provider_id)).
   - Introduce exception hierarchy; replace sys.exit in core logic—CLI layer intercepts.

3. **1.0 → 1.1:**
   - Remove deprecated shim; enforce plugin descriptor usage.
   - Introduce optional telemetry flag to gather adoption metrics (opt-in).

4. **Annotation Migration:**
   - Document resource prefix differences; provide mapping table (aws_* vs azurerm_* vs google_*).

5. **Breaking Change Policy:**
   - Any field removal from tfdata requires: (a) migration note, (b) minor version bump if non-breaking, major (1.x increment) if breaking.

6. **Rollback Strategy:**
   - Feature flags per provider (internal boolean): if instability detected, disable provider-specific handlers while leaving core recognition intact.

**Deprecation Timeline:**
- Direct AWS constants usage: Warn at 0.9, error at 1.0, removed at 1.1.
- sys.exit usage for library functions: partially replaced at 1.0, fully removed at 1.1.

---

## Success Metrics & KPIs

| Category | KPI | Target |
|----------|-----|--------|
| Adoption | % diagrams using non-AWS provider | 30% by 1.0 + 45% by 1.2 |
| Quality | Test coverage (lines) | +25% vs 0.8 by 1.0; ≥70% total by 1.2 |
| Stability | Crash/unhandled exception rate | <1% by 1.0 |
| Performance | 500-node diagram time | ≤15s by 1.0; ≤10s by 1.1 |
| Performance | 1k-node diagram time | Baseline –25% by 1.1 |
| Security | High severity open issues | 0 outstanding by end of 1.0 |
| Community | Provider-related PRs merged | ≥5 by 1.2 |
| Extensibility | Avg time to add new provider (internal prototype) | ≤3 days by 1.1 |
| Reliability | Re-run determinism (same input = same graph) | 100% deterministic in tests by 1.0 |
| Docs | Provider framework guide completion | Published by 1.1 |
| User Value | Annotation usage in multi-cloud diagrams | ≥20% of multi-cloud runs by 1.2 (opt-in telemetry) |

---

## Risk Register

| Risk | Type | Description | Impact | Probability | Mitigation | Owner |
|------|------|-------------|--------|-------------|------------|-------|
| Hidden AWS coupling surfaces late | Technical | Residual AWS constants missed | Medium | High | Incremental scan & mypy strict mode | Platform |
| Azure/GCP icon gaps reduce UX | Product | Incomplete visual fidelity | Medium | Medium | Fallback generic icons + icon completeness checklist | Core |
| Performance degradation from abstraction | Technical | Added indirection slows large graphs | High | Medium | Early profiling in 0.9, caching configs | Platform |
| Plugin security (arbitrary code) | Security | Malicious handler injection | High | Low | Signed provider registry + allowlist + docs | Platform |
| Test fixture insufficiency | Quality | Poor edge-case coverage multi-cloud | Medium | High | Allocate dedicated sprint capacity; community examples | QA |
| Timeline slip due to refactor scope creep | Delivery | Over-expansion of initial abstraction | High | Medium | Strict scope gate: only core data paths in 0.9 | PM |
| Backward compatibility regression AWS | Product | Existing users blocked | High | Low | Regression test suite vs 0.8 snapshots | Core |
| Community confusion on provider naming | Adoption | Misuse of prefixes & annotations | Medium | Medium | Provide prefix matrix & annotation examples | Docs |
| Diagram layout inconsistency multi-cloud | UX | Mixed clusters appear disorganized | Medium | Medium | Canonical categories + draw_order per provider early | Core |
| Large Terraform plan parse failures new providers | Technical | Unhandled resource semantics | Medium | Medium | Graceful fallback to generic nodes | Core |

---

## Open Questions & Decisions Needed

1. **Telemetry Strategy:** What minimal opt-in fields (e.g., provider counts, node volume) are acceptable for measuring adoption while respecting privacy?
2. **Fallback Behavior:** Should unknown provider resources always map to generic nodes or attempt heuristic categorization?
3. **Plugin Distribution:** Will we allow external pip installable provider packs or require monorepo contributions only?
4. **Security Review:** Is a formal review required before enabling dynamic imports for plugin providers?
5. **Performance Baseline Definition:** Reference hardware configuration standard (CPU/memory) for timing KPIs.
6. **Kubernetes Scope:** How deep to model (Ingress, StatefulSets, ConfigMaps) in first iteration?
7. **Annotation Cross-Provider Enrichment:** Should we auto-suggest cross-provider edges (e.g., Cloudflare DNS → AWS ALB) or keep strictly user-defined?
8. **Versioning Scheme Post 1.0:** Stick to semantic minor increments (1.1, 1.2) for provider additions vs separate provider package versions?
9. **Service Mapping Extensibility:** YAML override vs Python plugin pattern—priority for enterprise customization?
10. **Mixed Graph Layout:** Single unified layout ordering vs per-provider grouped clusters—need design input.

**Items needing stakeholder decision in next planning meeting:** 1, 3, 7, 9.

---

## Rationale for Sequencing

- **0.9** focuses on "foundational enablers" (ProviderContext, config externalization, critical correctness fixes) because all future value (multi-cloud, plugins, performance improvements) depends on clean separation from AWS coupling.
- **1.0** targets GA-level reliability and core provider completeness to establish credibility before broadening scope.
- **1.1** emphasizes extensibility (plugins) and performance—timely once feature baseline is stable and usage patterns can inform optimization.
- **1.2** invests in ecosystem growth and advanced semantics to solidify market differentiation.

This sequence aligns short-term functional user value (Azure/GCP) with long-term architectural durability (plugin framework) while actively reducing technical debt that would otherwise inflate total cost of ownership.

---

## Work Breakdown Example (Initial Sprints 0.9)

### Sprint 1 (Foundation)
- ProviderDescriptor + ProviderContext (8 pts)
- Extract AWS config → aws.py (4 pts)
- Service mapping minimal (3 pts)
- Tfwrapper provider detection refactor (2 pts)
- Fix annotations.modify_nodes bug (2 pts)
- Set up test scaffolding for provider fixtures (4 pts)

### Sprint 2 (Azure/GCP Alpha + Robustness)
- Azure config + handlers + icons (6 pts)
- GCP config + handlers + icons (6 pts)
- Drawing refactor (6 pts)
- Reverse_relations fix + tests (3 pts)
- Optional return guards (3 pts)
- Basic multi-provider integration tests (4 pts)

**Buffer / Spillover:** 5 pts.

---

## Initial User Story Catalog (Representative)

1. As a Terraform engineer, I want to specify `--provider azure` so that my Azure resources produce a diagram automatically.
2. As a multi-cloud architect, I want a single diagram including AWS and GCP resources so that I can visualize cross-cloud dependencies.
3. As a contributor, I want a documented ProviderDescriptor so that I can add Cloudflare support without editing core.
4. As a security engineer, I want the tool to avoid unsafe shell execution so that CI usage is hardened.
5. As an ops engineer, I want large graphs to render faster so that pipelines stay within SLA thresholds.
6. As a power user, I want canonical categories in the JSON export so that I can post-process diagrams for reporting.
7. As a reviewer, I want deterministic outputs for the same Terraform code so that diffs represent real infrastructure changes.

---

## Acceptance Criteria Aggregated (Cross-Release)

- Provider-agnostic graphmaker functions receive provider_ctx and never reference AWS_* directly.
- All special resource handling is routed via provider-specific handlers through registry dispatch.
- Annotations engine loads AUTO_ANNOTATIONS from the active provider config.
- Node meta_data includes provider and category fields for every recognized resource.
- Subprocess calls are exception-backed and free of os.system vulnerability patterns.
- Mypy strict passes in CI with zero new warnings at 1.0.
- Resource image lookup falls back gracefully (no crash) for missing provider icons.
- Performance benchmarks published (README + docs) starting 1.1.
- Plugin developer guide present by 1.1.

---

## Documentation & Communication Plan

- **0.9 Blog/Release Notes:** "TerraVision Multi-Cloud Foundation (Alpha Azure/GCP)".
- **1.0 GA Announcement:** highlight stability metrics, adoption, sample diagrams.
- **Migration Guide** updates between 0.9 and 1.0: remove AWS-only customization patterns.
- **Provider Matrix Table:** mapping prefixes (aws_, azurerm_, google_) → canonical categories.
- **Annotation Examples:** multi-cloud connect/disconnect patterns.
- **Plugin Developer Guide:** published after 1.1 (providers/README.md).

---

## Rollback / Contingency Procedures

- **If Azure/GCP handlers cause >10% failure rate during RC:**
  - Disable handler invocation; revert to generic nodes while keeping provider_id labeling.
- **If ProviderContext introduces performance regression >30%:**
  - Fallback to cached static config objects per provider; delay dynamic dispatch for 1 release.
- **If plugin security concerns arise:**
  - Restrict dynamic import to internal provider list; defer external plugin enablement.

---

## Tracking & Reporting

- Weekly status report: velocity, defect counts, adoption pre-release (internal testing).
- Burn-down chart per sprint with blockers flagged (e.g., icon shortage, test fixture delays).
- KPI dashboard updates each minor release (manual until telemetry opt-in implemented).

---

## Next Steps (Immediate Actions)

1. Confirm sprint planning estimates with engineering.
2. Approve ProviderContext interface & naming conventions.
3. Kick off icon acquisition for Azure/GCP core sets (minimum viable subset).
4. Allocate QA resource for multi-provider test harness.
5. Draft migration warning mechanism for legacy imports.

---

**End of Roadmap**
