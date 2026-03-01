"""Git library module for TerraVision.

This module handles cloning and caching of Terraform modules from various sources
including Git repositories (GitHub, GitLab, Bitbucket), Terraform Registry, and
Terraform Enterprise. Supports SSH, HTTPS, and registry URL formats.
"""

import os
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from sys import exit
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urlparse

import click
import git
import requests
from git import RemoteProgress
from tqdm import tqdm

import modules.helpers as helpers
from modules.helpers import *


def _parse_version(version_str: str) -> Optional[Tuple[int, ...]]:
    """Parse a version string like '5.48.0' into a tuple of ints.

    Returns None for unparseable versions (e.g., pre-release '1.0.0-pre').
    """
    try:
        return tuple(int(x) for x in version_str.split("."))
    except ValueError:
        return None


def _resolve_version_constraint(constraint: str, versions: List[str]) -> Optional[str]:
    """Resolve a Terraform version constraint against available versions.

    Supports ~>, >=, <=, >, <, = operators and comma-separated constraints.
    Returns the latest version satisfying all constraints, or None.
    """
    constraint = constraint.strip()
    if not constraint or not versions:
        return None

    # Parse individual constraints from comma-separated string
    constraints = [c.strip() for c in constraint.split(",")]

    def matches(ver_str: str) -> bool:
        ver = _parse_version(ver_str)
        if ver is None:
            return False
        for cons in constraints:
            cons = cons.strip()
            if cons.startswith("~>"):
                bound = cons[2:].strip()
                bound_parts = bound.split(".")
                min_ver = _parse_version(bound)
                # ~> X.Y means >= X.Y, < (X+1).0
                # ~> X.Y.Z means >= X.Y.Z, < X.(Y+1).0
                if len(bound_parts) <= 2:
                    max_ver = (min_ver[0] + 1, 0, 0)
                else:
                    max_ver = (min_ver[0], min_ver[1] + 1, 0)
                if not (min_ver <= ver < max_ver):
                    return False
            elif cons.startswith(">="):
                if ver < _parse_version(cons[2:].strip()):
                    return False
            elif cons.startswith("<="):
                if ver > _parse_version(cons[2:].strip()):
                    return False
            elif cons.startswith(">"):
                if ver <= _parse_version(cons[1:].strip()):
                    return False
            elif cons.startswith("<"):
                if ver >= _parse_version(cons[1:].strip()):
                    return False
            elif cons.startswith("="):
                if ver != _parse_version(cons[1:].strip()):
                    return False
            else:
                # Bare version string
                if ver != _parse_version(cons):
                    return False
        return True

    matching = [v for v in versions if matches(v)]
    if not matching:
        return None
    matching.sort(key=_parse_version)
    return matching[-1]


# Global module-level variables
all_repos: List[str] = list()
annotations: Dict[str, Any] = dict()
abspath: str = os.path.abspath(__file__)
dname: str = os.path.dirname(abspath)
MODULE_DIR: str = str(Path(Path.home(), ".terravision", "module_cache"))

# Create module cache directory if it doesn't exist
if not os.path.exists(MODULE_DIR):
    os.makedirs(MODULE_DIR)


class CloneProgress(RemoteProgress):
    """Progress bar for git clone operations.

    Displays a progress bar using tqdm during git repository cloning.
    """

    def __init__(self) -> None:
        """Initialize progress bar."""
        super().__init__()
        self.pbar = tqdm(leave=False)

    def update(
        self,
        op_code: int,
        cur_count: int,
        max_count: Optional[int] = None,
        message: str = "",
    ) -> None:
        """Update progress bar with current clone status.

        Args:
            op_code: Git operation code
            cur_count: Current progress count
            max_count: Maximum progress count
            message: Optional status message
        """
        self.pbar.total = max_count
        self.pbar.n = cur_count
        self.pbar.refresh()


