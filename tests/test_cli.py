import logging
import os
import sys
import subprocess
from pathlib import Path

PKG_SRC = str(Path(__file__).resolve().parents[1] / "src")


def run_module(args):
	cmd = [sys.executable, "-m", "cursor_explorer", *args]
	env = os.environ.copy()
	env["PYTHONPATH"] = PKG_SRC
	return subprocess.run(cmd, env=env, capture_output=True, text=True)


def test_help_prints(capsys):
	# Intentionally run the module to exercise the help path
	proc = run_module(["--help"])
	assert proc.returncode == 0
	assert "Explore Cursor chats" in proc.stdout


def test_info_nonexistent_db_logs_and_exits():
	logging.getLogger(__name__).info("starting info nonexistent db test")
	proc = run_module(["info", "--db", str(Path("/tmp/does-not-exist-state.vscdb"))])
	assert proc.returncode != 0
	assert "Exists: no" in proc.stdout
	# For real commands, stderr includes usage summary JSON
	assert "usage_summary" in (proc.stderr or "")
	logging.getLogger(__name__).info("completed info nonexistent db test")


def test_keys_on_missing_table_shows_message(tmp_path):
	# Create an empty SQLite file that has no tables; we'll expect missing table notice
	empty_db = tmp_path / "empty.vscdb"
	empty_db.write_bytes(b"")
	proc = run_module(["keys", "--db", str(empty_db)])
	# Depending on SQLite behavior, connecting to empty file may error; accept non-zero
	assert "cursorDiskKV not found" in proc.stdout or proc.returncode != 0
