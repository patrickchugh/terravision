# Phase 4 Bug Fixes: Developer Deep Dive

## Overview

This guide documents each bug fix implemented in Phase 4. For each fix: what was broken, root cause, solution approach, code examples with file paths and line numbers, and how to test.

## FIX01 & FIX07: SQS Queue Policy Transitive Linking

**File**: `modules/resource_handlers/aws.py`  
**Function**: `link_sqs_queue_policy()`  
**Lines**: 964-989

### What was broken
Lambda → SQS policy → Queue created wrong direction edges, leading to confusing visualizations.

### Root cause
The linking logic followed reverse references or attached policies without transitive edge correction.

### Solution approach
Reverse the transitive linking: derive direct Lambda → Queue edges based on policy attachments. Ensure direction aligns with action flow: Lambda consumes or produces messages on the queue.

### Code location
```python
# modules/resource_handlers/aws.py:1010-1024
def link_sqs_queue_policy(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Link SQS queues to resources via queue policies.
    
    Creates transitive connections: if Lambda → SQS Policy → Queue,
    then Lambda should also connect directly to Queue.
    """
    result = dict(terraform_data)
    
    # Map queue policies to their queues
    policy_to_queue = {}
    for resource, deps in sorted(terraform_data.items()):
        if "aws_sqs_queue_policy" in resource:
            for dep in deps:
                if "aws_sqs_queue" in dep:
                    policy_to_queue[resource] = dep
    
    # Add transitive links from resources → queue (via policy)
    for resource, deps in sorted(terraform_data.items()):
        for dep in deps:
            if "aws_sqs_queue_policy" in dep and dep in policy_to_queue:
                queue = policy_to_queue[dep]
                if queue not in result[resource]:
                    result[resource].append(queue)
    
    return result
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestLinkSqsQueuePolicy`
- **Integration**: Validate queues in `tests/json/expected-wordpress.json` if applicable
- **Assert**: Direction of edges Lambda → Queue

---

## FIX02 & CR04: IAM Resource Disconnection Scope

**File**: `modules/cloud_config/aws.py`  
**Lines**: 236-242

### What was broken
Adding all IAM resources to DISCONNECT_LIST removed essential IAM visualizations.

### Root cause
Over-broad configuration scope led to loss of meaningful edges and nodes.

### Solution approach
Restrict DISCONNECT_LIST to only `aws_iam_role_policy` (inline policies). Rely on FIX08 transitive linking to prevent unwanted reverse connections.

### Code location
```python
# modules/cloud_config/aws.py:236-242
DISCONNECT_LIST = [
    "aws_iam_role_policy",  # Inline IAM policies clutter IAM role diagrams
]
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestHandleSpecialCases::test_disconnect_services_removed`
- **Unit**: `tests/unit/test_aws_handlers.py::TestLinkEc2ToIamRoles` (indirectly validates edges remain)
- **Assert**: Roles, instance profiles, and other IAM items still appear with correct connections

---

## FIX03: Security Group Orphan Handling

**File**: `modules/resource_handlers/aws.py`  
**Function**: `aws_handle_sg()`  
**Lines**: 584-592

### What was broken
Security groups (SGs) with children were removed as orphans.

### Root cause
Orphan removal logic did not check for child relationships before pruning.

### Solution approach
Preserve SGs that have child resources (interfaces, instances). Only remove truly orphaned SGs without parents or children.

### Code location
```python
# modules/resource_handlers/aws.py:584-592
# Remove orphaned security groups (those with no parents and no children)
for sg in list(tfdata["graphdict"].keys()):
    if sg.startswith("aws_security_group.") and sg not in orphaned_sgs:
        # Check if this SG has any resources referencing it (children)
        has_children = any(
            sg in deps for deps in tfdata["graphdict"].values()
        )
        
        if not has_children and not tfdata["graphdict"][sg]:
            # No children and no parents - truly orphaned
            orphaned_sgs.add(sg)
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestAwsHandleSg`
- **Assert**: SG nodes remain when attached to dependent resources

---

## FIX04: Classic ELB Support

**File**: `modules/resource_handlers/aws.py`  
**Function**: `aws_handle_lb()`  
**Lines**: 640-748

### What was broken
Classic ELBs (`aws_elb.*`) were ignored; only ALB/NLB supported.

### Root cause
Handler detection limited to application/network load balancers.

