"""Clowder MCP Server implementation."""

import os
import random
from typing import Any

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


def _safe_get(client: ClowderClient, path: str, params: dict | None = None) -> Any:
    """Perform a GET request and raise a clear RuntimeError on failure."""
    try:
        return client.get(path, params=params) if params else client.get(path)
    except Exception as exc:
        raise RuntimeError(f"Clowder API request failed for {path!r}: {exc}") from exc


# ---------------------------------------------------------------------------
# Spaces
# ---------------------------------------------------------------------------


@mcp.tool()
def list_spaces() -> list[dict]:
    """List all spaces in the Clowder instance.

    Returns:
        A list of spaces, each containing id, name, description, and other details.
    """
    client = get_clowder_client()
    result = _safe_get(client, "/spaces")
    if not isinstance(result, list):
        raise RuntimeError(f"Expected a list from /spaces, got {type(result).__name__}")
    return result


@mcp.tool()
def find_space_by_name(name: str) -> list[dict]:
    """Find spaces whose name contains the given string (case-insensitive).

    Args:
        name: A substring to search for in space names.

    Returns:
        A list of matching spaces with their id, name, and description.
    """
    client = get_clowder_client()
    spaces = _safe_get(client, "/spaces")
    if not isinstance(spaces, list):
        raise RuntimeError(f"Expected a list from /spaces, got {type(spaces).__name__}")
    name_lower = name.lower()
    return [s for s in spaces if name_lower in s.get("name", "").lower()]


@mcp.tool()
def get_space(space_id: str) -> dict:
    """Get details of a specific space.

    Args:
        space_id: The ID of the space.

    Returns:
        A dict containing id, name, description, created date, dataset count, etc.
    """
    client = get_clowder_client()
    return _safe_get(client, f"/spaces/{space_id}")


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


def _get_datasets_for_space(space_id: str) -> list[dict]:
    """Internal helper: return full dataset objects for a space."""
    client = get_clowder_client()
    result = _safe_get(client, f"/spaces/{space_id}/datasets")
    if not isinstance(result, list):
        raise RuntimeError(
            f"Expected a list from /spaces/{space_id}/datasets, got {type(result).__name__}"
        )
    return result


@mcp.tool()
def list_datasets_in_space(space_id: str) -> list[dict]:
    """List all datasets in a space with their name, id, description, and dates.

    Args:
        space_id: The ID of the space.

    Returns:
        A list of dataset summaries (id, name, description, created).
    """
    datasets = _get_datasets_for_space(space_id)
    return [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "description": d.get("description"),
            "created": d.get("created"),
        }
        for d in datasets
    ]


@mcp.tool()
def get_dataset(dataset_id: str) -> dict:
    """Get details of a specific dataset.

    Args:
        dataset_id: The ID of the dataset.

    Returns:
        A dict containing id, name, description, author, created dates,
        file count, space memberships, tags, and other dataset-level fields.
    """
    client = get_clowder_client()
    return _safe_get(client, f"/datasets/{dataset_id}")


@mcp.tool()
def get_dataset_metadata(dataset_id: str) -> list[dict]:
    """Get user-defined metadata attached to a dataset.

    Returns all metadata records including content and provenance (who added it,
    when, and via which extractor).

    Args:
        dataset_id: The ID of the dataset.

    Returns:
        A list of metadata records. Each record has 'content' (the domain-specific data)
        and provenance fields (id, attached_to, created_at, agent).
    """
    client = get_clowder_client()
    result = _safe_get(client, f"/datasets/{dataset_id}/metadata.jsonld")
    if not isinstance(result, list):
        raise RuntimeError(
            f"Expected a list from metadata.jsonld for dataset {dataset_id!r}, "
            f"got {type(result).__name__}"
        )
    return result


