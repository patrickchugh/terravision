#!/usr/bin/env python
from typing import Any, Dict, List, Optional
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import ollama
import requests
import click

import tomli
import modules.annotations as annotations
import modules.drawing as drawing
import modules.fileparser as fileparser
import modules.graphmaker as graphmaker
import modules.helpers as helpers
import modules.interpreter as interpreter
import modules.tfwrapper as tfwrapper
import modules.resource_handlers as resource_handlers
from modules.config_loader import load_config
from modules.provider_detector import detect_providers, get_primary_provider_or_default
from importlib.metadata import version

# def _get_version() -> str:
# """Read version from pyproject.toml."""
# pyproject_path = Path(__file__).parent / "pyproject.toml"
# with open(pyproject_path, "rb") as f:
#     pyproject = tomli.load(f)
# return pyproject["tool"]["poetry"]["version"]

__version__ = version("terravision")


def _get_provider_config(tfdata: Dict[str, Any]) -> Any:
    """Get provider-specific configuration from tfdata.

    Args:
        tfdata: Terraform data dictionary (may contain provider_detection)

    Returns:
        Provider-specific configuration module
    """
    provider = get_primary_provider_or_default(tfdata)
    return load_config(provider)


def my_excepthook(exc_type: type, exc_value: BaseException, exc_traceback: Any) -> None:
    """Custom exception hook for unhandled errors.

    Args:
        exc_type: Exception type
        exc_value: Exception instance
        exc_traceback: Traceback object
    """
    import traceback

    print(f"Unhandled error: {exc_type}, {exc_value}")
    traceback.print_exception(exc_type, exc_value, exc_traceback)


def _show_banner() -> None:
    """Display TerraVision ASCII banner."""
    banner = (
        "\n\n\n"
        " _____                          _     _             \n"
        "/__   \\___ _ __ _ __ __ ___   _(_)___(_) ___  _ __  \n"
        "  / /\\/ _ \\ '__| '__/ _` \\ \\ / / / __| |/ _ \\| '_ \\ \n"
        " / / |  __/ |  | | | (_| |\\ V /| \\__ \\ | (_) | | | |\n"
        " \\/   \\___|_|  |_|  \\__,_| \\_/ |_|___/_|\\___/|_| |_|\n"
        "                                                    \n"
        "\n"
    )
    print(banner)


