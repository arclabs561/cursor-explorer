# Agent Explorer (Chats, Annotations, RAG, Adversary)

Agent-agnostic CLI tool for exploring AI agent chat data. Supports multiple agents (Cursor, Cline, Aider, etc.) via pluggable backend system.

This repo hosts pragmatic, composable dev tools. Each tool is a small, focused CLI with shared Python modules under `src/`.

## Common setup

- Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Sync env (installs dev tools and shared libs):
```bash
uv sync --all-extras --dev
```
- Lint/tests:
```bash
uv run ruff check .
uv run pytest -q
```

## Shared modules

See `src/` for modules used across tools (paths, db, parser, annotations, vector, embeddings, index, tracing, etc.).

## Task runner

Use `just` for common tasks (per-tool and shared):
```bash
just --list
just sync
just lint
just test         # quiet tests
just test-verbose # show logs/stdout/stderr
```

## Notes

- Tools output JSON suitable for pipelines (`| jq ...`) where noted. Some commands (e.g., `info`, `keys`, `chats`, `convo`) print human-readable text.
- Set `OPENAI_API_KEY`; default model reads `OPENAI_MODEL` (default `gpt-5`).
- Embedding model reads `OPENAI_EMBED_MODEL`/`EMBEDDING_MODEL` (defaults to `text-embedding-3-small`). If both are set, `OPENAI_EMBED_MODEL` takes precedence.
- Tracing writes JSONL to `LLM_LOG_PATH` (default `llm_usage.jsonl`). Add run context with `--trace-meta key=value`.
- Each command prints a usage summary to stderr (events, cache hits/stores, tokens).
- Read-only by default; handle your data with care.

### Default DB path

- Override with `CURSOR_STATE_DB` (Cursor) or `AGENT_STATE_DB` (generic)
- Use `--agent` flag to specify agent type (defaults to 'cursor')
- Cursor paths:
  - macOS: `~/Library/Application Support/Cursor/User/*/state.vscdb`
  - Windows: `%APPDATA%\Cursor\User\*\state.vscdb`
  - Linux: `~/.config/Cursor/User/*/state.vscdb`



## Vector search flows

### Per-conversation (quick, no extra DB)

1) Precompute embeddings (cached in `llm_cache.sqlite`):
```bash
PYTHONPATH=src uv run python -m cursor_explorer index-embeds <composer_id> --scope pairs --embed-model text-embedding-3-small
```
2) Search semantically:
```bash
PYTHONPATH=src uv run python -m cursor_explorer vsearch <composer_id> --scope pairs --query "how did we refactor auth?" --topk 10
```

### Corpus (sqlite-vec)

1) Build JSONL across conversations:
```bash
PYTHONPATH=src uv run python -m cursor_explorer index ./cursor_index.jsonl --limit-composers 200 --max-turns 50
```
2) Create sqlite-vec DB with embeddings (dim auto-detected from model):
```bash
PYTHONPATH=src uv run python -m cursor_explorer vec-db-index ./cursor_vec.db ./cursor_index.jsonl
```
3) Query the vector DB:
```bash
PYTHONPATH=src uv run python -m cursor_explorer vec-db-search ./cursor_vec.db --query "guardrails for jailbreaks" --k 8
```

Notes:
- sqlite-vec is loaded via the Python package (`pip install sqlite-vec`) or extension names (`vec0`/`sqlite-vec`).
- Table name defaults to `vec_index`; validated to alphanumeric/underscore.
- Embedding model defaults to `text-embedding-3-small`. You can override via `OPENAI_EMBED_MODEL` (preferred) or `EMBEDDING_MODEL`.

## Toolchat (JSON-schema tools for agents)

Available tools:
- `list_chats` — enumerate chats (ids, titles)
- `cat_chat` — slice `pairs`/`messages` for a chat
- `index_jsonl` — build/refresh JSONL index across chats
- `vec_db_index` — build sqlite-vec DB from the index
- `sparse_search`, `vec_db_search`, `hybrid_search` — retrieve items
- `review_chat` — adversarial review (base vs variants) diffs
- `fuzz_seeds` — fuzz over seed queries and summarize issues

Example:
```bash
PYTHONPATH=src uv run python -m cursor_explorer toolchat \
  --prompt "List chats then search for prompt injection and code blocks, show top 3 items" --sparse
```

### CLI

- Module: `PYTHONPATH=src uv run python -m cursor_explorer --help`
- Script: `uv run cursor-explorer --help` (alias: `uv run cursor-chat-explorer --help`)

### Additional shared modules

- `cursor_explorer.qa` — QA helpers and utilities (experimental)
- `cursor_explorer.tag_cluster` — simple tag clustering (experimental)
