import json
import os
import sqlite3
import sys
import subprocess
from pathlib import Path


PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")


def run_module(args):
    cmd = [sys.executable, "-m", "cursor_explorer", *args]
    env = os.environ.copy()
    env["PYTHONPATH"] = PKG_SRC
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def _make_db(tmp_path: Path) -> tuple[str, str]:
    dbp = tmp_path / "cli_demo.sqlite"
    conn = sqlite3.connect(str(dbp))
    cur = conn.cursor()
    cur.execute("CREATE TABLE cursorDiskKV(key TEXT PRIMARY KEY, value BLOB)")
    # composerData with two bubbles
    composer_id = "cid1"
    composer_json = (
        '{"title":"T","fullConversationHeadersOnly":[{"bubbleId":"b1","type":1,"serverBubbleId":0},{"bubbleId":"b2","type":2,"serverBubbleId":0}]}'
    ).encode("utf-8")
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", (f"composerData:{composer_id}", composer_json))
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", (f"bubbleId:{composer_id}:b1", b'{"text":"hello"}'))
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", (f"bubbleId:{composer_id}:b2", b'{"text":"world"}'))
    # misc key for show/search
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", ("misc:foo", b"hello world"))
    conn.commit()
    conn.close()
    return str(dbp), composer_id


def _write_jsonl(tmp_path: Path, items):
	p = tmp_path / "idx.jsonl"
	p.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
	return p


def test_cli_chats_convo_dump_show_search_rag(tmp_path):
    db_path, cid = _make_db(tmp_path)

    proc = run_module(["chats", "--db", db_path, "--limit", "5"])
    assert proc.returncode == 0 and f"composerData:{cid}" in proc.stdout

    proc = run_module(["convo", "--db", db_path, cid])
    assert proc.returncode == 0 and "[user]" in proc.stdout and "[assistant]" in proc.stdout

    proc = run_module(["dump", "--db", db_path, cid])
    assert proc.returncode == 0
    msgs = json.loads(proc.stdout)
    assert isinstance(msgs, list) and len(msgs) == 2

    proc = run_module(["show", "--db", db_path, "misc:foo", "--preview", "5"])
    assert proc.returncode == 0
    assert proc.stdout.strip().endswith("... [truncated]")

    proc = run_module(["search", "--db", db_path, "--key-like", "%misc%", "--contains", "world", "--limit", "10"])
    assert proc.returncode == 0 and "misc:foo" in proc.stdout

    proc = run_module(["rag", "--db", db_path, cid, "--query", "hello", "-k", "3"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data.get("composer_id") == cid and "results" in data


def test_rules_extract_cli(tmp_path):
	# build a tiny index that includes preference/decision phrases
	items = [
		{"composer_id": "c1", "turn_index": 0, "user": "I prefer concise outputs", "assistant": "Here's a short plan:\n- Step 1\n- Step 2", "user_head": "I prefer concise outputs", "assistant_head": "Here's a short plan", "annotations": {}},
		{"composer_id": "c1", "turn_index": 1, "user": "we decided to use sqlite-vec", "assistant": "Sounds good.", "user_head": "we decided to use sqlite-vec", "assistant_head": "Sounds good.", "annotations": {}},
	]
	idx = _write_jsonl(tmp_path, items)
	cmd = [sys.executable, "-m", "cursor_explorer", "rules-extract", str(idx), str(tmp_path / "rules.json")]
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	proc = sys.modules.get("subprocess")
	if proc is None:
		import subprocess as sp
	else:
		sp = proc
	res = sp.run(cmd, env=env, capture_output=True, text=True)
	assert res.returncode == 0
	out = json.loads(res.stdout)
	assert isinstance(out, dict)
	its = out.get("items", [])
	assert its and all("statement" in it and "satisfaction_score" in it for it in its)
	# scores in [-1,1]
	for it in its:
		assert -1.0 <= float(it.get("satisfaction_score", 0)) <= 1.0


def test_cli_vec_search_rejects_invalid_table_name():
    proc = run_module(["vec-search", "/tmp/nonexistent.sqlite", "--table", "bad;drop", "--query", "q"]) 
    assert proc.returncode != 0
    assert "invalid table name" in proc.stdout


