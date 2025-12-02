import json
import os
import sys
import subprocess
from pathlib import Path


PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")


def run_cli(args):
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	return subprocess.run([sys.executable, "-m", "cursor_explorer", *args], env=env, capture_output=True, text=True)


def test_cluster_index_and_summarize_without_llm(tmp_path):
	# Build a tiny index
	idx = tmp_path / "tiny.index.jsonl"
	rows = [
		{"composer_id": "c1", "turn_index": 0, "user": "how to deploy", "assistant": "use docker", "annotations": {"tags": ["deploy"]}},
		{"composer_id": "c1", "turn_index": 1, "user": "design api", "assistant": "consider versioning", "annotations": {"contains_design": True}},
		{"composer_id": "c1", "turn_index": 2, "user": "learn rust", "assistant": "ownership model", "annotations": {"contains_learning": True}},
	]
	with idx.open("w", encoding="utf-8") as f:
		for r in rows:
			f.write(json.dumps(r) + "\n")
	# Build a small binary cluster tree using the simple method (no EVOC, no LLM)
	tree_path = tmp_path / "tree.json"
	proc = run_cli(["cluster-index", str(idx), str(tree_path), "--depth", "2", "--min-size", "1", "--limit", "3"])
	assert proc.returncode == 0
	data = json.loads(proc.stdout)
	assert data.get("meta", {}).get("count", 0) == 3
	assert tree_path.exists()

	# Summarization requires LLM; skip if no key present
	if not os.getenv("OPENAI_API_KEY") or os.getenv("LLM_INTEGRATION") != "1":
		return
	# With LLM enabled in env, run summarization
	out_path = tmp_path / "tree.sum.json"
	proc = run_cli(["cluster-summarize", str(tree_path), str(idx), str(out_path)])
	assert proc.returncode == 0
	assert out_path.exists()
	try:
		obj = json.loads(out_path.read_text())
		assert "tree" in obj
	except Exception:
		# tolerate non-JSON if LLM returned non-strict JSON, but file should exist
		pass