### Solution approach
Add detection and handling for `aws_elb.*` resources. Normalize attributes and edges to match existing LB patterns.

### Code location
```python
# modules/resource_handlers/aws.py:640-748
def aws_handle_lb(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle AWS load balancer types (ALB, NLB, Classic ELB).
    
    Detects all three LB types and normalizes metadata.
    """
    # Find all load balancers including classic ELBs
    albs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_alb")
    nlbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_lb")
    classic_elbs = helpers.list_of_dictkeys_containing(tfdata["graphdict"], "aws_elb.")
    
    all_lbs = albs + nlbs + classic_elbs
    
    for lb in all_lbs:
        # Detect LB type from metadata or resource name
        if "aws_elb." in lb and "aws_elb_attachment" not in lb:
            lb_type = "classic"
        elif tfdata["meta_data"].get(lb, {}).get("load_balancer_type") == "network":
            lb_type = "network"
        else:
            lb_type = "application"
        
        # Update metadata with detected type
        tfdata["meta_data"][lb]["lb_type"] = lb_type
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestAwsHandleLb::test_detects_alb_nlb_and_clb_variants`
- **Assert**: Classic ELB nodes and edges exist in graph

---

## FIX05: Subnet Availability Zone Handling

**File**: `modules/resource_handlers/aws.py`  
**Function**: `aws_handle_subnet_azs()`  
**Lines**: 293-347

### What was broken
Missing 'hidden' key caused crashes; AZ suffixes not applied to subnet names.

### Root cause
Incomplete initialization, naming rules not enforced for AZs.

### Solution approach
- Initialize 'hidden' key to prevent KeyError
- Apply AZ suffix logic (e.g., `subnet~1` for us-east-1a)

### Code location
```python
# modules/resource_handlers/aws.py:293-347
def aws_handle_subnet_azs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Add AZ suffix to subnet names and initialize hidden key."""
    
    for subnet in tfdata["graphdict"]:
        if "aws_subnet" in subnet:
            # Initialize hidden key to prevent crashes
            if "meta_data" not in tfdata:
                tfdata["meta_data"] = {}
            if subnet not in tfdata["meta_data"]:
                tfdata["meta_data"][subnet] = {}
            
            # Set hidden key if not present
            if "hidden" not in tfdata["meta_data"][subnet]:
                tfdata["meta_data"][subnet]["hidden"] = False
            
            # Add AZ suffix if availability_zone exists
            if "availability_zone" in tfdata["meta_data"][subnet]:
                az = tfdata["meta_data"][subnet]["availability_zone"]
                if az and az[-1].isalpha():
                    suffix = str(ord(az[-1].lower()) - ord("a") + 1)
                    # Update resource name with suffix
                    new_name = f"{subnet}~{suffix}"
                    # ... (remainder of renaming logic)
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestAwsHandleSubnetAzs`
- **Assert**: No crashes, names include AZ suffix (e.g., `~1`, `~2`)

---

## FIX06: EFS Mount Target Grouping

**File**: `modules/resource_handlers/aws.py`  
**Function**: `aws_handle_efs()`  
**Lines**: 352-388

### What was broken
EFS mount targets not grouped under file systems.

### Root cause
Flat structure led to scattered nodes without hierarchy.

### Solution approach
Complete rewrite: group mount targets under parent EFS file system using hierarchical structure.

### Code location
```python
# modules/resource_handlers/aws.py:352-388
def aws_handle_efs(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Group EFS mount targets under their parent file system."""
    
    # Find all EFS file systems and mount targets
    efs_filesystems = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_file_system"
    )
    efs_mount_targets = helpers.list_of_dictkeys_containing(
        tfdata["graphdict"], "aws_efs_mount_target"
    )
    
    # Group mount targets by file system
    for fs in efs_filesystems:
        fs_id = tfdata["meta_data"].get(fs, {}).get("id", "")
        
        # Find mount targets for this file system
        for mt in efs_mount_targets:
            mt_fs_id = tfdata["meta_data"].get(mt, {}).get("file_system_id", "")
            
            if mt_fs_id == fs_id:
                # Add mount target as child of file system
                if mt not in tfdata["graphdict"][fs]:
                    tfdata["graphdict"][fs].append(mt)
                
                # Remove mount target as standalone node
                if mt in tfdata["graphdict"]:
                    del tfdata["graphdict"][mt]
    
    return tfdata
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestAwsHandleEfs`
- **Integration**: `tests/json/expected-wordpress.json`, `tests/json/bastion-expected.json` updated
- **Assert**: Mount targets nested under EFS file system nodes

