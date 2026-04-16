# Feature Specification: Native draw.io mxGraph Emitter

**Feature Branch**: `012-native-drawio-emitter`  
**Created**: 2026-04-16  
**Status**: Draft  
**Input**: User description: "Replace graphviz2drawio with native mxGraph emitter (GitHub issue #188)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate draw.io Diagram from Terraform Code (Priority: P1)

A user runs `terravision draw --source ./terraform --format drawio` and receives a `.drawio` file that opens correctly in the draw.io desktop application or web editor. The diagram contains all infrastructure resources, connections, and cluster groupings (VPCs, subnets, availability zones) matching the same layout produced by the existing PNG/SVG output path. Icons use draw.io's native provider shape libraries (AWS, Azure, GCP) rather than embedded base64 PNG images.

**Why this priority**: This is the core value proposition. Without a working end-to-end drawio export, no other story delivers value. It also validates the entire pipeline: DOT generation, xdot parsing, mxGraph XML emission, and shape mapping.

**Independent Test**: Run `terravision draw --source <any-terraform-dir> --format drawio`, open the resulting `.drawio` file in draw.io, and verify all resources, connections, and groupings are present with correct native icons.

**Acceptance Scenarios**:

1. **Given** a Terraform project with AWS resources, **When** the user runs `terravision draw --source ./terraform --format drawio`, **Then** a `.drawio` file is produced that opens in draw.io without errors, contains all expected resource nodes with native AWS shape-library icons, correct edge connections, and proper cluster hierarchy (VPC > AZ > Subnet).
2. **Given** a Terraform project with Azure resources, **When** the user runs `terravision draw --source ./terraform --format drawio`, **Then** the `.drawio` file uses native Azure shape-library icons for recognized resource types.
3. **Given** a Terraform project with GCP resources, **When** the user runs `terravision draw --source ./terraform --format drawio`, **Then** the `.drawio` file uses native GCP shape-library icons for recognized resource types.
4. **Given** a resource type that has no mapping in the draw.io shape library, **When** the diagram is generated, **Then** the resource falls back to an embedded PNG icon so no resources are missing from the output.

---

### User Story 2 - HTML Labels and Embedded Images in Clusters Render Correctly (Priority: P1)

A user generating a drawio diagram sees cluster containers (VPC, subnet, security group, resource group, virtual network) with their full HTML-table labels preserved — including embedded images and formatted text. For AWS, this means corner icons at the top-left of clusters. For Azure and GCP, this means any HTML-table labels with embedded provider images render correctly. The old `graphviz2drawio` approach silently dropped all HTML-table cluster labels, losing both icons and formatted text.

**Why this priority**: Cluster rendering is fundamental to architecture diagram comprehension. The HTML labels carry provider-specific visual cues (AWS corner icons, Azure/GCP cluster header images) that help users identify grouping types at a glance. Without these, the drawio output is significantly less useful than the PNG output.

**Independent Test**: Generate drawio files from Terraform projects across all three providers that contain grouping resources (AWS VPCs/subnets, Azure resource groups/VNets, GCP networks). Open in draw.io and verify HTML-table labels with embedded images render correctly for each provider.

**Acceptance Scenarios**:

1. **Given** an AWS Terraform project with VPC, subnet, and AZ resources, **When** the user generates a drawio file, **Then** each cluster container displays its corner icon at the top-left position and the cluster label is visible and correctly placed.
2. **Given** an Azure Terraform project with resource groups and virtual networks, **When** the user generates a drawio file, **Then** cluster containers display their HTML-table labels with embedded provider images correctly.
3. **Given** a GCP Terraform project with network and subnetwork resources, **When** the user generates a drawio file, **Then** cluster containers display their HTML-table labels with embedded provider images correctly.
4. **Given** a diagram with nested clusters (VPC containing AZ containing subnet), **When** the drawio file is opened, **Then** the nesting hierarchy is preserved and visually correct.

---

### User Story 3 - Simplified Installation (Priority: P2)

A user installs TerraVision and uses the drawio export without needing to install `graphviz2drawio`, `pygraphviz`, or compile C extensions. The only system dependency remains the `dot` binary (Graphviz), which is already required for PNG/SVG output.

**Why this priority**: Installation friction (especially on Apple Silicon and Windows) is a pain point motivating this feature. Removing the C-extension dependency lowers the barrier to adoption.

**Independent Test**: Install TerraVision via `pip install terravision` (without the `[drawio]` extra) on a clean environment. Run `terravision draw --format drawio` and verify it works without additional dependency installation.

**Acceptance Scenarios**:

1. **Given** a fresh Python environment with only TerraVision and Graphviz installed, **When** the user runs `terravision draw --source ./terraform --format drawio`, **Then** the command succeeds without requiring `graphviz2drawio` or `pygraphviz`.
2. **Given** an Apple Silicon Mac without CFLAGS/LDFLAGS configured, **When** the user installs TerraVision and runs drawio export, **Then** installation and export both succeed without C-extension compilation.

---

### User Story 4 - Footer, Legend, and Label Positioning Correct by Construction (Priority: P3)

A user generates a drawio diagram and finds the footer (title), flow legend table, and node labels all positioned correctly — matching the PNG output — without any post-processing XML fixups. The footer and legend are currently positioned via a gvpr post-processing script that adjusts the Graphviz DOT file; the native emitter must honour those same positions when reading the xdot layout.

**Why this priority**: This fixes known visual defects in the current draw.io export where the footer lands at the top and legend tables are misplaced.

**Independent Test**: Generate a drawio file from a Terraform project with annotations (title, custom labels) and with `--ai-annotate` to produce a flow legend table. Open in draw.io and verify the footer is at the bottom, the legend table appears in the same position as the PNG output, and node labels appear below icons.

