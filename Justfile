# Command runner for common tasks (requires `just`)
# Install `just`: https://github.com/casey/just

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default: check

install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

sync:
	uv sync --all-extras --dev

test *args:
	uv run pytest -q -n auto {{args}}

test-verbose *args:
	# Show stdout/stderr and print captured logs; pass -vv for more detail
	uv run pytest -q -s -vv -n auto {{args}}

lint *args:
	uv run ruff check . {{args}}

format *args:
	uv run ruff format . {{args}}

check:
	just lint
	just test

build:
	uv build

clean:
	rm -rf .venv .pytest_cache __pycache__ */__pycache__ dist build *.egg-info test_log.log

run *args:
	PYTHONPATH=src uv run python -m cursor_explorer {{args}}

info *args:
	PYTHONPATH=src uv run python -m cursor_explorer info {{args}}

tables *args:
	PYTHONPATH=src uv run python -m cursor_explorer tables {{args}}

keys *args:
	PYTHONPATH=src uv run python -m cursor_explorer keys {{args}}

search *args:
	PYTHONPATH=src uv run python -m cursor_explorer search {{args}}

show *args:
	PYTHONPATH=src uv run python -m cursor_explorer show {{args}}

chats *args:
	PYTHONPATH=src uv run python -m cursor_explorer chats {{args}}

fuzz *args:
	PYTHONPATH=src uv run python -m cursor_explorer fuzz {{args}}

pairs *args:
	PYTHONPATH=src uv run python -m cursor_explorer pairs {{args}}

scales *args:
	PYTHONPATH=src uv run python -m cursor_explorer scales {{args}}

# New recipes for indexing and vector search
index *args:
	PYTHONPATH=src uv run python -m cursor_explorer index {{args}}

sample *args:
	PYTHONPATH=src uv run python -m cursor_explorer sample {{args}}

vec-index *args:
	PYTHONPATH=src uv run python -m cursor_explorer vec-db-index {{args}}

vec-search *args:
	PYTHONPATH=src uv run python -m cursor_explorer vec-db-search {{args}}

vsearch *args:
	PYTHONPATH=src uv run python -m cursor_explorer vsearch {{args}}

index-embeds *args:
	PYTHONPATH=src uv run python -m cursor_explorer index-embeds {{args}}

toolchat *args:
	PYTHONPATH=src uv run python -m cursor_explorer toolchat {{args}}

# Local script runners
agent-qa-sweep:
	./scripts/agent_qa_sweep.sh

agent-query-fuzzer:
	./scripts/agent_query_fuzzer.sh

build-index-and-vecdb:
	./scripts/build_index_and_vecdb.sh

# Dotfiles and system restoration
dotfiles-setup:
	# Setup local dotfiles
	./dotfiles/setup

dotfiles-resup:
	# Restore system using ~/dev/dotfiles (if it exists)
	@if [ -d ~/dev/dotfiles ]; then \
		./dotfiles/setup ~/dev/dotfiles; \
	else \
		echo "~/dev/dotfiles does not exist. Using local dotfiles instead."; \
		./dotfiles/setup; \
	fi

resup:
	# Full system restoration: setup dotfiles from ~/dev/dotfiles
	just dotfiles-resup
