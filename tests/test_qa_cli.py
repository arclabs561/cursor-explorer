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


def test_qa_on_synthetic_index(tmp_path):
	idx = tmp_path / "tiny.index.jsonl"
	rows = [
		{"composer_id": "c1", "turn_index": 0, "user_head": "ask", "assistant_head": "answer", "annotations": {"contains_design": True, "tags": ["design"]}},
		{"composer_id": "c1", "turn_index": 1, "user_head": "", "assistant_head": "", "annotations": {}},
	]
	with idx.open("w", encoding="utf-8") as f:
		for r in rows:
			f.write(json.dumps(r) + "\n")
	proc = run_cli(["qa", str(idx), "--limit", "10"]) 
	assert proc.returncode == 0
	data = json.loads(proc.stdout)
	assert "counts" in data and "avg_head_len" in data and "missing_keys" in data and "tag_counts" in data
	assert data["counts"]["turns"] == 2
	# ensure at least one boolean count recorded
	assert any(k.startswith("ann_") for k in data["counts"]) 