**Acceptance Scenarios**:

1. **Given** a Terraform project with a `terravision.yml` annotation file that includes a title, **When** the user generates a drawio file, **Then** the title/footer appears at the bottom of the canvas, not the top.
2. **Given** a Terraform project with AI-generated flow annotations producing a legend table, **When** the user generates a drawio file, **Then** the legend table appears in the same canvas position as it does in the PNG output.
3. **Given** any Terraform project, **When** the user generates a drawio file, **Then** all node labels appear below their respective icons.

---

### User Story 5 - Users Can Replace Shapes from draw.io Sidebar (Priority: P3)

A user opens the generated drawio file and right-clicks on a resource node. The node uses a native draw.io shape, allowing the user to browse and replace it with a sibling shape from the same official AWS/Azure/GCP library via draw.io's shape picker.

**Why this priority**: This is a usability enhancement for users who want to customize diagrams after generation. It works automatically as a consequence of using native shapes but adds no functionality on its own.

**Independent Test**: Open a generated drawio file in draw.io, right-click a resource node, and verify the shape picker offers related shapes from the same provider library.

**Acceptance Scenarios**:

1. **Given** a drawio file with native AWS shapes, **When** the user selects a Lambda node in draw.io and opens the shape picker, **Then** the sidebar displays the AWS shape library with related compute shapes available for replacement.

---

### Edge Cases

- What happens when `dot -Txdot` produces unexpected or malformed output for a particular graph topology?
- How does the emitter handle resources with very long names that might affect label positioning?
- What happens when a cluster has no child resources (empty VPC or subnet)?
- How does the emitter handle bidirectional edges (two-way arrows between resources)?
- What happens when the Terraform project produces zero resources (empty plan)?
- How does the emitter handle special characters in resource names or labels (e.g., quotes, angle brackets)?
- What happens when annotations add external actor nodes (e.g., "Internet", "Users") that have no Terraform resource type?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate valid mxGraph XML that opens without errors in draw.io desktop and web applications
- **FR-002**: System MUST parse xdot output from `dot -Txdot` to extract node positions, dimensions, cluster bounding boxes, edge paths, and label positions
- **FR-003**: System MUST map resource types to draw.io native shape-library identifiers for AWS, Azure, and GCP providers
- **FR-004**: System MUST fall back to embedded PNG icon when no native shape-library mapping exists for a resource type
- **FR-005**: System MUST preserve cluster hierarchy (VPC > AZ > Subnet) using mxGraph parent-child cell relationships
- **FR-006**: System MUST faithfully render HTML-table cluster labels including embedded images (AWS corner icons, Azure/GCP cluster header images) and formatted text
- **FR-007**: System MUST render node labels below their icons
- **FR-008**: System MUST render edges with correct source/target connections and appropriate arrow styles (unidirectional and bidirectional)
- **FR-009**: System MUST position the diagram footer/title at the bottom of the canvas
- **FR-010**: System MUST produce the drawio file without requiring the `graphviz2drawio` or `pygraphviz` dependencies
- **FR-011**: System MUST support all existing CLI options that apply to drawio output (`--source`, `--outfile`, `--workspace`, `--varfile`, `--annotate`, `--planfile`, `--graphfile`, `--simplified`, `--show`, `--debug`)
- **FR-012**: System MUST handle annotation-added nodes (external actors, custom nodes) that lack Terraform resource types
- **FR-013**: System MUST produce well-formed XML that does not contain unescaped special characters in labels or attributes
- **FR-014**: System MUST handle edge label positioning for annotated connections
- **FR-015**: System MUST support the `--show` flag to auto-open the generated drawio file

### Key Entities

- **Shape Mapping**: A lookup table that maps TerraVision internal resource type identifiers to draw.io native shape-library names (e.g., `aws_lambda_function` maps to `mxgraph.aws4.lambda_function`)
- **mxCell**: The fundamental XML element in draw.io files, representing a node, edge, or container with geometry, style, and parent-child relationships
- **Cluster**: A grouping container (VPC, AZ, subnet, security group) that translates to an mxCell with child cells nested via the `parent` attribute

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can generate drawio files from Terraform projects of any size without installing C-extension dependencies
- **SC-002**: 100% of resources, connections, and cluster groupings present in the PNG output are also present in the drawio output for the same Terraform project
- **SC-003**: Generated drawio files open without errors or warnings in draw.io desktop application (v24+) and draw.io web editor
- **SC-004**: Native shape-library coverage includes at least the top 50 most common resource types for each supported provider (AWS, Azure, GCP)
- **SC-005**: HTML-table cluster labels with embedded images are correctly rendered in the drawio output without any post-processing XML fixups
- **SC-006**: Footer/title elements are positioned at the bottom of the canvas in the drawio output

## Assumptions

- The `dot` binary (Graphviz) is already installed as a system dependency, as required by TerraVision for PNG/SVG output — no new system dependency is introduced
- The `-Txdot` output format from Graphviz is stable and well-documented, providing reliable position data for nodes, edges, and clusters
- draw.io's native shape-library names (e.g., `mxgraph.aws4.*`, `mxgraph.azure.*`, `mxgraph.gcp.*`) are stable identifiers that do not change between draw.io releases
- The existing DOT generation pipeline in `modules/drawing.py` (including gvpr post-processing) remains unchanged — the new emitter consumes its output
- The `graphviz2drawio` and `pygraphviz` optional dependencies can be removed from the project without affecting any other feature
- The `_postprocess_drawio_xml()` function is no longer needed and can be removed
- Users who rely on the current drawio output format will see improved (not degraded) results, as the native emitter fixes known rendering issues
- The CLI interface remains identical — `terravision draw --format drawio` continues to work with the same flags
