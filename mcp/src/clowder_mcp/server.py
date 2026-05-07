"""Clowder MCP Server implementation."""

import asyncio
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastmcp import FastMCP
from pyclowder.client import ClowderClient

mcp = FastMCP("clowder")

_THREAD_POOL = ThreadPoolExecutor(max_workers=6)
MAX_COLLECT_SIZE = 100

# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

_ARRAY_SEGMENT = re.compile(r"\[\]$")


def _resolve_path(node: Any, segments: list[str]) -> tuple[Any, str | None]:
    """Walk a nested dict following dot-notation segments.

    Returns (value, warning) where warning is a non-None string when the path
    hit a list without a '[]' segment — the most common user mistake that
    causes silent None returns.

    A segment ending with '[]' means the value is a list — fan out over every
    element and collect all leaf values into a flat list.
    """
    if not segments:
        return node, None
    if node is None:
        return None, None

    seg = segments[0]
    rest = segments[1:]

    if _ARRAY_SEGMENT.search(seg):
        key = seg[:-2]
        arr = node.get(key) if isinstance(node, dict) else None
        if not isinstance(arr, list):
            return None, None
        collected = []
        warnings = []
        for item in arr:
            val, warn = _resolve_path(item, rest)
            if warn:
                warnings.append(warn)
            if val is not None:
                if isinstance(val, list):
                    collected.extend(val)
                else:
                    collected.append(val)
        return (collected or None), (warnings[0] if warnings else None)

    if not isinstance(node, dict):
        return None, None

    child = node.get(seg)
    # Detect missing '[]': the next key resolved to a list but path has no '[]'
    if isinstance(child, list) and rest:
        return None, (
            f"Path segment '{seg}' is a list but '[]' was not appended. "
            f"Use '{seg}[]' to fan out over list elements."
        )
    return _resolve_path(child, rest)


