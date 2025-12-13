# Storage & File Systems

## EFS (Elastic File System)

**Transformation**: EFS file systems and mount targets are reorganized for clarity.

**What Happens**:
1. **Mount targets connect to file systems**:
   - Mount targets are the user-facing interface to EFS
   - Each mount target is connected to its file system

2. **File system connections are reversed**:
   - Resources that connect to the file system are reversed
   - This makes the file system the source of the connection

3. **File system references are replaced with mount targets**:
   - In consolidated nodes, file system references are replaced with mount targets
   - This shows the mount point as the access mechanism

**Hierarchy**:
```
Before:
Subnet → EFS File System → EFS Mount Target

After:
Subnet → EFS Mount Target → EFS File System
```

**Connections**:
- **Added**: Mount target → File system
- **Reversed**: Resource → File system becomes File system → Resource
- **Replaced**: File system references become mount target references in consolidated views

**Why**: Mount targets are the subnet-specific access points; the file system is the shared backend storage.

## Implementation

```
FUNCTION handle_efs_resources(tfdata):

    // Step 1: Find EFS resources
    efs_systems = FIND_RESOURCES_CONTAINING(graphdict, "aws_efs_file_system")
    efs_mount_targets = FIND_RESOURCES_CONTAINING(graphdict, "aws_efs_mount_target")

    // Step 2: Link mount targets to file systems
    FOR EACH target IN efs_mount_targets:
        FOR EACH fs IN efs_systems:
            // Mount target points to file system
            IF fs NOT IN graphdict[target]:
                ADD fs TO graphdict[target]

            // Reverse file system connections
            FOR EACH fs_connection IN COPY(graphdict[fs]):
                IF fs_connection starts with "aws_efs_mount_target":
                    // Remove mount target from FS connections
                    REMOVE fs_connection FROM graphdict[fs]
                ELSE:
                    // Reverse: fs_connection → fs becomes fs → fs_connection
                    ADD fs TO graphdict[fs_connection]
                    REMOVE fs_connection FROM graphdict[fs]

    // Step 3: Replace file system references with mount targets in consolidated nodes
    FOR EACH node IN graphdict:
        IF node is consolidated:
            connections = COPY(graphdict[node])
            FOR EACH connection IN connections:
                IF connection starts with "aws_efs_file_system":
                    // Replace with mount target
                    target = efs_mount_targets[0]
                    target_base = REMOVE_SUFFIX(target)  // Remove ~1, ~2, etc.
                    REMOVE connection FROM graphdict[node]
                    ADD target_base TO graphdict[node]

    RETURN tfdata
```

**Key Transformation**: Mount target becomes the user-facing resource; file system is the backend
