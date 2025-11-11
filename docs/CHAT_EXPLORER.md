# Chat Explorer Tool

A focused CLI tool for inspecting and extracting Cursor chat data from local SQLite (`state.vscdb`).
Read-only, jq-friendly JSON, optional LLM annotations/summaries, and basic adversarial probes.

## Quickstart

- Ensure Cursor is closed.
- Default DB (macOS): `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`

Install uv (once):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create/sync venv and dev deps:

```bash
uv sync --all-extras --dev
```

Run CLI:

```bash
uv run cursor-explorer --help
uv run cursor-explorer info
```

### Optional extras

- LLM support: `uv sync --extra llm`
- .env loading: `uv sync --extra extras` or `uv sync --extra dotenv`

Set `OPENAI_API_KEY` (in shell or `.env`). Optionally `OPENAI_MODEL`.

## Commands

- `info` — show DB path, existence, size, tables (text output)
- `tables` — list tables (text)
- `keys` — list keys in `cursorDiskKV` (text; prefix/like filters)
- `search` — search keys by LIKE pattern (text)
- `show` — show a specific key's value (pretty JSON when possible)
- `chats` — list `composerData:*` entries with optional parsed metadata (text)
- `convo` — print reconstructed conversation for a `composer_id` (text)
- `dump` — dump reconstructed messages as JSON
- `pairs` — emit user-assistant pairs (embedding-ready); `--annotate`, `--rich`, `--llm`
- `adversarial` — generate adversarial variants and pattern analysis
- `prompt` — run an LLM using a template with variables

### Prompt runner

```bash
uv run cursor-explorer prompt prompts/annotation.json.tmpl \
  --var user="Hello" --var assistant="World" --llm-model gpt-4o-mini
```

Templates use `{{ var }}` placeholders.

### LLM usage logging and caching

- Usage log file: `llm_usage.jsonl` (override with `LLM_LOG_PATH`)
- Control previews: `LLM_LOG_INPUT=0` and/or `LLM_LOG_OUTPUT=0`
- Truncate previews: `LLM_LOG_TRUNCATE=1000`
- Caching DB: `llm_cache.sqlite` (override with `LLM_CACHE_PATH`)

Caching keys include the model, instructions, and input text. Delete the cache file to reset.

Handle with care; this data may be sensitive.

### Advanced commands

- `scales` — heuristic micro/meso/macro summary; `--llm` to include LLM summary
- `rag` — retrieve turns by query over heads and annotations
- `index` — pre-index all chats into a JSONL file
- `sample` — reservoir sample from a JSONL index
- `index-embeds` — precompute embeddings for a single conversation into local cache (default `EMBEDDING_MODEL=text-embedding-3-small`)
- `vsearch` — semantic search within a single conversation (uses cached embeddings)
- `vec-index` — build a sqlite-vec database from a JSONL index (requires sqlite-vec)
- `vec-search` — vector search a sqlite-vec database
- `toolchat` — run a one-turn chat where the model may call an annotations search tool
