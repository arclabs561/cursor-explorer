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


def test_help_mentions_cluster_commands():
	proc = run_cli(["--help"])
	assert proc.returncode == 0
	assert "cluster-index" in proc.stdout
	assert "cluster-summarize" in proc.stdout
	assert "cluster-evoc" in proc.stdout


def test_cluster_evoc_errors_when_missing_dependency(tmp_path):
	# Skip if evoc is actually installed
	try:
		import evoc  # type: ignore  # noqa: F401
		return
	except Exception:
		pass
	# create a tiny synthetic index
	idx = tmp_path / "tiny.index.jsonl"
	items = [
		{"composer_id": "c1", "turn_index": 0, "user": "hello", "assistant": "world", "annotations": {"tags": ["greet"], "has_useful_output": True}},
		{"composer_id": "c1", "turn_index": 1, "user": "foo", "assistant": "bar", "annotations": {"contains_design": False}},
	]
	with idx.open("w", encoding="utf-8") as f:
		for it in items:
			f.write(json.dumps(it) + "\n")
	out = tmp_path / "evoc.json"
	proc = run_cli(["cluster-evoc", str(idx), str(out), "--limit", "2"])
	assert proc.returncode != 0
	# error should mention evoc requirement
	assert "evoc" in (proc.stderr.lower() or "") or "required" in (proc.stderr.lower() or "")


