# clowder-mcp

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes [Clowder](https://clowderframework.org) research data repositories to AI assistants. It lets Claude and other MCP-capable clients navigate spaces, discover datasets, inspect metadata, and run full-text searches — all without leaving the conversation.

## Overview

The server wraps the Clowder REST API using [pyclowder](https://pypi.org/project/pyclowder/) and exposes it as a set of MCP tools via the [FastMCP](https://github.com/jlowin/fastmcp) framework. It communicates over stdio, making it easy to wire into Claude Code, Claude Desktop, or any other MCP host.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- A Clowder instance URL and API key

## Environment Variables

| Variable | Description |
|---|---|
| `CLOWDER_URL` | Base URL of the Clowder instance (e.g. `https://re-mat.clowderframework.org`) |
| `CLOWDER_KEY` | Your Clowder API key |

## Running the Server

Install dependencies and run with `uv` from the `mcp/` directory:

```bash
cd mcp
uv run clowder-mcp
```

Or from any directory using `--directory`:

```bash
uv run --directory /path/to/clowder-mcp/mcp clowder-mcp
```

### Wiring into Claude Code (`.mcp.json`)

Add this to your project's `.mcp.json` (or Claude Code's global MCP config):

```json
{
  "mcpServers": {
    "clowder": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/clowder-mcp/mcp",
        "clowder-mcp"
      ],
      "env": {
        "CLOWDER_URL": "https://your-clowder-instance.org",
        "CLOWDER_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Debugging with FastMCP Inspector

FastMCP ships with a built-in inspector that lets you call tools interactively in a browser UI without needing Claude:

```bash
cd mcp
CLOWDER_URL=https://your-instance.org CLOWDER_KEY=your-key \
  uv run fastmcp dev src/clowder_mcp/server.py
```

This starts a local web server. Open the printed URL to inspect and call tools manually.

### Running Tests

```bash
cd mcp
uv run pytest
```

---

## MCP Tools

The server exposes nine tools organized into three areas.

### Spaces

#### `list_spaces()`
Lists all spaces in the Clowder instance.

**Returns:** list of spaces — each with `id`, `name`, `description`, and other metadata.

---

#### `find_space_by_name(name)`
Finds spaces whose name contains a given substring (case-insensitive).

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Substring to match against space names |

**Returns:** list of matching spaces.

---

#### `get_space(space_id)`
Gets full details for a specific space.

| Parameter | Type | Description |
|---|---|---|
| `space_id` | `str` | ID of the space |

**Returns:** dict with `id`, `name`, `description`, creation date, dataset count, etc.

---

### Datasets

#### `list_datasets_in_space(space_id)`
Lists all datasets in a space with summary information.

| Parameter | Type | Description |
|---|---|---|
| `space_id` | `str` | ID of the space |

**Returns:** list of `{id, name, description, created}` dicts.

---

#### `get_dataset(dataset_id)`
Gets full details for a specific dataset.

| Parameter | Type | Description |
|---|---|---|
| `dataset_id` | `str` | ID of the dataset |

**Returns:** dict with `id`, `name`, `description`, author, dates, file count, space memberships, tags.

---

#### `get_dataset_metadata(dataset_id)`
Gets user-defined metadata attached to a dataset, including provenance.

| Parameter | Type | Description |
|---|---|---|
| `dataset_id` | `str` | ID of the dataset |

**Returns:** list of metadata records. Each has a `content` field (domain-specific data) and provenance fields (`id`, `attached_to`, `created_at`, `agent`).

---

#### `get_dataset_files(dataset_id)`
Lists the files contained in a dataset.

| Parameter | Type | Description |
|---|---|---|
| `dataset_id` | `str` | ID of the dataset |

**Returns:** list of `{id, filename, size, contentType, date-created, authorId}` dicts.

---

### Search & Discovery

#### `search_in_space(query, space_id, resource_type, field, from_index, size)`
Full-text keyword search backed by ElasticSearch. Searches names, descriptions, and all metadata content.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | — | Keyword or phrase |
| `space_id` | `str` | — | ID of the space to search within |
| `resource_type` | `str \| None` | `"dataset"` | Filter by `"dataset"`, `"file"`, `"collection"`, or `None` for all types |
| `field` | `str \| None` | `None` | Restrict search to a specific metadata field name |
| `from_index` | `int` | `0` | Zero-based pagination offset |
| `size` | `int` | `20` | Results per page (max 240) |

**Returns:** `{total_size, count, from_index, results}` where each result has `id`, `name`, `description`, `created`, `spaces`, and `url`.

---

#### `get_metadata_fields(space_id, sample_size)`
Discovers metadata field names and sample values by sampling datasets in a space. Use this to learn what field paths and vocabulary terms are available before calling `search_in_space`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `space_id` | `str` | — | ID of the space |
| `sample_size` | `int` | `5` | Number of datasets to sample (max 10) |

**Returns:** dict mapping flattened field paths (e.g. `"content.Batch ID"`) to lists of up to 3 example values.

---

## Skills

The `skills/` directory holds Claude Code [skill files](https://docs.anthropic.com/en/docs/claude-code/skills) that provide project-specific context and recommended workflows on top of the generic MCP tools. Skills are loaded by Claude Code and injected into the system prompt when invoked.

```
skills/
└── remat/
    └── SKILL.md   # Guide for the RE-Mat Clowder instance
```

### Adding a new skill

1. Create a subdirectory under `skills/` named after your project or instance.
2. Add a `SKILL.md` file describing:
   - The Clowder instance URL and its purpose
   - The spaces it contains and their research context
   - The metadata schemas used in each space (field paths and example values)
   - Recommended tool call sequences for common queries
   - Domain-specific vocabulary for effective searches

### `remat` skill

Documents the RE-Mat Clowder instance (`re-mat.clowderframework.org`), which stores polymer formulation and polymerization experiments. Covers three spaces:

- **DSC Cure Kinetics** — differential scanning calorimetry on polymer formulations; metadata includes batch ID, operator, catalyst/monomer/inhibitor identities, DSC procedure parameters, and computed enthalpy/peak/onset values.
- **Front Velocities** — FROMP (Frontal Ring-Opening Metathesis Polymerization) experiments; metadata includes frontal velocity, maximum temperature, initiation method, geometry, and photocontrol settings.
- **DSC Post Cures** — DSC measurements on FROMP-cured samples; metadata includes glass transition temperature (Tg), residual enthalpy, and sampling location.

The skill also documents recommended workflows (e.g. `list_spaces` → `get_metadata_fields` → `search_in_space` → `get_dataset_metadata`) and example query terms for each space.

---

## Project Structure

```
clowder-mcp/
├── mcp/                        # Python package
│   ├── pyproject.toml          # Project metadata and dependencies
│   ├── uv.lock                 # Locked dependency versions
│   └── src/
│       └── clowder_mcp/
│           └── server.py       # MCP server and all tool definitions
└── skills/                     # Claude Code skills
    └── remat/
        └── SKILL.md            # RE-Mat instance guide
```

## Dependencies

| Package | Purpose |
|---|---|
| `fastmcp` | MCP server framework |
| `pyclowder` | Clowder REST API client |
| `genson` | JSON schema inference (used internally) |


## Acknowledgements
This work was supported as part of the Regenerative Energy-Efficient Manufacturing of Thermoset Polymeric 
Materials (REMAT), an Energy Frontier Research Center funded by the U.S. Department of Energy, Office of Science, 
Basic Energy Sciences at the <insert name of university> under award #DE-SC0023457.
