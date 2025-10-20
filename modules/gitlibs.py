import os
import re
import shutil
import tempfile
from pathlib import Path
from sys import exit
from urllib.parse import urlparse
import modules.helpers as helpers
import click
import git
import requests
from git import RemoteProgress
from tqdm import tqdm

from modules.helpers import *

# Create Tempdir and Module Cache Directories
all_repos = list()
annotations = dict()
# temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
MODULE_DIR = str(Path(Path.home(), ".terravision", "module_cache"))
if not os.path.exists(MODULE_DIR):
    os.makedirs(MODULE_DIR)


class CloneProgress(RemoteProgress):
    def __init__(self):
        super().__init__()
        self.pbar = tqdm(leave=False)

    def update(self, op_code, cur_count, max_count=None, message=""):
        self.pbar.total = max_count
        self.pbar.n = cur_count
        self.pbar.refresh()


def handle_readme_source(resp) -> str:
    """Extract and convert git URL from Bitbucket API response.

    Args:
        resp: HTTP response containing readme with git URL

    Returns:
        Formatted SSH git URL
    """
    readme = resp.json()["root"]["readme"]
    githubURL = "ssh://git@" + find_between(readme, "(https://", ")")

    # Convert domain format for SSH
    found = re.findall("\.........\.net", githubURL)
    for site in found:
        githubURL = githubURL.replace(site, "-ssh" + site)

    # Convert Bitbucket URL format to git SSH format
    githubURL = githubURL.replace("/projects/", ":7999/")
    githubURL = githubURL.replace("/repos/", "/")
    startindex = githubURL.index("/browse?")
    githubURL = githubURL[0:startindex] + ".git"

    return githubURL


def get_clone_url(sourceURL: str):
    """Parse source URL and extract git clone URL, subfolder, and tag.

    Args:
        sourceURL: Source URL in various formats (git::, registry, or direct URL)

    Returns:
        Tuple of (git_url, subfolder, git_tag)
    """
    gitaddress = ""
    subfolder = ""
    git_tag = ""

    # Handle git:: prefixed URLs
    is_git_prefix = (
        sourceURL.startswith("git::ssh://")
        or sourceURL.startswith("git@git")
        or "git::" in sourceURL
    )
    if is_git_prefix:
        return _handle_git_prefix_url(sourceURL)

    # Handle direct domain URLs
    if helpers.check_for_domain(sourceURL):
        return _handle_domain_url(sourceURL)

    # Handle Terraform Registry or plain HTTP Module URLs
    return _handle_registry_url(sourceURL)


def _handle_git_prefix_url(sourceURL: str):
    """Handle URLs with git:: prefix."""
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
    gitaddress = gitaddress.replace("git@github.com/", "git@github.com:")
    gitaddress = gitaddress.replace("git@gitlab.com/", "git@gitlab.com:")

    # Extract subfolder if present
    has_subfolder = "//" in gitaddress and not gitaddress.startswith("https://")
    if has_subfolder:
        subfolder_array = gitaddress.split("//")
        subfolder = subfolder_array[1].split("?")[0]
        gitaddress = subfolder_array[0]
    elif "?ref" in gitaddress:
        gitaddress = gitaddress.split("?ref=")[0]
        git_tag = sourceURL.split("?ref=")[1]

    return gitaddress, subfolder, git_tag


def _handle_domain_url(sourceURL: str):
    """Handle direct domain URLs."""
    subfolder = ""
    git_tag = ""

    # Extract git tag if present
    if "?ref" in sourceURL:
        git_tag = sourceURL.split("?ref=")[1]
        sourceURL = sourceURL.split("?ref=")[0]

    # Handle subfolder in URL
    if sourceURL.count("//") > 1:
        subfolder_array = sourceURL.split("//")
        subfolder = subfolder_array[2].split("?")[0]
        githubURL = subfolder_array[0] + "//" + subfolder_array[1]
    else:
        githubURL = "https://" + sourceURL if "http" not in sourceURL else sourceURL

    return githubURL, subfolder, git_tag


def _handle_registry_url(sourceURL: str):
    """Handle Terraform Registry Module URLs."""
    gitaddress = sourceURL
    subfolder = ""
    headers = ""

    # Determine registry domain and setup authentication
    if check_for_domain(sourceURL):
        domain = urlparse("https://" + sourceURL).netloc
        registrypath = sourceURL.split(domain)
        gitaddress = registrypath[1]
        domain = "https://" + domain + "/api/registry/v1/modules/"
        click.echo(f"    Assuming Terraform Enterprise API Server URL: {domain}")

        if "TFE_TOKEN" not in os.environ:
            click.echo(
                click.style(
                    "\nERROR: No TFE_TOKEN environment variable set. Unable to authorise with Terraform Enterprise Server",
                    fg="red",
                    bold=True,
                )
            )
            exit()

        headers = {"Authorization": "bearer " + os.environ["TFE_TOKEN"]}
    else:
        domain = "https://registry.terraform.io/v1/modules/"

    # Extract subfolder if present
    if sourceURL.count("//") >= 1:
        subfolder_array = sourceURL.split("//")
        subfolder = subfolder_array[1].split("?")[0]
        gitaddress = subfolder_array[0]

    # Fetch git URL from registry or use cached path
    module_repo = gitaddress.replace("/", "_")
    module_cache_path = os.path.join(MODULE_DIR, module_repo)

    if os.path.exists(module_cache_path):
        return gitaddress, subfolder, ""

    try:
        r = requests.get(domain + gitaddress, headers=headers)
        githubURL = r.json()["source"]
    except:
        click.echo(
            click.style(
                f"\nERROR: Cannot connect to Git Repo and Terraform Enterprise server. Check authorisation token, server address and network settings\n\n Code: {r.status_code} - {r.reason}",
                fg="red",
                bold=True,
            )
        )
        exit()

    if githubURL == "":
        githubURL = handle_readme_source(r)

    return githubURL, subfolder, ""


