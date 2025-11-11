import json
import os
from pathlib import Path

from cursor_explorer import toolchat as toolchatmod
from cursor_explorer import index as indexmod


def test_tools_schema_contains_expected_tools():
	schemas = toolchatmod.get_tools_schema()
	names = {s["function"]["name"] for s in schemas}
	assert {
		"annotations_search",
		"list_chats",
		"cat_chat",
		"index_jsonl",
		"vec_db_index",
		"sparse_search",
		"vec_db_search",
		"hybrid_search",
		"review_chat",
		"fuzz_seeds",
	}.issubset(names)


def test_sparse_search_on_custom_index(tmp_path):
	# Create a tiny JSONL index
	index_path = tmp_path / "idx.jsonl"
	items = [
		{"composer_id": "c1", "turn_index": 1, "user": "prompt injection example", "assistant": "" , "user_head": "prompt injection", "assistant_head": "", "annotations": {"tags": ["security"]}},
		{"composer_id": "c2", "turn_index": 2, "user": "code block and json payload", "assistant": "", "user_head": "code block", "assistant_head": "json payload", "annotations": {"tags": ["code"]}},
	]
	index_path.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")

	# Sparse search should find both with token overlap
	out = indexmod.search_index(str(index_path), "prompt injection code block", k=5)
	ids = [(o.get("composer_id"), o.get("turn_index")) for o in out]
	assert ("c1", 1) in ids and ("c2", 2) in ids


def test_sample_cli_on_index(tmp_path, monkeypatch):
	# Build minimal index
	index_path = tmp_path / "idx.jsonl"
	items = [
		{"composer_id": "c1", "turn_index": 1, "user": "u", "assistant": "a", "user_head": "u", "assistant_head": "a", "annotations": {}},
		{"composer_id": "c2", "turn_index": 2, "user": "u2", "assistant": "a2", "user_head": "u2", "assistant_head": "a2", "annotations": {}},
		{"composer_id": "c3", "turn_index": 3, "user": "u3", "assistant": "a3", "user_head": "u3", "assistant_head": "a3", "annotations": {}},
	]
	index_path.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")

	# Use the CLI 'sample' via module runner
	import sys
	import subprocess
	PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	proc = subprocess.run([sys.executable, "-m", "cursor_explorer", "sample", str(index_path), "2"], env=env, capture_output=True, text=True)
	assert proc.returncode == 0
	arr = json.loads(proc.stdout)
	assert isinstance(arr, list) and len(arr) == 2