@mcp.tool()
def get_dataset_files(dataset_id: str) -> list[dict]:
    """List the files contained in a dataset.

    Args:
        dataset_id: The ID of the dataset.

    Returns:
        A list of file summaries, each containing id, filename, size,
        content type, date uploaded, and author.
    """
    client = get_clowder_client()
    files = _safe_get(client, f"/datasets/{dataset_id}/files")
    if not isinstance(files, list):
        raise RuntimeError(
            f"Expected a list from /datasets/{dataset_id}/files, got {type(files).__name__}"
        )
    return [
        {
            "id": f.get("id"),
            "filename": f.get("filename"),
            "size": f.get("size"),
            "contentType": f.get("contentType"),
            "date-created": f.get("date-created"),
            "authorId": f.get("authorId"),
        }
        for f in files
    ]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _search_in_space(
    query: str,
    space_id: str,
    resource_type: str | None = "dataset",
    field: str | None = None,
    from_index: int = 0,
    size: int = 20,
) -> dict:
    client = get_clowder_client()

    params: dict[str, Any] = {
        "query": query,
        "spaceid": space_id,
        "from": from_index,
        "size": size,
    }
    if resource_type is not None:
        params["resource_type"] = resource_type
    if field is not None:
        params["field"] = field

    response = _safe_get(client, "/search", params=params)

    if not isinstance(response, dict):
        raise RuntimeError(
            f"Expected a dict from /search, got {type(response).__name__}: {response!r}"
        )

    raw_results = response.get("results", [])
    if not isinstance(raw_results, list):
        raise RuntimeError(
            f"Expected 'results' to be a list, got {type(raw_results).__name__}"
        )

    base_url = os.environ.get("CLOWDER_URL", "").rstrip("/")

    results = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "description": r.get("description", ""),
            "created": r.get("created"),
            "spaces": r.get("spaces", []),
            "url": f"{base_url}/datasets/{r.get('id')}",
        }
        for r in raw_results
        if r.get("id")
    ]

    return {
        "total_size": response.get("total_size", len(results)),
        "count": len(results),
        "from_index": from_index,
        "results": results,
    }


@mcp.tool()
def search_in_space(
    query: str,
    space_id: str,
    resource_type: str | None = "dataset",
    field: str | None = None,
    from_index: int = 0,
    size: int = 20,
) -> dict:
    """Search resources in a space using full-text keyword search backed by ElasticSearch.

    The Clowder search indexes all text fields including names, descriptions,
    and all metadata content. Use plain keywords or domain-specific terms.

    Pagination: use from_index and size to page through large result sets.
    The returned 'total_size' tells you how many resources matched in total.

    Args:
        query:         A keyword or phrase to search for.
        space_id:      The ID of the space to search within.
        resource_type: Filter by resource type: "dataset", "file", or "collection".
                       Pass None to search across all resource types (default: "dataset").
        field:         Optional metadata field name to restrict the search to.
                       When omitted, all indexed fields are searched.
        from_index:    Zero-based offset for pagination (default 0).
        size:          Number of results to return per page (default 20, max 240).

    Returns:
        A dict with:
          - 'total_size': total number of matching resources
          - 'count': number returned in this page
          - 'from_index': the offset used
          - 'results': list of dicts, each with id, name, description, created, spaces, url
    """
    return _search_in_space(query, space_id, resource_type, field, from_index, size)


@mcp.tool()
def get_metadata_fields(space_id: str, sample_size: int = 5) -> dict:
    """Discover metadata field names and sample values by sampling datasets in a space.

    Samples datasets from the space, fetches their metadata, and returns a flattened
    view of all metadata field paths with example values. This is useful for
    understanding what field names and terms to use when calling search_in_space.

    Args:
        space_id:    The ID of the space.
        sample_size: Number of datasets to sample (default 5, max 10).

    Returns:
        A dict mapping flattened field paths to a list of example values seen
        across the sampled datasets.
    """
    sample_size = min(sample_size, 10)
    datasets = _get_datasets_for_space(space_id)
    if not datasets:
        return {}

    n = min(sample_size, len(datasets))
    sampled_ids = random.sample([d["id"] for d in datasets if d.get("id")], n)

    client = get_clowder_client()
    field_examples: dict[str, list] = {}

    def _flatten(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                _flatten(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for item in obj:
                _flatten(item, prefix)
        else:
            if obj is not None and str(obj).strip():
                field_examples.setdefault(prefix, [])
                val = str(obj)
                if val not in field_examples[prefix]:
                    field_examples[prefix].append(val)

    for dataset_id in sampled_ids:
        try:
            records = _safe_get(client, f"/datasets/{dataset_id}/metadata.jsonld")
            if not isinstance(records, list):
                continue
            for rec in records:
                content = rec.get("content")
                if isinstance(content, dict):
                    _flatten(content)
        except RuntimeError:
            continue

    # Trim to at most 3 example values per field
    return {k: v[:3] for k, v in sorted(field_examples.items())}



if __name__ == "__main__":
    mcp.run()
