import os
import sys
import json
import subprocess
from pathlib import Path
import llm_helpers as llmmod
from cursor_explorer import annotate as annotatemod

PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")
DB_GLOBAL = os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/state.vscdb")


def run_pairs(composer_id: str):
	cmd = [sys.executable, "-m", "cursor_explorer", "pairs", "--db", DB_GLOBAL, composer_id, "--annotate"]
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	return subprocess.run(cmd, env=env, capture_output=True, text=True)


def test_pairs_smoke_if_db_exists():
	import pytest
	if not os.path.exists(DB_GLOBAL):
		pytest.skip("Cursor DB not found; skipping CLI pairs smoke test")
	# Probe a composer id by listing chats first
	cmd_list = [sys.executable, "-m", "cursor_explorer", "chats", "--db", DB_GLOBAL, "--limit", "1"]
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	proc_list = subprocess.run(cmd_list, env=env, capture_output=True, text=True)
	assert proc_list.returncode == 0
	lines = [line.strip() for line in proc_list.stdout.splitlines() if line.strip()]
	assert lines, "expected at least one composerData line"
	first = lines[0]
	composer_id = first.split(":", 1)[1].split()[0]

	proc = run_pairs(composer_id)
	assert proc.returncode == 0
	data = json.loads(proc.stdout)
	assert isinstance(data, list)
	if data:
		assert set(["user", "assistant"]).issubset(data[0].keys())


def test_annotate_pair_heuristics_basic():
	pair = {
		"user": "I prefer a simple API. Could you show code?",
		"assistant": "Sure, here's a snippet. It works great!\n```python\nprint('ok')\n```",
	}
	ann = annotatemod.annotate_pair_rich(pair)
	assert ann["has_useful_output"] is True
	assert ann["contains_preference"] is True
	# The current heuristic treats mentions of "API" as design-related
	assert ann["contains_design"] is True
	assert ann["user_polarity"] in {"neutral", "positive"}
	assert ann["assistant_polarity"] == "positive"


def test_conversation_scales_heuristic():
	pairs = [
		{"turn_index": 1, "user": "Build a CLI", "assistant": "I'll create a parser"},
		{"turn_index": 2, "user": "Add tests", "assistant": "Next I'll add pytest"},
	]
	out = annotatemod.annotate_conversation_scales(pairs)
	assert set(out.keys()) == {"micro", "meso", "macro"}
	assert len(out["micro"]) >= 1
	assert out["macro"] != ""


def test_llm_annotation_integration_if_enabled():
	import pytest
	if not os.getenv("OPENAI_API_KEY") or os.getenv("LLM_INTEGRATION") != "1":
		pytest.skip("LLM integration not enabled")
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	pair = {"user": "Summarize this", "assistant": "Here is a concise output"}
	resp = llmmod.annotate_pair_llm(client, pair, model)
	assert isinstance(resp, dict)
	for k in [
		"user_summary",
		"assistant_summary",
		"user_polarity",
		"assistant_polarity",
		"unfinished_thread",
		"has_useful_output",
		"contains_preference",
		"contains_design",
		"contains_learning",
		"tags",
	]:
		assert k in resp
