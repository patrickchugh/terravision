"""Git library module for TerraVision.

This module handles cloning and caching of Terraform modules from various sources
including Git repositories (GitHub, GitLab, Bitbucket), Terraform Registry, and
Terraform Enterprise. Supports SSH, HTTPS, and registry URL formats.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from sys import exit
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urlparse
import stat
import click
import git
import requests
from git import RemoteProgress
from tqdm import tqdm

import modules.helpers as helpers
from modules.helpers import *

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


def get_clone_url(sourceURL: str) -> Tuple[str, str, str]:
    """Parse source URL and extract git clone URL, subfolder, and tag.

    Determines URL type and delegates to appropriate handler function.
    Supports git::, direct domain URLs, and Terraform Registry URLs.

    Args:
        sourceURL: Source URL in various formats (git::, registry, or direct URL)

    Returns:
        Tuple of (git_url, subfolder, git_tag)
    """
    # Check for git:: prefix (SSH or HTTPS git URLs)
    is_git_prefix = (
        sourceURL.startswith("git::ssh://")
        or sourceURL.startswith("git@git")
        or "git::" in sourceURL
    )
    if is_git_prefix:
        return _handle_git_prefix_url(sourceURL)

    # Check for direct domain URLs (GitHub, GitLab, etc.)
    if helpers.check_for_domain(sourceURL):
        return _handle_domain_url(sourceURL)

    # Default to Terraform Registry or plain HTTP Module URLs
    return _handle_registry_url(sourceURL)


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

    # Extract git address based on prefix type
    if "ssh://" in sourceURL:
        split_array = sourceURL.split("git::ssh://")
    elif "git::http" in sourceURL:
        split_array = sourceURL.split("git::")
    else:
        split_array = sourceURL.split("git::")

    gitaddress = split_array[-1]

    # Normalize GitHub and GitLab SSH URLs
    gitaddress = gitaddress.replace("git@github.com/", "git@github.com:")
    gitaddress = gitaddress.replace("git@gitlab.com/", "git@gitlab.com:")

    # Extract subfolder if present (indicated by //)
    has_subfolder = "//" in gitaddress and not gitaddress.startswith("https://")
    if has_subfolder:
        subfolder_array = gitaddress.split("//")
        subfolder = subfolder_array[1].split("?")[0]
        gitaddress = subfolder_array[0]
    elif "?ref" in gitaddress:
        # Extract git tag/branch reference
        gitaddress = gitaddress.split("?ref=")[0]
        git_tag = sourceURL.split("?ref=")[1]

    return gitaddress, subfolder, git_tag


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


def _handle_registry_url(sourceURL: str) -> Tuple[str, str, str]:
    """Handle Terraform Registry Module URLs.

    Resolves Terraform Registry or Terraform Enterprise module URLs to their
    underlying git repository URLs. Handles authentication for private registries.

    Args:
        sourceURL: Terraform Registry module URL

    Returns:
        Tuple of (github_url, subfolder, git_tag)
    """
    gitaddress = sourceURL
    subfolder = ""
    headers: Dict[str, str] = {}

    # Determine if using Terraform Enterprise or public registry
    if check_for_domain(sourceURL):
        # Terraform Enterprise private registry
        domain = urlparse("https://" + sourceURL).netloc
        registrypath = sourceURL.split(domain)
        gitaddress = registrypath[1]
        domain = "https://" + domain + "/api/registry/v1/modules/"
        click.echo(f"    Assuming Terraform Enterprise API Server URL: {domain}")

        # Require authentication token for private registry
        if "TFE_TOKEN" not in os.environ:
            click.echo(
                click.style(
                    "\nERROR: No TFE_TOKEN environment variable set. "
                    "Unable to authorise with Terraform Enterprise Server",
                    fg="red",
                    bold=True,
                )
            )
            exit()

        headers = {"Authorization": "bearer " + os.environ["TFE_TOKEN"]}
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
        githubURL = r.json()["source"]
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

    return githubURL, subfolder, ""


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


def clone_files(sourceURL: str, tempdir: str, module: str = "main") -> str:
    """Clone git repository or retrieve from cache.

    Main entry point for retrieving Terraform module code. Checks cache first,
    then clones from remote source if needed. Handles both URL and local paths.

    Args:
        sourceURL: Source URL of the module (git URL, registry URL, or local path)
        tempdir: Temporary directory for cloning
        module: Module name for cache organization (default: "main")

    Returns:
        Path to cloned module code directory
    """
    click.echo(click.style("\nLoading Sources..", fg="white", bold=True))

    # Sanitize repo name for cross-platform filesystem compatibility
    reponame = (
        sourceURL.replace("/", "_")
        .replace("?", "_")
        .replace(":", "_")
        .replace("=", "_")
    )
    codepath = os.path.join(MODULE_DIR, reponame) + f";{module};"

    # Return cached module if it exists
    if os.path.exists(codepath) and module != "main":
        return _handle_cached_module(codepath, tempdir, module, reponame)

    # Clone new module
    if module != "main":
        click.echo(f"  Processing External Module named '{module}': {sourceURL}")

    # Determine if source is remote URL or local directory
    if helpers.check_for_domain(str(sourceURL)):
        # Remote source: parse URL and clone
        githubURL, subfolder, git_tag = get_clone_url(sourceURL)
        _clone_full_repo(githubURL, subfolder, git_tag, codepath)
    else:
        # Local path: extract subfolder and copy
        gitelements = helpers.extract_subfolder_from_repo(sourceURL)
        subfolder = gitelements[1]
        _clone_full_repo(sourceURL, subfolder, "", codepath)
        click.echo(
            click.style(
                f"  Retrieved code from registry source: {sourceURL}", fg="green"
            )
        )

    return os.path.join(codepath, subfolder)


def _handle_cached_module(
    codepath: str, tempdir: str, module: str, reponame: str
) -> str:
    """Handle retrieval of cached module.

    Returns path to cached module without re-downloading. Copies to temp
    directory if needed for isolation.

    Args:
        codepath: Path to cached module
        tempdir: Temporary directory for module copies
        module: Module name
        reponame: Repository name

    Returns:
        Path to cached module directory
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

    return os.path.join(codepath_module, "")


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
