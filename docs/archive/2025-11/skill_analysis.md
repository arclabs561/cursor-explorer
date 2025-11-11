# Skill Analysis: Current State & Recommendations

## Current Skills

**Status**: No skills currently installed (`~/.skill-mcp/skills/` is empty)

## Analysis Methodology

Analyzed the codebase to identify:
1. Frequently used CLI commands and workflows
2. Repeated patterns in scripts and tools
3. Common development tasks
4. Integration points with external systems

## Recommended Skills (Prioritized by Evidence)

### 1. **git-workflow** (HIGH PRIORITY)

**Evidence**:
- 20+ git-related scripts in `bin/`: `gp`, `gb`, `gca`, `gdc`, `gmp`, `rebase-check`, `rb`, `cb`, `ga`, etc.
- User rules emphasize non-interactive git commit manipulation
- Extensive git aliases in `dotfiles/home/.aliasrc` and `.gitconfig`
- `rebase-check` script validates commits during rebase
- Memory mentions "mindful git workflows tool" (GP)

**Recommended Skill Functions**:
- `rebase_check`: Validate commits during rebase (wraps `bin/rebase-check`)
- `commit_amend`: Non-interactive commit amending
- `commit_fixup`: Create fixup commits for autosquash
- `branch_list`: List branches sorted by date (wraps `bin/gb`)
- `merge_base`: Find merge base between branches
- `commit_reword`: Reword commit messages non-interactively

**Why**: Git operations are the most frequent workflow based on script count and user rules.

---

### 2. **cursor-chat-analysis** (HIGH PRIORITY)

**Evidence**:
- Entire `cursor_explorer` module with 24+ CLI commands
- Commands: `chats`, `pairs`, `vsearch`, `index-embeds`, `toolchat`, `fuzz`, `adversarial`, `review`
- Vector search workflows documented in README
- `agent_qa_sweep.sh` script for automated QA over chats
- Multiple index files: `cursor_index.jsonl`, `cursor_vec.db`, `cursor_items.db`

**Recommended Skill Functions**:
- `list_chats`: List all Cursor conversations
- `search_chat`: Semantic search across chat history
- `index_embeddings`: Build embeddings for a conversation
- `vector_search`: Query vector database
- `extract_pairs`: Extract user-assistant pairs
- `fuzz_queries`: Generate adversarial query variants

**Why**: This is a core tool in the repo with extensive functionality that would benefit from skill-based access.

---

### 3. **code-quality** (MEDIUM PRIORITY)

**Evidence**:
- `Justfile` has `lint`, `format`, `test`, `test-verbose` commands
- Uses `ruff` for linting and formatting
- `pytest` for testing with parallel execution (`-n auto`)
- `rebase-check` script runs linting on each commit
- User rules emphasize running tests automatically

**Recommended Skill Functions**:
- `run_lint`: Execute ruff check
- `run_format`: Format code with ruff
- `run_tests`: Run pytest with appropriate flags
- `run_check`: Combined lint + test (default `just check`)

**Why**: Quality checks are run frequently (pre-commit, during rebase, CI).

---

### 4. **project-setup** (MEDIUM PRIORITY)

**Evidence**:
- `uv sync --all-extras --dev` used throughout
- `Justfile` has `sync` command
- Multiple projects: `cognee/`, `cursor_explorer/`, each with own `pyproject.toml`
- Environment variable management (`.env` files, `python-dotenv`)

**Recommended Skill Functions**:
- `sync_deps`: Run `uv sync` with appropriate flags
- `install_uv`: Install uv if missing
- `check_env`: Validate required environment variables
- `setup_project`: Full project setup (install uv, sync deps, check env)

**Why**: Setup is a common first step and dependency management is frequent.

---

### 5. **cognee-integration** (MEDIUM PRIORITY)

**Evidence**:
- Large `cognee/` directory with MCP server (`cognee-mcp/`)
- Cognee MCP tools: `cognify`, `codify`, `search`, `list_data`, `delete`
- `cognee-mcp-issues.md` and `cognee-mcp-storage.md` documentation
- Integration with knowledge graphs and vector databases

**Recommended Skill Functions**:
- `cognify_data`: Ingest data into cognee knowledge graph
- `codify_repo`: Analyze code repository and build code graph
- `search_memory`: Query cognee memory
- `list_datasets`: List all datasets in cognee

**Why**: Cognee is a major component with complex workflows that would benefit from skill-based access.

---

### 6. **vector-search** (LOW-MEDIUM PRIORITY)

**Evidence**:
- Vector search flows documented in README
- `vec-db-index`, `vec-db-search`, `vsearch` commands
- Uses `sqlite-vec` for vector storage
- Embedding model configuration (`OPENAI_EMBED_MODEL`)

**Recommended Skill Functions**:
- `build_vector_index`: Create sqlite-vec database from JSONL
- `vector_search`: Query vector database
- `hybrid_search`: Combine sparse and vector search
- `index_embeddings`: Precompute embeddings for conversations

**Why**: Vector search is a specialized workflow that's part of cursor-chat-analysis but could be standalone.

---

### 7. **development-automation** (LOW PRIORITY)

**Evidence**:
- `agent_qa_sweep.sh` for automated QA
- `agent_query_fuzzer.sh` for query fuzzing
- `build_index_and_vecdb.sh` for index building
- LLM usage tracking (`llm_usage.jsonl`, `llm_cache.sqlite`)

**Recommended Skill Functions**:
- `run_qa_sweep`: Execute agent QA sweep
- `fuzz_queries`: Generate and test query variants
- `build_indexes`: Build chat indexes and vector DBs
- `track_llm_usage`: Analyze LLM usage patterns

**Why**: These are less frequent but valuable automation tasks.

---

## Implementation Priority

1. **git-workflow** - Most evidence, highest frequency
2. **cursor-chat-analysis** - Core functionality, extensive tooling
3. **code-quality** - Frequent use, simple to implement
4. **project-setup** - Common first step, straightforward
5. **cognee-integration** - Complex but valuable
6. **vector-search** - Specialized, could be part of cursor-chat-analysis
7. **development-automation** - Nice to have, lower frequency

## Skill Composition Strategy

Following the skill-mcp pattern of multi-skill unification:

- **Library skills**: Create reusable utilities (e.g., `git-utils`, `db-utils`)
- **Workflow skills**: Compose library skills for specific workflows
- **Example**: `git-workflow` could import from `git-utils` for common operations

## Next Steps

1. Create `git-workflow` skill first (highest priority)
2. Create `cursor-chat-analysis` skill (core functionality)
3. Test skill composition by having workflows import from library skills
4. Iterate based on actual usage patterns

