"""Clowder MCP Server implementation."""

import os

from fastmcp import FastMCP
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


if __name__ == "__main__":
    mcp.run()