def _validate_source(source: List[str]) -> None:
    """Validate source input is not a .tf file.

    Args:
        source: List of source paths

    Raises:
        SystemExit: If source is a .tf file
    """
    if source[0].endswith(".tf"):
        click.echo(
            click.style(
                "\nERROR: You have passed a .tf file as source. Please pass a folder containing .tf files or a git URL.\n",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def _load_json_source(source: str) -> Dict[str, Any]:
    """Load and parse JSON source file.

    Args:
        source: Path to JSON file

    Returns:
        Dictionary containing tfdata with graphdict and metadata
    """
    with open(source, "r") as file:
        jsondata = json.load(file)
    tfdata = {"annotations": {}, "meta_data": {}}
    if "all_resource" in jsondata:
        click.echo(
            "Source appears to be a JSON of previous debug output. Will not call terraform binary."
        )
        tfdata = jsondata
        tfdata["graphdict"] = dict(tfdata["original_graphdict"])
        tfdata["metadata"] = dict(tfdata["original_metadata"])
    else:
        click.echo(
            "Source is a pre-generated JSON tfgraph file. Will not call terraform binary or AI model."
        )
        tfdata["graphdict"] = jsondata
    return tfdata


def _process_terraform_source(
    source: List[str], varfile: List[str], workspace: str, annotate: str, debug: bool
) -> Dict[str, Any]:
    """Process Terraform source files and generate initial tfdata.

    Args:
        source: List of source paths
        varfile: List of variable file paths
        workspace: Terraform workspace name
        annotate: Path to annotations file
        debug: Enable debug mode

    Returns:
        Dictionary containing parsed Terraform data
    """
    tfdata = tfwrapper.tf_initplan(source, varfile, workspace, debug)
    tfdata = tfwrapper.tf_makegraph(tfdata, debug)
    codepath = (
        [tfdata["codepath"]]
        if isinstance(tfdata["codepath"], str)
        else tfdata["codepath"]
    )
    tfdata = fileparser.read_tfsource(codepath, varfile, annotate, tfdata)
    if debug:
        helpers.export_tfdata(tfdata)
    return tfdata


def _enrich_graph_data(
    tfdata: Dict[str, Any], debug: bool, already_processed: bool
) -> Dict[str, Any]:
    """Enrich graph data with relationships and transformations.

    Args:
        tfdata: Terraform data dictionary
        debug: Enable debug mode
        already_processed: Whether data was already processed

    Returns:
        Enriched tfdata dictionary
    """
    tfdata = interpreter.prefix_module_names(tfdata)
    tfdata = interpreter.resolve_all_variables(tfdata, debug, already_processed)
    tfdata = resource_handlers.handle_special_cases(tfdata)
    tfdata = graphmaker.add_relations(tfdata)
    tfdata = graphmaker.consolidate_nodes(tfdata)
    tfdata = annotations.add_annotations(tfdata)
    tfdata = graphmaker.detect_and_set_counts(tfdata)
    tfdata = graphmaker.handle_special_resources(tfdata)
    tfdata = graphmaker.handle_variants(tfdata)
    tfdata = graphmaker.create_multiple_resources(tfdata)
    tfdata = graphmaker.cleanup_cross_subnet_connections(tfdata)
    tfdata = graphmaker.reverse_relations(tfdata)
    tfdata = helpers.remove_recursive_links(tfdata)
    tfdata = resource_handlers.match_resources(tfdata)

    return tfdata


def _print_graph_debug(outputdict: Dict[str, Any], title: str) -> None:
    """Print formatted graph dictionary for debugging.

    Args:
        outputdict: Dictionary to print
        title: Title to display
    """
    click.echo(click.style(f"\n{title}:\n", fg="white", bold=True))
    click.echo(json.dumps(outputdict, indent=4, sort_keys=True))


def compile_tfdata(
    source: List[str],
    varfile: List[str],
    workspace: str,
    debug: bool,
    annotate: str = "",
) -> Dict[str, Any]:
    """Compile Terraform data from source files into enriched graph dictionary.

    Args:
        source: List of source paths (folders, git URLs, or JSON files)
        varfile: List of paths to .tfvars files
        workspace: Terraform workspace name
        debug: Enable debug output and export tracedata
        annotate: Path to custom annotations YAML file

    Returns:
        Enriched tfdata dictionary with graphdict and metadata
    """
    _validate_source(source)
    already_processed = False
    if source[0].endswith(".json"):
        tfdata = _load_json_source(source[0])
        already_processed = True
        if "all_resource" not in tfdata:
            _print_graph_debug(tfdata["graphdict"], "Loaded JSON graphviz dictionary")
    else:
        tfdata = _process_terraform_source(source, varfile, workspace, annotate, debug)

    # Detect cloud provider and store in tfdata (multi-cloud support)
    if "all_resource" in tfdata and "provider_detection" not in tfdata:
        try:
            provider_detection = detect_providers(tfdata)
            tfdata["provider_detection"] = provider_detection
            click.echo(
                click.style(
                    f"\nDetected cloud provider: {provider_detection['primary_provider'].upper()} "
                    f"({provider_detection['resource_counts'][provider_detection['primary_provider']]} resources)\n",
                    fg="cyan",
                    bold=True,
                )
            )
        except Exception as e:
            click.echo(
                click.style(
                    f"\nERROR: Failed to detect cloud provider: {e}",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()

    if "all_resource" in tfdata:
        _print_graph_debug(tfdata["graphdict"], "Terraform JSON graph dictionary")
        tfdata = _enrich_graph_data(tfdata, debug, already_processed)
        tfdata["graphdict"] = helpers.sort_graphdict(tfdata["graphdict"])
        _print_graph_debug(tfdata["graphdict"], "Enriched graphviz dictionary")
    return tfdata


def _check_dependencies() -> None:
    """Check if required command-line tools are available."""
    dependencies = ["dot", "gvpr", "git", "terraform"]
    bundle_dir = Path(__file__).parent
    sys.path.append(str(bundle_dir))
    for exe in dependencies:
        location = shutil.which(exe) or os.path.isfile(exe)
        if location:
            click.echo(f"  {exe} command detected: {location}")
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: {exe} command executable not detected in path. Please ensure you have installed all required dependencies first",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()


def _check_terraform_version() -> None:
    """Validate Terraform version is compatible."""
    version_file = "terraform_version.txt"

    try:
        result = subprocess.run(
            ["terraform", "-v"], capture_output=True, text=True, check=True
        )
        version_output = result.stdout

        version_line = version_output.split("\n")[0]
        print(f"  terraform version detected: {version_line}")
        version = version_line.split(" ")[1].replace("v", "")
        version_major = version.split(".")[0]

        if version_major != "1":
            click.echo(
                click.style(
                    f"\n  ERROR: Terraform Version '{version}' is not supported. Please upgrade to >= v1.0.0",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except (subprocess.CalledProcessError, IndexError, FileNotFoundError) as e:
        click.echo(
            click.style(
                f"\n  ERROR: Failed to check Terraform version: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def _check_ollama_server(ollama_host: str) -> None:
    """Check if Ollama server is reachable.

    Args:
        ollama_host: Ollama server host URL
    """
    click.echo("  checking Ollama server..")
    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            click.echo(f"  Ollama server reachable at: {ollama_host}")
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: Ollama server returned status {response.status_code}",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(
                f"\n  ERROR: Cannot reach Ollama server at {ollama_host}: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def _create_ollama_client(ollama_host: str) -> ollama.Client:
    """Create and return Ollama LLM client.

    Args:
        ollama_host: Ollama server host URL

    Returns:
        Configured Ollama client instance
    """
    return ollama.Client(host=ollama_host, headers={"x-some-header": "some-value"})


def _stream_ollama_llm_response(
    client: ollama.Client,
    graphdict: Dict[str, Any],
    refinement_prompt: str,
    debug: bool,
) -> str:
    """Stream LLM response and return complete output.

    Args:
        client: Ollama client instance
        graphdict: Graph dictionary to refine
        refinement_prompt: Provider-specific refinement prompt
        debug: Enable debug explanations

    Returns:
        Complete LLM response string
    """
    stream = client.chat(
        model="llama3",
        keep_alive=-1,
        messages=[
            {
                "role": "user",
                "content": refinement_prompt
                + (
                    "Explain why you made every change after outputting the refined JSON\n"
                    if debug
                    else "Return ONLY the corrected JSON in the same format, with no additional explanation."
                )
                + str(graphdict),
            }
        ],
        options={"temperature": 0, "seed": 42, "top_p": 1.0, "top_k": 1},
        stream=True,
    )
    full_response = ""
    for chunk in stream:
        content = chunk["message"]["content"]
        print(content, end="", flush=True)
        full_response += content
    return full_response


def _stream_bedrock_response(
    graphdict: Dict[str, Any],
    refinement_prompt: str,
    bedrock_endpoint: str,
    debug: bool,
) -> str:
    """Stream Bedrock API response and return complete output.

    Args:
        graphdict: Graph dictionary to refine
        refinement_prompt: Provider-specific refinement prompt
        bedrock_endpoint: Bedrock API Gateway endpoint URL
        debug: Enable debug explanations

    Returns:
        Complete Bedrock API response string
    """

    payload = {
        "messages": [
            {
                "role": "user",
                "content": refinement_prompt
                + (
                    "Explain why you made every change after outputting the refined JSON\n"
                    if debug
                    else "Return ONLY the corrected JSON in the same format, with no additional explanation."
                )
                + str(graphdict),
            }
        ],
        "max_tokens": 10000,
    }

    response = requests.post(
        bedrock_endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        stream=True,
        timeout=300,
    )
    full_response = ""
    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            print(chunk, end="", flush=True)
            full_response += chunk
    return full_response


def _refine_with_llm(
    tfdata: Dict[str, Any], aibackend: str, debug: bool
) -> Dict[str, Any]:
    """Refine graph dictionary using LLM and return updated tfdata.

    Args:
        tfdata: Terraform data dictionary
        aibackend: AI backend to use ('ollama' or 'bedrock')
        debug: Enable debug mode

    Returns:
        Updated tfdata with refined graphdict
    """
    # Get provider-specific configuration
    config = _get_provider_config(tfdata)
    provider = get_primary_provider_or_default(tfdata)

    # Get provider-specific refinement prompt
    refinement_prompt_attr = f"{provider.upper()}_REFINEMENT_PROMPT"
    refinement_prompt = getattr(
        config, refinement_prompt_attr, config.AWS_REFINEMENT_PROMPT
    )

    click.echo(
        click.style(
            f"\nCalling {aibackend.capitalize()} AI Model for {provider.upper()} diagram refinement..\n",
            fg="white",
            bold=True,
        )
    )

    if aibackend.lower() == "ollama":
        client = _create_ollama_client(config.OLLAMA_HOST)
        full_response = _stream_ollama_llm_response(
            client, tfdata["graphdict"], refinement_prompt, debug
        )
    elif aibackend.lower() == "bedrock":
        full_response = _stream_bedrock_response(
            tfdata["graphdict"], refinement_prompt, config.BEDROCK_API_ENDPOINT, debug
        )

    refined_json = helpers.extract_json_from_string(full_response)
    _print_graph_debug(refined_json, "Final LLM Refined JSON")
    tfdata["graphdict"] = refined_json
    return tfdata


def _check_bedrock_endpoint(bedrock_endpoint: str) -> None:
    """Check if Bedrock API endpoint is reachable.

    Args:
        bedrock_endpoint: Bedrock API Gateway endpoint URL
    """
    click.echo("  checking Bedrock API Gateway endpoint..")
    try:
        response = requests.get(bedrock_endpoint, timeout=5, stream=True)
        if response.status_code in [200, 403, 404]:
            click.echo(f"  Bedrock API Gateway reachable at: {bedrock_endpoint}")
            if response.status_code == 200:
                response.close()
        else:
            click.echo(
                click.style(
                    f"\n  ERROR: Bedrock API Gateway returned status {response.status_code}",
                    fg="red",
                    bold=True,
                )
            )
            sys.exit()
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(
                f"\n  ERROR: Cannot reach Bedrock API Gateway endpoint at {bedrock_endpoint}: {e}",
                fg="red",
                bold=True,
            )
        )
        sys.exit()


def preflight_check(aibackend: Optional[str] = None) -> None:
    """Check required dependencies and Terraform version compatibility.

    Args:
        aibackend: AI backend to validate ('ollama' or 'bedrock')
    """
    click.echo(click.style("\nPreflight check..", fg="white", bold=True))
    _check_dependencies()
    _check_terraform_version()

    if aibackend:
        # Load default AWS config for preflight (endpoints are the same across providers)
        default_config = load_config("aws")

        if aibackend.lower() == "ollama":
            _check_ollama_server(default_config.OLLAMA_HOST)
        elif aibackend.lower() == "bedrock":
            _check_bedrock_endpoint(default_config.BEDROCK_API_ENDPOINT)

    click.echo("\n")


@click.version_option(version=__version__, prog_name="terravision")
@click.group()
def cli() -> None:
    """TerraVision generates cloud architecture diagrams and documentation from Terraform scripts.

    For help with a specific command type:
    terravision [COMMAND] --help
    """
    pass


@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL, Folder or .JSON file)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile",
    multiple=True,
    default=[],
    help="Path to .tfvars variables file",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output diagram (default architecture.dot.png)",
)
@click.option(
    "--format", default="png", help="Output format(png, svg, pdf, jpg, dot etc.)"
)
@click.option(
    "--show", is_flag=True, default=False, help="Show diagram after generation"
)
@click.option(
    "--simplified",
    is_flag=True,
    default=False,
    help="Simplified high level services shown only",
)
@click.option("--annotate", default="", help="Path to custom annotations file (YAML)")
@click.option(
    "--aibackend",
    default="",
    type=click.Choice(["", "bedrock", "ollama"], case_sensitive=False),
    help="AI backend to use (bedrock or ollama)",
)
@click.option("--avl_classes", hidden=True)
def draw(
    debug: bool,
    source: tuple,
    workspace: str,
    varfile: tuple,
    outfile: str,
    format: str,
    show: bool,
    simplified: bool,
    annotate: str,
    aibackend: str,
    avl_classes: Any,
) -> None:
    """Draw architecture diagram from Terraform code.

    Args:
        debug: Enable debug mode
        source: Source paths tuple
        workspace: Terraform workspace
        varfile: Variable files tuple
        outfile: Output filename
        format: Output format (any Graphviz format: png, svg, pdf, jpg, etc.)
        show: Show diagram after generation
        simplified: Generate simplified diagram
        annotate: Path to annotations file
        aibackend: AI backend to use
        avl_classes: Available classes (hidden)
    """
    if not debug:
        sys.excepthook = my_excepthook
    _show_banner()
    preflight_check(aibackend)
    tfdata = compile_tfdata(source, varfile, workspace, debug, annotate)
    # Pass to LLM if this is not a pregraphed JSON
    if "all_resource" in tfdata and aibackend:
        tfdata = _refine_with_llm(tfdata, aibackend, debug)

    # Add provider suffix to output filename for non-AWS providers
    final_outfile = outfile
    if tfdata.get("provider_detection"):
        provider = tfdata["provider_detection"].get("primary_provider", "aws")
        if provider != "aws" and not outfile.endswith(f"-{provider}"):
            final_outfile = f"{outfile}-{provider}"

    drawing.render_diagram(tfdata, show, simplified, final_outfile, format, source)


@cli.command()
@click.option("--debug", is_flag=True, default=False, help="Dump exception tracebacks")
@click.option(
    "--source",
    multiple=True,
    default=["."],
    help="Source files location (Git URL or folder)",
)
@click.option(
    "--workspace",
    multiple=False,
    default="default",
    help="The Terraform workspace to initialise",
)
@click.option(
    "--varfile", multiple=True, default=[], help="Path to .tfvars variables file"
)
@click.option(
    "--show_services",
    is_flag=True,
    default=False,
    help="Only show unique list of cloud services actually used",
)
@click.option(
    "--outfile",
    default="architecture",
    help="Filename for output list (default architecture.json)",
)
@click.option("--annotate", default="", help="Path to custom annotations file (YAML)")
@click.option(
    "--aibackend",
    # type=click.Choice(["bedrock", "ollama"], case_sensitive=False),
    help="AI backend to use (bedrock or ollama)",
)
@click.option("--avl_classes", hidden=True)
def graphdata(
    debug: bool,
    source: tuple,
    varfile: tuple,
    workspace: str,
    show_services: bool,
    annotate: str,
    aibackend: str,
    avl_classes: Any,
    outfile: str = "graphdata.json",
) -> None:
    """List cloud resources and relations as JSON.

    Args:
        debug: Enable debug mode
        source: Source paths tuple
        varfile: Variable files tuple
        workspace: Terraform workspace
        show_services: Show only unique services
        annotate: Path to annotations file
        aibackend: AI backend to use
        avl_classes: Available classes (hidden)
        outfile: Output JSON filename
    """
    if not debug:
        sys.excepthook = my_excepthook
    _show_banner()
    preflight_check(aibackend)
    tfdata = compile_tfdata(source, varfile, workspace, debug, annotate)
    # Pass to LLM if this is not a pregraphed JSON
    if "all_resource" in tfdata and aibackend and (not show_services):
        tfdata = _refine_with_llm(tfdata, aibackend, debug)
    click.echo(click.style("\nFinal Output JSON Dictionary :", fg="white", bold=True))
    unique = helpers.unique_services(tfdata["graphdict"])
    click.echo(
        json.dumps(
            tfdata["graphdict"] if not show_services else unique,
            indent=4,
            sort_keys=True,
        )
    )
    if not outfile.endswith(".json"):
        outfile += ".json"
    click.echo(f"\nExporting graph object into file {outfile}")
    with open(outfile, "w") as f:
        json.dump(
            tfdata["graphdict"] if not show_services else unique,
            f,
            indent=4,
            sort_keys=True,
        )
    click.echo("\nCompleted!")


def main():
    cli(
        default_map={
            "draw": {"avl_classes": dir()},
            "graphdata": {"avl_classes": dir()},
        }
    )


if __name__ == "__main__":
    main()