def handle_readme_source(resp: requests.Response) -> str:
    """Extract and convert git URL from Bitbucket API response.

    Args:
        resp: HTTP response containing readme with git URL

    Returns:
        Formatted SSH git URL
    """
    readme = resp.json()["root"]["readme"]
    githubURL = "ssh://git@" + find_between(readme, "(https://", ")")

    # Convert domain format for SSH
    found = re.findall(r"\.........\.net", githubURL)
    for site in found:
        githubURL = githubURL.replace(site, "-ssh" + site)

    # Convert Bitbucket URL format to git SSH format
    githubURL = githubURL.replace("/projects/", ":7999/")
    githubURL = githubURL.replace("/repos/", "/")
    startindex = githubURL.index("/browse?")
    githubURL = githubURL[0:startindex] + ".git"

    return githubURL


# Known git hosting domains that should be cloned directly (not via registry API)
GIT_HOSTING_DOMAINS = ["github.com", "gitlab.com", "bitbucket.org"]

# Archive file extensions supported for HTTP module sources
ARCHIVE_EXTENSIONS = (
    ".zip",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".tar",
)


def _is_http_archive(url: str) -> bool:
    """Check if a URL points to a downloadable archive file.

    Args:
        url: URL to check (may have s3::, gcs::, or query parameters)

    Returns:
        True if URL ends with a known archive extension
    """
    # Strip s3::/gcs:: prefixes and query parameters for extension check
    clean = url
    for prefix in ("s3::", "gcs::"):
        if clean.startswith(prefix):
            clean = clean[len(prefix) :]
    # Remove query params first, then strip // subfolder (keep archive path, not subfolder)
    clean = clean.split("?")[0]
    # For protocol URLs, skip protocol //, then strip // subfolder
    if clean.startswith(("https://", "http://")):
        protocol_end = clean.find("//") + 2
        remaining = clean[protocol_end:]
        if "//" in remaining:
            clean = clean[:protocol_end] + remaining.split("//", 1)[0]
    return any(clean.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def _download_and_extract_archive(url: str, destination: str) -> None:
    """Download an archive from HTTP URL and extract it to destination.

    Supports .zip, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, and .tar.
    Handles s3:: and gcs:: prefixed URLs by stripping the prefix.

    Args:
        url: HTTP URL to download the archive from
        destination: Local directory to extract archive contents into
    """
    # Strip s3::/gcs:: prefixes — the underlying URL is plain HTTP
    for prefix in ("s3::", "gcs::"):
        if url.startswith(prefix):
            url = url[len(prefix) :]

    # Remove ?ref= or other query params from download URL
    download_url = url.split("?")[0]

    click.echo(f"  Downloading archive: {download_url}")

    try:
        resp = requests.get(download_url, stream=True, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        click.echo(
            click.style(
                f"\nERROR: Failed to download archive from {download_url}: {e}",
                fg="red",
                bold=True,
            )
        )
        exit()

    # Write to a temp file, then extract
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        os.makedirs(destination, exist_ok=True)

        if download_url.endswith(".zip"):
            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(destination)
        elif any(
            download_url.endswith(ext)
            for ext in (
                ".tar.gz",
                ".tgz",
                ".tar.bz2",
                ".tbz2",
                ".tar.xz",
                ".txz",
                ".tar",
            )
        ):
            with tarfile.open(tmp_path, "r:*") as tf:
                tf.extractall(destination)
        else:
            click.echo(
                click.style(
                    f"\nERROR: Unsupported archive format: {download_url}",
                    fg="red",
                    bold=True,
                )
            )
            exit()

        click.echo(click.style(f"  Extracted archive to {destination}", fg="green"))
    finally:
        os.unlink(tmp_path)


def _is_git_hosting_url(sourceURL: str) -> bool:
    """Check if URL is for a known git hosting service.

    Args:
        sourceURL: Source URL to check

    Returns:
        True if URL contains a known git hosting domain
    """
    return any(domain in sourceURL for domain in GIT_HOSTING_DOMAINS)


def get_clone_url(sourceURL: str, version_constraint: str = "") -> Tuple[str, str, str]:
    """Parse source URL and extract git clone URL, subfolder, and tag.

    Determines URL type and delegates to appropriate handler function.
    Supports git::, direct domain URLs, and Terraform Registry URLs.

    Args:
        sourceURL: Source URL in various formats (git::, registry, or direct URL)
        version_constraint: Terraform version constraint (e.g., "~> 5.0")

    Returns:
        Tuple of (git_url, subfolder, git_tag)
    """
    # Check for HTTP archive sources (e.g., .tgz, .zip from S3, GCS, or any HTTP URL)
    # Must check before git:: prefix since s3::/gcs:: could be confused with git::
    if _is_http_archive(sourceURL):
        return _handle_http_archive_url(sourceURL)

    # Check for git:: prefix (SSH or HTTPS git URLs)
    is_git_prefix = (
        sourceURL.startswith("git::ssh://")
        or sourceURL.startswith("git@git")
        or "git::" in sourceURL
    )
    if is_git_prefix:
        return _handle_git_prefix_url(sourceURL)

    # Check for direct domain URLs (GitHub, GitLab, Bitbucket, etc.)
    # Only route to domain handler for known git hosting providers;
    # other domains (e.g., app.terraform.io) are private registries.
    if helpers.check_for_domain(sourceURL) and _is_git_hosting_url(sourceURL):
        return _handle_domain_url(sourceURL)

    # Default to Terraform Registry (public or private) or plain HTTP Module URLs
    return _handle_registry_url(sourceURL, version_constraint)


def _handle_git_prefix_url(sourceURL: str) -> Tuple[str, str, str]:
    """Handle URLs with git:: prefix.

    Parses git:: prefixed URLs for SSH and HTTPS git repositories,
    extracting the git address, subfolder path, and tag reference.

    Args:
        sourceURL: URL with git:: prefix

    Returns:
        Tuple of (git_address, subfolder, git_tag)
    """
    subfolder = ""
    git_tag = ""

    # Remove git:: prefix, keeping the rest (ssh://, https://, etc.)
    if "git::" in sourceURL:
        gitaddress = sourceURL.split("git::", 1)[1]
    else:
        gitaddress = sourceURL

    # Normalize GitHub and GitLab SSH URLs to SCP-style (only when not using ssh:// protocol)
    if not gitaddress.startswith("ssh://"):
        gitaddress = gitaddress.replace("git@github.com/", "git@github.com:")
        gitaddress = gitaddress.replace("git@gitlab.com/", "git@gitlab.com:")

    # Extract subfolder if present (indicated by // after protocol)
    # For protocol-based URLs (https://, http://, ssh://), skip past the protocol //
    if gitaddress.startswith(("https://", "http://", "ssh://")):
        protocol_end = gitaddress.find("//") + 2
        remaining = gitaddress[protocol_end:]
        has_subfolder = "//" in remaining
        if has_subfolder:
            repo_part, subfolder_part = remaining.split("//", 1)
            subfolder = subfolder_part.split("?")[0]
            gitaddress = gitaddress[:protocol_end] + repo_part
            if "?ref" in subfolder_part:
                git_tag = subfolder_part.split("?ref=")[1]
        elif "?ref" in gitaddress:
            git_tag = gitaddress.split("?ref=")[1]
            gitaddress = gitaddress.split("?ref=")[0]
    else:
        has_subfolder = "//" in gitaddress
        if has_subfolder:
            subfolder_array = gitaddress.split("//")
            subfolder = subfolder_array[1].split("?")[0]
            gitaddress = subfolder_array[0]
            if "?ref" in subfolder_array[1]:
                git_tag = subfolder_array[1].split("?ref=")[1]
        elif "?ref" in gitaddress:
            gitaddress = gitaddress.split("?ref=")[0]
            git_tag = sourceURL.split("?ref=")[1]

    return gitaddress, subfolder, git_tag


def _handle_http_archive_url(sourceURL: str) -> Tuple[str, str, str]:
    """Handle HTTP archive URLs (.tgz, .zip, etc.).

    Strips s3::/gcs:: prefixes, extracts // subfolder if present,
    and returns the download URL. No git tag is applicable.

    Args:
        sourceURL: HTTP archive URL (possibly with s3::/gcs:: prefix)

    Returns:
        Tuple of (download_url, subfolder, empty_tag)
    """
    url = sourceURL
    subfolder = ""

    # Strip s3::/gcs:: prefixes
    for prefix in ("s3::", "gcs::"):
        if url.startswith(prefix):
            url = url[len(prefix) :]

    # Extract // subfolder if present (skip protocol //)
    if url.startswith(("https://", "http://")):
        protocol_end = url.find("//") + 2
        remaining = url[protocol_end:]
        if "//" in remaining:
            repo_part, subfolder = remaining.split("//", 1)
            subfolder = subfolder.split("?")[0]
            url = url[:protocol_end] + repo_part

    return url, subfolder, ""


def _handle_domain_url(sourceURL: str) -> Tuple[str, str, str]:
    """Handle direct domain URLs.

    Parses direct GitHub, GitLab, or other git hosting URLs, extracting
    the repository URL, subfolder path, and tag reference.

    Args:
        sourceURL: Direct domain URL (e.g., github.com/owner/repo)

    Returns:
        Tuple of (github_url, subfolder, git_tag)
    """
    subfolder = ""
    git_tag = ""

    # Extract git tag/branch reference if present
    if "?ref" in sourceURL:
        git_tag = sourceURL.split("?ref=")[1]
        sourceURL = sourceURL.split("?ref=")[0]

    # Parse URL structure for subfolder
    if sourceURL.count("//") > 1:
        # URL with // separator: https://domain/repo//subfolder
        if sourceURL.startswith(("http://", "https://")):
            # Find protocol end, then split on // for subfolder
            protocol_end = sourceURL.find("//") + 2
            remaining = sourceURL[protocol_end:]
            if "//" in remaining:
                repo_part, subfolder = remaining.split("//", 1)
                subfolder = subfolder.split("?")[0]
                githubURL = sourceURL[:protocol_end] + repo_part
        else:
            # Non-HTTP URL with // separator
            parts = sourceURL.split("//", 1)
            githubURL = parts[0]
            subfolder = parts[1].split("?")[0] if len(parts) > 1 else ""
    else:
        # Check for // subfolder in non-HTTP URLs (e.g., github.com/owner/repo//subfolder)
        if "//" in sourceURL and not sourceURL.startswith(("http://", "https://")):
            parts = sourceURL.split("//", 1)
            githubURL = "https://" + parts[0]
            subfolder = parts[1].split("?")[0]
        else:
            # URL with path segments: domain/owner/repo/subfolder/path
            parts = sourceURL.rstrip("/").split("/")
            if sourceURL.startswith(("http://", "https://")):
                # HTTPS URL: https://domain/owner/repo[.git] or https://domain/owner/repo/subfolder
                if len(parts) > 5:
                    githubURL = "/".join(parts[:5])
                    subfolder = "/".join(parts[5:])
                else:
                    githubURL = sourceURL
            elif len(parts) > 3:
                # Non-HTTP URL: domain/owner/repo/subfolder
                githubURL = "/".join(parts[:3])
                subfolder = "/".join(parts[3:])
                githubURL = "https://" + githubURL
            else:
                githubURL = sourceURL
                if "http" not in githubURL:
                    githubURL = "https://" + githubURL

    return githubURL, subfolder, git_tag


def _handle_registry_url(
    sourceURL: str, version_constraint: str = ""
) -> Tuple[str, str, str]:
    """Handle Terraform Registry Module URLs.

    Resolves Terraform Registry or Terraform Enterprise module URLs to their
    underlying git repository URLs. Handles authentication for private registries.

    Args:
        sourceURL: Terraform Registry module URL
        version_constraint: Terraform version constraint (e.g., "~> 5.0")

    Returns:
        Tuple of (github_url, subfolder, git_tag)
    """
    gitaddress = sourceURL
    subfolder = ""
    headers: Dict[str, str] = {}

    # Determine if using Terraform Enterprise or public registry
    if check_for_domain(sourceURL):
        # Terraform Enterprise / Terraform Cloud private registry
        hostname = urlparse("https://" + sourceURL).netloc
        registrypath = sourceURL.split(hostname)
        gitaddress = registrypath[1]
        domain = "https://" + hostname + "/api/registry/v1/modules/"
        click.echo(f"    Assuming Terraform Enterprise API Server URL: {domain}")

        # Build TF_TOKEN_* env var name (dots/dashes become underscores)
        token_env_var = "TF_TOKEN_" + hostname.replace(".", "_").replace("-", "_")
        token = os.environ.get(token_env_var)

        if not token:
            click.echo(
                click.style(
                    f"\nERROR: No {token_env_var} environment variable set. "
                    f"Unable to authorise with {hostname}",
                    fg="red",
                    bold=True,
                )
            )
            exit()

        headers = {"Authorization": "bearer " + token}
    else:
        # Public Terraform Registry
        domain = "https://registry.terraform.io/v1/modules/"

    # Extract subfolder if present
    if sourceURL.count("//") >= 1:
        subfolder_array = sourceURL.split("//")
        subfolder = subfolder_array[1].split("?")[0]
        gitaddress = subfolder_array[0]

    # Check cache before fetching from registry
    module_repo = gitaddress.replace("/", "_")
    module_cache_path = os.path.join(MODULE_DIR, module_repo)

    if os.path.exists(module_cache_path):
        return gitaddress, subfolder, ""

    # Fetch module source URL from registry API
    try:
        r = requests.get(domain + gitaddress, headers=headers)
        resp_json = r.json()
        githubURL = resp_json["source"]
    except Exception:
        click.echo(
            click.style(
                f"\nERROR: Cannot connect to Git Repo and Terraform Enterprise server. "
                f"Check authorisation token, server address and network settings\n\n "
                f"Code: {r.status_code} - {r.reason}",
                fg="red",
                bold=True,
            )
        )
        exit()

    # Fallback to readme source if main source is empty
    if githubURL == "":
        githubURL = handle_readme_source(r)

    # Resolve version constraint to a git tag
    git_tag = ""
    if version_constraint:
        available_versions = resp_json.get("versions", [])
        resolved = _resolve_version_constraint(version_constraint, available_versions)
        if resolved:
            # Fetch the specific version to get its git tag
            try:
                ver_resp = requests.get(
                    domain + gitaddress + "/" + resolved, headers=headers
                )
                ver_tag = ver_resp.json().get("tag", "")
                if ver_tag:
                    git_tag = ver_tag
                    click.echo(
                        f"  Resolved version constraint '{version_constraint}' "
                        f"to {resolved} (tag: {git_tag})"
                    )
            except Exception:
                click.echo(
                    f"  WARNING: Could not resolve version {resolved}, " f"using latest"
                )

    return githubURL, subfolder, git_tag


def clone_specific_folder(repo_url: str, folder_path: str, destination: str) -> str:
    """Clone only a specific folder from a git repository using sparse checkout.

    Uses git sparse checkout to clone only a specific subdirectory from a
    repository, reducing clone time and disk usage for large repositories.

    Args:
        repo_url: Git repository URL
        folder_path: Path to specific folder within repository
        destination: Local destination path

    Returns:
        Normalized repository URL with HTTPS protocol
    """
    # Initialize empty git repository
    repo = git.Repo.init(destination)
    repo_url = "https://" + repo_url if "http" not in repo_url else repo_url

    # Get or create remote origin
    try:
        origin = repo.remote("origin")
    except Exception:
        origin = repo.create_remote("origin", repo_url)

    # Enable sparse checkout in git config
    with repo.config_writer() as config:
        config.set_value("core", "sparseCheckout", "true")

    # Configure which folder to checkout
    sparse_checkout_file = os.path.join(destination, ".git", "info", "sparse-checkout")
    os.makedirs(os.path.dirname(sparse_checkout_file), exist_ok=True)
    with open(sparse_checkout_file, "w") as f:
        f.write(f"{folder_path}/*\n")

    # Fetch and checkout default branch (main or master)
    origin.fetch(depth=1)
    default_branch = (
        "main" if "origin/main" in [ref.name for ref in origin.refs] else "master"
    )
    repo.git.checkout(f"origin/{default_branch}")

    return repo_url


def clone_files(
    sourceURL: str, tempdir: str, module: str = "main", version: str = ""
) -> str:
    """Clone git repository or retrieve from cache.

    Main entry point for retrieving Terraform module code. Checks cache first,
    then clones from remote source if needed. Handles both URL and local paths.

    Args:
        sourceURL: Source URL of the module (git URL, registry URL, or local path)
        tempdir: Temporary directory for cloning
        module: Module name for cache organization (default: "main")
        version: Terraform version constraint (e.g., "~> 5.0")

    Returns:
        Path to cloned module code directory
    """
    click.echo(click.style("\nLoading Sources..", fg="white", bold=True))

    # Parse the URL to extract subfolder before sanitizing
    # This is needed to handle registry modules with subfolders (e.g., module//subfolder)
    githubURL, subfolder, git_tag = get_clone_url(sourceURL, version)

    # Extract the base URL without subfolder (before //) for cache path generation
    # This ensures that modules with subfolders (e.g., module//subfolder) are cached correctly
    base_source_url = sourceURL

    # Handle s3::/gcs:: prefixed URLs (e.g., s3::https://...//subfolder)
    if sourceURL.startswith(("s3::", "gcs::")):
        stripped = sourceURL.split("::", 1)[1]
        if stripped.startswith(("http://", "https://")):
            protocol_end = stripped.find("//") + 2
            remaining = stripped[protocol_end:]
            if "//" in remaining:
                prefix = sourceURL.split("::", 1)[0] + "::"
                base_source_url = (
                    prefix + stripped[:protocol_end] + remaining.split("//", 1)[0]
                )
    # Handle git:: prefixed URLs (e.g., git::https://...//subfolder)
    elif sourceURL.startswith("git::"):
        remaining_after_prefix = sourceURL[5:]  # Remove "git::" prefix
        if remaining_after_prefix.startswith(("http://", "https://", "ssh://")):
            # Protocol-based URL - skip past protocol //, then check for subfolder //
            protocol_end = remaining_after_prefix.find("//") + 2
            after_protocol = remaining_after_prefix[protocol_end:]
            if "//" in after_protocol:
                base_source_url = (
                    "git::"
                    + remaining_after_prefix[:protocol_end]
                    + after_protocol.split("//", 1)[0]
                )
        elif "//" in remaining_after_prefix:
            # SCP-style git URL or other format with subfolder
            base_source_url = "git::" + remaining_after_prefix.split("//", 1)[0]
    elif sourceURL.startswith(("http://", "https://")):
        # For HTTP(S) URLs, find protocol end then check for // in remaining part
        protocol_end = sourceURL.find("//") + 2
        remaining = sourceURL[protocol_end:]
        if "//" in remaining:
            base_source_url = sourceURL[:protocol_end] + remaining.split("//", 1)[0]
    elif "//" in sourceURL:
        # For non-HTTP URLs (registry, etc.), split on //
        base_source_url = sourceURL.split("//", 1)[0]

    # Sanitize repo name for cross-platform filesystem compatibility
    reponame = (
        base_source_url.replace("/", "_")
        .replace("?", "_")
        .replace(":", "_")
        .replace("=", "_")
    )
    codepath = os.path.join(MODULE_DIR, reponame) + f";{module};"

    # Return cached module if it exists
    if os.path.exists(codepath):
        return _handle_cached_module(codepath, tempdir, module, reponame, subfolder)

    # Clone new module
    if module != "main":
        click.echo(f"  Processing External Module named '{module}': {sourceURL}")

    # Determine if source is an HTTP archive, remote URL, or local directory
    if _is_http_archive(sourceURL):
        # HTTP archive (e.g., .tgz, .zip from S3, GCS, or any HTTP server)
        _download_and_extract_archive(githubURL, codepath)
    elif helpers.check_for_domain(str(sourceURL)):
        # Remote source: clone the repository
        _clone_full_repo(githubURL, subfolder, git_tag, codepath)
    else:
        # Local path or registry URL: clone the repository
        _clone_full_repo(githubURL, subfolder, git_tag, codepath)
        click.echo(
            click.style(
                f"  Retrieved code from registry source: {sourceURL}", fg="green"
            )
        )

    return os.path.join(codepath, subfolder)


def _handle_cached_module(
    codepath: str, tempdir: str, module: str, reponame: str, subfolder: str
) -> str:
    """Handle retrieval of cached module.

    Returns path to cached module without re-downloading. Copies to temp
    directory if needed for isolation.

    Args:
        codepath: Path to cached module
        tempdir: Temporary directory for module copies
        module: Module name
        reponame: Repository name
        subfolder: Subfolder path within the module (empty string if none)

    Returns:
        Path to cached module directory including subfolder
    """
    click.echo(
        f"  Skipping download of module {reponame}, "
        f"found existing folder in module cache"
    )

    temp_module_path = os.path.join(tempdir, f";{module};{reponame}")

    # Determine correct module path
    if f";{module};" in codepath and module != "main":
        codepath_module = os.path.join(codepath, module)
        if not os.path.exists(codepath_module):
            codepath_module = codepath
    else:
        codepath_module = codepath

    # Copy to temp directory if not already there
    if not os.path.exists(temp_module_path):
        if not os.path.exists(codepath_module):
            codepath_module = codepath
        shutil.copytree(codepath_module, temp_module_path)

    # When subfolder is specified, navigate from codepath root (matches fresh clone behavior)
    if subfolder:
        return os.path.join(codepath, subfolder)
    return codepath_module


def _clone_full_repo(githubURL: str, subfolder: str, tag: str, codepath: str) -> str:
    """Clone entire repository.

    Performs full git clone of repository with optional branch/tag checkout.
    Displays progress bar during clone operation.

    Args:
        githubURL: Git repository URL
        subfolder: Subfolder path within repository
        tag: Git tag or branch to checkout (empty for default branch)
        codepath: Local destination path for clone

    Returns:
        Subfolder path within cloned repository
    """
    # Parse URL if not already a domain URL
    if not helpers.check_for_domain(githubURL):
        githubURL, subfolder, tag = get_clone_url(githubURL)

    # Helper function for Windows read-only file removal
    def remove_readonly(func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    # Clean existing directory or create new one
    if os.path.exists(codepath):
        shutil.rmtree(codepath, onerror=remove_readonly)
    os.makedirs(codepath, exist_ok=True)

    # Configure clone options
    options: List[str] = []
    if tag:
        options.append("--branch " + tag)

    # Attempt to clone repository
    try:
        git.Repo.clone_from(
            githubURL,
            str(codepath),
            multi_options=options,
            progress=CloneProgress(),
        )
    except Exception as e:
        click.echo(f"Git Error: {type(e).__name__}: {str(e)}\n\n")
        click.echo(
            click.style(
                f"\nERROR: Unable to call Git to clone repository! "
                f"Check git and SSH fingerprints and keys are correct and "
                f"ensure the repo {githubURL} is reachable via the git CLI.",
                fg="red",
                bold=True,
            )
        )
        shutil.rmtree(codepath, ignore_errors=True)
        exit()

    return subfolder
