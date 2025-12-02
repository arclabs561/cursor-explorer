# Agent Explorer

CLI tool for exploring and analyzing AI agent chat data (Cursor, Cline, Aider, etc.).

## Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --all-extras --dev
uv pip install git+https://github.com/arclabs561/multiscale.git
uv pip install -e ../llm-helpers  # Or publish llm-helpers first
```

## Usage

### Basic exploration

```bash
# List conversations
uv run agent-explorer chats

# Show a conversation
uv run agent-explorer convo <composer_id>

# Search chat history
uv run agent-explorer find-solution "python error handling" --k 5

# Recall forgotten discussions
uv run agent-explorer remember "authentication" --k 3

# Find design plans across conversations
uv run agent-explorer design-coherence
```

### Indexing and search

```bash
# Build index (idempotent)
uv run agent-explorer ensure-indexed

# Vector search (requires sqlite-vec)
uv run agent-explorer vec-db-index ./cursor_vec.db ./cursor_index.jsonl
uv run agent-explorer vec-db-search ./cursor_vec.db --query "..." --k 10
```

### Multi-scale viewing

```bash
# Build hierarchical summaries
uv run agent-explorer multiscale --save-tree tree.json

# View stats and health
uv run agent-explorer multiscale-stats tree.json
uv run agent-explorer multiscale-check tree.json
```

## Configuration

- `CURSOR_STATE_DB`: Override default database path
- `OPENAI_API_KEY`: Required for LLM features
- `OPENAI_MODEL`: Default model (default: `gpt-4o-mini`)
- `OPENAI_EMBED_MODEL`: Embedding model (default: `text-embedding-3-small`)

## Features

- **Search**: Semantic and sparse search across chat history
- **Memory**: Recall past discussions with LLM summarization
- **Design coherence**: Organize scattered design plans
- **Multi-scale**: Hierarchical summarization (RAPTOR-like)
- **Caching**: Idempotent indexing and LLM response caching
- **Vector search**: sqlite-vec integration for semantic search

## Notes

- Commands output JSON where noted (`| jq ...` for pipelines)
- Read-only by default; handles your data with care
- See `README_DEPENDENCIES.md` for detailed dependency setup
