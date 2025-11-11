import json
import os
import sys
import subprocess
from pathlib import Path


PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")
DB_GLOBAL = os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/state.vscdb")


def run_cli(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = PKG_SRC
    return subprocess.run([sys.executable, "-m", "cursor_explorer", *args], env=env, capture_output=True, text=True)


def test_index_and_rag_sparse_over_real_db():
    if not os.path.exists(DB_GLOBAL):
        import pytest
        pytest.skip("Cursor DB not found; skipping real-DB pipeline smoke test")
    idx = Path("./cursor_index.test.jsonl").resolve()
    proc = run_cli(["index", str(idx), "--db", DB_GLOBAL, "--limit-composers", "10", "--max-turns", "10"])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out.get("wrote", 0) >= 0

    # Sample two items
    proc = run_cli(["sample", str(idx), "2"])
    assert proc.returncode == 0
    items = json.loads(proc.stdout)
    assert isinstance(items, list) and len(items) == 2

    # Grab a composer id and run rag with sparse queries
    proc = run_cli(["chats", "--db", DB_GLOBAL, "--limit", "1"])
    assert proc.returncode == 0
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return
    cid = lines[0].split(":", 1)[1].split()[0]
    proc = run_cli(["rag", cid, "--db", DB_GLOBAL, "--query", "prompt injection", "--query", "code block", "-k", "3"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "results" in data


def test_review_adversary_judge_if_enabled():
    import pytest
    if not os.path.exists(DB_GLOBAL):
        pytest.skip("Cursor DB not found")
    if not os.getenv("OPENAI_API_KEY") or os.getenv("LLM_INTEGRATION") != "1":
        pytest.skip("LLM integration not enabled")
    # pick one chat
    proc = run_cli(["chats", "--db", DB_GLOBAL, "--limit", "1"])
    assert proc.returncode == 0
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return
    cid = lines[0].split(":", 1)[1].split()[0]
    # run review
    proc = run_cli(["review", cid, "--db", DB_GLOBAL])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert set(["composer_id", "turns", "judgment", "meta"]).issubset(data.keys())