---

## FIX08: EC2 to IAM Role Linking

**File**: `modules/resource_handlers/aws.py`  
**Function**: `link_ec2_to_iam_roles()`  
**Lines**: 934-960

### What was broken
EC2 → instance profile → role did not create direct EC2 → role link.

### Root cause
Missing transitive linking logic to simplify indirect relationships.

### Solution approach
Add transitive linking to connect EC2 directly to IAM role for clearer visualization.

### Code location
```python
# modules/resource_handlers/aws.py:976-1006
def link_ec2_to_iam_roles(terraform_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Link EC2 instances to IAM roles via instance profiles.
    
    Creates transitive connections: EC2 → Instance Profile → Role
    becomes EC2 → Role (while keeping profile visible).
    """
    result = dict(terraform_data)
    
    # Map instance profiles to IAM roles
    profile_to_role = {}
    for resource, deps in sorted(terraform_data.items()):
        if "aws_iam_instance_profile" in resource:
            for dep in deps:
                if "aws_iam_role" in dep and "policy" not in dep:
                    profile_to_role[resource] = dep
    
    # Find EC2 instances and add transitive IAM role link
    for resource, deps in sorted(terraform_data.items()):
        if "aws_instance" in resource:
            for dep in deps:
                if "aws_iam_instance_profile" in dep and dep in profile_to_role:
                    iam_role = profile_to_role[dep]
                    if iam_role not in result[resource]:
                        result[resource].append(iam_role)
    
    return result
```

### How to test
- **Unit**: `tests/unit/test_aws_handlers.py::TestLinkEc2ToIamRoles`
- **Assert**: EC2 → Role edges exist while profiles remain represented

---

## Code Review Fixes (CR01-CR06)

### CR01: Dead Code Removal
Removed duplicate dead block in `aws_handle_vpcendpoints()` that was unreachable after the first return statement.

### CR02/CR02a: Return Type Safety

**File**: `modules/drawing.py`  
**Function**: `handle_nodes()`  
**Lines**: 137, 156, 198-209, 369-380

**Problem**: Function could return `None` causing unpack errors.

**Solution**:
- Return `Tuple[Optional[Node], List[str]]` (line 137)
- Use `return None, drawn_resources` (line 156)
- Add guards at call sites to handle None (lines 198-209, 369-380)

```python
# Line 137: Updated return type
def handle_nodes(...) -> Tuple[Optional[Node], List[str]]:

# Line 156: Return tuple with None instead of bare return
if resource_type not in avl_classes:
    return None, drawn_resources

# Lines 198-209: Guard against None
connectedNode, drawn_resources = handle_nodes(...)
# Skip if node creation failed
if connectedNode is None:
    continue
```

### CR03: Security Improvement (subprocess vs os.system)

**File**: `modules/drawing.py`  
**Lines**: 10, 536-544

**Problem**: `os.system()` had no error handling and security concerns.

**Solution**:
- Use `subprocess.run(check=True, capture_output=True)`
- Add `import subprocess` (line 10)

```python
# Line 10: Added import
import subprocess

# Lines 536-544: Secure subprocess execution
subprocess.run(
    ["gvpr", "-c", "-q", "-f", str(path_to_script), str(path_to_predot), "-o", str(path_to_postdot)],
    check=True,
    capture_output=True,
    text=True,
)
```

### CR05: Code Quality
Removed duplicate `OUTER_NODES` assignment at line 63 in `modules/drawing.py`.

### CR06: Dead Code Removal
Removed commented-out code and unused `ecs_nodes` variable in `aws_handle_ecs()`.

---

## Testing References

**All new unit tests**: `tests/unit/test_aws_handlers.py`

**Integration fixtures updated**:
- `tests/json/expected-wordpress.json`
- `tests/json/bastion-expected.json`

---

## How to Extend

- Use **transitive linking** to surface direct, semantically meaningful edges
- Preserve **parent-child relationships** via grouping when resources are hierarchical
- Apply **provider detection** where class resolution depends on resource type prefixes
- Write **unit tests** for every handler and linking change
- Update **integration fixtures** when diagram structure changes
