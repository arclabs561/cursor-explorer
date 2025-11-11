import json
import os
import sys
import subprocess
from pathlib import Path


PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")


def run_cmd(args):
	cmd = [sys.executable, "-m", "cursor_explorer", *args]
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	return subprocess.run(cmd, env=env, capture_output=True, text=True)


def test_fuzz_runs_without_llm_and_logs(tmp_path, monkeypatch):
	log_path = tmp_path / "trace.jsonl"
	monkeypatch.setenv("LLM_LOG_PATH", str(log_path))
	proc = run_cmd(["fuzz", "--seed", "hello", "--iterations", "1"])
	assert proc.returncode == 0
	data = json.loads(proc.stdout)
	assert "runs" in data
	assert log_path.exists()