def clone_specific_folder(repo_url: str, folder_path: str, destination: str):
    """Clone only a specific folder from a git repository using sparse checkout.

    Args:
        repo_url: Git repository URL
        folder_path: Path to specific folder within repository
        destination: Local destination path

    Returns:
        Normalized repository URL
    """
    repo = git.Repo.init(destination)
    repo_url = "https://" + repo_url if "http" not in repo_url else repo_url
    try:
        origin = repo.remote("origin")
    except:
        origin = repo.create_remote("origin", repo_url)

    # Enable sparse checkout
    with repo.config_writer() as config:
        config.set_value("core", "sparseCheckout", "true")

    # Specify the folder to checkout
    sparse_checkout_file = os.path.join(destination, ".git", "info", "sparse-checkout")
    os.makedirs(os.path.dirname(sparse_checkout_file), exist_ok=True)
    with open(sparse_checkout_file, "w") as f:
        f.write(f"{folder_path}/*\n")

    # Fetch and checkout default branch
    origin.fetch(depth=1)
    default_branch = (
        "main" if "origin/main" in [ref.name for ref in origin.refs] else "master"
    )
    repo.git.checkout(f"origin/{default_branch}")

    return repo_url


def clone_files(sourceURL: str, tempdir: str, module="main"):
    """Clone git repository or retrieve from cache.

    Args:
        sourceURL: Source URL of the module
        tempdir: Temporary directory for cloning
        module: Module name (default: "main")

    Returns:
        Path to cloned module code
    """
    click.echo(click.style("\nLoading Sources..", fg="white", bold=True))

    # Sanitize repo name for Windows compatibility
    reponame = (
        sourceURL.replace("/", "_")
        .replace("?", "_")
        .replace(":", "_")
        .replace("=", "_")
    )
    codepath = os.path.join(MODULE_DIR, reponame) + f";{module};"

    # Return cached module if exists
    if os.path.exists(codepath) and module != "main":
        return _handle_cached_module(codepath, tempdir, module, reponame)

    # Clone new module
    if module != "main":
        click.echo(f"  Processing External Module named '{module}': {sourceURL}")

    # Check if there is a subfolder element in sourceURL
    gitelements = helpers.extract_subfolder_from_repo(sourceURL)
    # Clone entire repo if no subfolder specified
    if gitelements[0] == sourceURL:
        subfolder = _clone_full_repo(sourceURL, codepath)
    else:
        if helpers.check_for_domain(str(sourceURL)):
            sourceURL = get_clone_url(sourceURL)[0]
        # Clone specific subfolder only
        subfolder = gitelements[1]
        clone_specific_folder(gitelements[0], subfolder, codepath)
        click.echo(
            click.style(
                f"  Retrieved code from registry source: {sourceURL}", fg="green"
            )
        )

    return os.path.join(codepath, subfolder)


def _handle_cached_module(codepath: str, tempdir: str, module: str, reponame: str):
    """Handle retrieval of cached module."""
    click.echo(
        f"  Skipping download of module {reponame}, found existing folder in module cache"
    )
    temp_module_path = os.path.join(tempdir, f";{module};{reponame}")
    if f";{module};" in codepath and module != "main":
        codepath_module = os.path.join(codepath, module)
    else:
        codepath_module = codepath
    if not os.path.exists(temp_module_path):
        if not os.path.exists(codepath_module):
            codepath_module = codepath
            shutil.copytree(codepath_module, temp_module_path)
    return os.path.join(temp_module_path, "")


def _clone_full_repo(sourceURL: str, codepath: str):
    """Clone entire repository."""
    githubURL, subfolder, tag = get_clone_url(sourceURL)
    os.makedirs(codepath)

    options = []
    if tag:
        options.append("--branch " + tag)

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
                f"\nERROR: Unable to call Git to clone repository! Check git and SSH fingerprints and keys are correct and ensure the repo {githubURL} is reachable via the git CLI.",
                fg="red",
                bold=True,
            )
        )
        shutil.rmtree(codepath, ignore_errors=True)
        exit()

    return subfolder