def _project(records: list[dict], fields: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Extract requested field paths from a dataset's metadata.jsonld records.

    Merges all content blocks first (each extractor owns distinct top-level keys),
    then resolves each requested dot-notation path against the merged dict.
    Missing paths produce None. Returns (projected_dict, warnings).

    NOTE on array associations: requesting two sibling array fields (e.g.
    catalyst[].name and catalyst[].ppm) returns separate flat lists. The
    pairing between elements is lost. Use get_dataset_metadata for full
    per-item detail on a single dataset.
    """
    merged: dict[str, Any] = {}
    for rec in records:
        content = rec.get("content")
        if isinstance(content, dict):
            merged.update(content)

    projected: dict[str, Any] = {}
    warnings: list[str] = []
    for f in fields:
        value, warn = _resolve_path(merged, f.split("."))
        projected[f] = value
        if warn:
            warnings.append(f"{f!r}: {warn}")
    return projected, warnings


def _fetch_metadata_raw(client: ClowderClient, dataset_id: str) -> list[dict] | None:
    """Fetch metadata.jsonld for one dataset; returns None on any error."""
    try:
        result = client.get(f"/datasets/{dataset_id}/metadata.jsonld")
        return result if isinstance(result, list) else None
    except Exception:
        return None


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
def get_metadata_fields(
    space_id: str,
    sample_size: int = 5,
    filter_prefix: str | None = None,
) -> dict:
    """Discover metadata field names and sample values by sampling datasets in a space.

    Samples datasets from the space, fetches their metadata, and returns a flattened
    view of all metadata field paths with example values. This is useful for
    understanding what field names and terms to use when calling search_in_space
    or choosing field paths for search_and_collect.

    Args:
        space_id:       The ID of the space.
        sample_size:    Number of datasets to sample (default 5, max 10).
        filter_prefix:  If provided, return only field paths starting with this
                        string (e.g. "FROMP Measurements" or "inputs.catalysts").

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

    result = {k: v[:3] for k, v in sorted(field_examples.items())}
    if filter_prefix:
        result = {k: v for k, v in result.items() if k.startswith(filter_prefix)}
    return result


# ---------------------------------------------------------------------------
# Search + collect (efficient combined tool)
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_and_collect(
    query: str,
    space_id: str,
    fields: list[str],
    resource_type: str | None = "dataset",
    field: str | None = None,
    from_index: int = 0,
    size: int = 20,
) -> dict:
    """Search datasets and extract specific metadata fields in a single call.

    Combines search_in_space and get_dataset_metadata into one efficient tool.
    The server fans out all metadata fetches in parallel and returns only the
    fields you requested — avoiding the N separate get_dataset_metadata calls
    that would otherwise fill the context window.

    Use this instead of calling search_in_space + get_dataset_metadata in a loop.

    FIELD PATH RULES — read carefully to avoid silent None values:

    1. Use dot-notation to address nested keys:
           "FROMP Measurements.Measured frontal velocity (mm/s)"
           "procedure.general.Initiation method"

    2. When a path segment is a LIST in the JSON, you MUST append '[]' to that
       segment. Without it the field returns None and a warning is emitted.
           WRONG:  "inputs.catalysts.catalyst-inputs.name"   → None
           RIGHT:  "inputs.catalysts.catalyst-inputs[].name" → ["GC-2", "GC-3"]

    3. Array fan-out collects all values into a flat list. If you request two
       sibling array fields (e.g. catalyst[].name AND catalyst[].ppm), you get
       two separate lists — the pairing between elements is LOST. To preserve
       pairings, call get_dataset_metadata on the individual dataset instead.

    4. Check 'path_warnings' in the response. A non-empty list means one or more
       field paths returned None due to a missing '[]' — correct the path and retry.

    Use get_metadata_fields(space_id) first to discover valid field paths.

    Args:
        query:         Keyword or phrase to search for.
        space_id:      ID of the space to search within.
        fields:        Dot-notation metadata field paths to extract per dataset.
                       Example:
                         ["FROMP Measurements.Measured frontal velocity (mm/s)",
                          "inputs.catalysts.catalyst-inputs[].name"]
        resource_type: "dataset", "file", or "collection" (default: "dataset").
        field:         Optional metadata field name to restrict the search to.
        from_index:    Zero-based offset for pagination (default 0).
        size:          Datasets to fetch and process. Capped at 50. Default: 20.

    Returns:
        A dict with:
          - 'total_size':     total search matches (may exceed 'size').
          - 'count':          number of datasets returned in this page.
          - 'from_index':     offset used.
          - 'results':        list of slim dicts, each with dataset_id, name, url,
                              and one key per requested field (value or None).
          - 'errors':         dataset IDs whose metadata could not be fetched.
          - 'path_warnings':  list of path correction hints — non-empty means a
                              field path is wrong (usually missing '[]'). Fix the
                              path and retry before drawing conclusions from None values.
    """
    size = min(size, MAX_COLLECT_SIZE)
    loop = asyncio.get_running_loop()

    search_result = await loop.run_in_executor(
        _THREAD_POOL,
        lambda: _search_in_space(query, space_id, resource_type, field, from_index, size),
    )

    matches = search_result["results"]
    if not matches:
        return {
            "total_size": search_result["total_size"],
            "count": 0,
            "from_index": from_index,
            "results": [],
            "errors": [],
        }

    client = get_clowder_client()

    async def _fetch_one(match: dict) -> tuple[dict, list[dict] | None]:
        records = await loop.run_in_executor(
            _THREAD_POOL,
            lambda: _fetch_metadata_raw(client, match["id"]),
        )
        return match, records

    gathered = await asyncio.gather(*[_fetch_one(m) for m in matches])

    base_url = os.environ.get("CLOWDER_URL", "").rstrip("/")
    results = []
    errors = []
    all_warnings: list[str] = []

    for match, records in gathered:
        dataset_id = match["id"]
        if records is None:
            errors.append(dataset_id)
            continue
        projected, warnings = _project(records, fields)
        for w in warnings:
            if w not in all_warnings:
                all_warnings.append(w)
        results.append({
            "dataset_id": dataset_id,
            "name": match["name"],
            "url": f"{base_url}/datasets/{dataset_id}",
            **projected,
        })

    return {
        "total_size": search_result["total_size"],
        "count": len(results),
        "from_index": from_index,
        "results": results,
        "errors": errors,
        "path_warnings": all_warnings,
    }


if __name__ == "__main__":
    mcp.run()
