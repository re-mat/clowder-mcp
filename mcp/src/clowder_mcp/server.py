"""Clowder MCP Server implementation."""
import sys

import os
import random

from fastmcp import FastMCP
from genson import SchemaBuilder
from pyclowder.client import ClowderClient

mcp = FastMCP("clowder")


def get_clowder_client() -> ClowderClient:
    """Get a configured Clowder client from environment variables."""
    url = os.environ.get("CLOWDER_URL")
    key = os.environ.get("CLOWDER_KEY")
    if not url or not key:
        raise ValueError("CLOWDER_URL and CLOWDER_KEY environment variables must be set")
    return ClowderClient(host=url, key=key)


@mcp.tool()
def hello(name: str) -> str:
    """Say hello to someone.

    Args:
        name: The name to greet.

    Returns:
        A greeting message.
    """
    return f"Hello, {name}!"


@mcp.tool()
def list_spaces() -> list[dict]:
    """List all spaces in the Clowder instance.

    Returns:
        A list of spaces with their details.
    """
    client = get_clowder_client()
    response = client.get("/spaces")
    return response


def _get_datasets_for_space(space_id: str) -> list[str]:
    """Internal helper to get all dataset IDs for a given space."""
    client = get_clowder_client()
    response = client.get(f"/spaces/{space_id}/datasets")
    return [dataset["id"] for dataset in response]


@mcp.tool()
def get_datasets_for_space(space_id: str) -> list[str]:
    """Get all dataset IDs for a given space.

    Args:
        space_id: The ID of the space to get datasets for.

    Returns:
        A list of dataset IDs in the space.
    """
    return _get_datasets_for_space(space_id)


@mcp.tool()
def get_schema_for_space(space_id: str) -> dict:
    """Generate a JSON schema from sampled datasets in a space.

    Samples up to 4 random datasets from the space and uses their
    technical metadata to infer a common schema using GenSON.

    Args:
        space_id: The ID of the space to generate a schema for.

    Returns:
        A JSON schema representing the structure of technical metadata
        found in the sampled datasets.
    """
    dataset_ids = _get_datasets_for_space(space_id)

    if not dataset_ids:
        return {"type": "object", "properties": {}}

    sample_size = min(4, len(dataset_ids))
    sampled_ids = random.sample(dataset_ids, sample_size)

    client = get_clowder_client()
    builder = SchemaBuilder()

    for dataset_id in sampled_ids:
        metadata = client.get(f"/datasets/{dataset_id}/technicalmetadatajson")
        builder.add_object(metadata)

    return builder.to_schema()


@mcp.tool()
def search_datasets_in_space(query: str, space_id: str) -> list[str]:
    """
    Query a clowder space using Clowder proprietary query syntax.

    Args:
        query: A Clowder query string in the form of "fieldName: value:"
               Note that the search-for value is enclosed in colon character

        space_id: The ID of the space to query.

    Query Syntax:
        - Format: "field.name": "value":
        - Use dot notation for nested fields: "parent.child.field": "value":
        - The colon separates the field path (on the left) from the search value (on the right) and terminates the search value
        - Field names with spaces must be quoted: "field name": "value":
        - Multiple conditions can be combined: {"field1": "value1", "field2": "value2"}

    Examples:
        Simple field query:
            "name": "John":

        Nested field with dot notation:
            "user.profile.age": "25":

        Field name with spaces (must be quoted):
            {procedure.general.Operator Initials": "RM":

        Multiple conditions (implicit AND):
            {"status": "active", "department": "sales"}


    Returns:
        Dictionary containing query results with matching documents.

    Note:
        - All field paths and values should be properly quoted as strings
        - Dot notation accesses nested object properties
        - The search value is enclosed in colon character

    Returns:
        A list of URLs pointing to matching datasets in Clowder.
    """
    client = get_clowder_client()

    params = {
        "query": query,
        "spaceid": space_id,
        "resource_type": "dataset",
    }

    response = client.get("/search", params=params)
    results = response.get("results", [])
    assert isinstance(
        results, list
    ), "Expected a list of datasets as the response from Clowder search"

    base_url = os.environ.get("CLOWDER_URL", "").rstrip("/")

    urls = []
    for result in results:
        dataset_id = result.get("id")
        if dataset_id:
            urls.append(f"{base_url}/datasets/{dataset_id}?space={space_id}")

    return urls


if __name__ == "__main__":
    mcp.run()