"""LLM/AI backend integration for TerraVision.

This module provides functions for interacting with AI backends (Ollama, Bedrock)
to refine graph dictionaries using large language models.
"""

import json
import sys
from typing import Any, Dict

import click
import ollama
import requests

import modules.helpers as helpers
from modules.config_loader import load_config
from modules.provider_detector import get_primary_provider_or_default


def check_ollama_server(ollama_host: str) -> None:
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


def check_bedrock_endpoint(bedrock_endpoint: str) -> None:
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


def create_ollama_client(ollama_host: str) -> ollama.Client:
    """Create and return Ollama LLM client.

    Args:
        ollama_host: Ollama server host URL

    Returns:
        Configured Ollama client instance
    """
    return ollama.Client(host=ollama_host, headers={"x-some-header": "some-value"})


def stream_ollama_response(
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


def stream_bedrock_response(
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


def refine_with_llm(
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
    provider = get_primary_provider_or_default(tfdata)
    config = load_config(provider)

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
        client = create_ollama_client(config.OLLAMA_HOST)
        full_response = stream_ollama_response(
            client, tfdata["graphdict"], refinement_prompt, debug
        )
    elif aibackend.lower() == "bedrock":
        full_response = stream_bedrock_response(
            tfdata["graphdict"], refinement_prompt, config.BEDROCK_API_ENDPOINT, debug
        )

    refined_json = helpers.extract_json_from_string(full_response)
    click.echo(click.style("\nFinal LLM Refined JSON:\n", fg="white", bold=True))
    click.echo(json.dumps(refined_json, indent=4, sort_keys=True))
    tfdata["graphdict"] = refined_json
    return tfdata
