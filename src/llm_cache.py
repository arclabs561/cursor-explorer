from __future__ import annotations

import os
import sqlite3
from typing import Optional, Dict


def _db_path() -> str:
	return os.getenv("LLM_CACHE_PATH", "llm_cache.sqlite")


def _connect() -> sqlite3.Connection:
	path = _db_path()
	conn = sqlite3.connect(path)
	conn.execute(
		"""
		CREATE TABLE IF NOT EXISTS cache (
			key TEXT PRIMARY KEY,
			value TEXT NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
		"""
	)
	conn.execute(
		"""
		CREATE TABLE IF NOT EXISTS cache_meta (
			key TEXT PRIMARY KEY,
			prompt_tokens INTEGER,
			completion_tokens INTEGER,
			total_tokens INTEGER,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
		"""
	)
	return conn


def get(key: str) -> Optional[str]:
	try:
		conn = _connect()
		row = conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
		conn.close()
		return row[0] if row else None
	except Exception:
		return None


def get_meta(key: str) -> Optional[Dict[str, int]]:
	try:
		conn = _connect()
		row = conn.execute(
			"SELECT prompt_tokens, completion_tokens, total_tokens FROM cache_meta WHERE key = ?",
			(key,),
		).fetchone()
		conn.close()
		if not row:
			return None
		return {
			"prompt_tokens": int(row[0]) if row[0] is not None else 0,
			"completion_tokens": int(row[1]) if row[1] is not None else 0,
			"total_tokens": int(row[2]) if row[2] is not None else 0,
		}
	except Exception:
		return None


def set(key: str, value: str, prompt_tokens: int | None = None, completion_tokens: int | None = None, total_tokens: int | None = None) -> None:
	try:
		conn = _connect()
		conn.execute("INSERT OR REPLACE INTO cache(key, value) VALUES(?, ?)", (key, value))
		conn.execute(
			"INSERT OR REPLACE INTO cache_meta(key, prompt_tokens, completion_tokens, total_tokens) VALUES(?, ?, ?, ?)",
			(key, prompt_tokens, completion_tokens, total_tokens),
		)
		conn.commit()
		conn.close()
	except Exception:
		return


def clear() -> None:
	try:
		conn = _connect()
		conn.execute("DELETE FROM cache")
		conn.execute("DELETE FROM cache_meta")
		conn.commit()
		conn.close()
	except Exception:
		return


def count() -> int:
	try:
		conn = _connect()
		row = conn.execute("SELECT COUNT(*) FROM cache").fetchone()
		conn.close()
		return int(row[0]) if row else 0
	except Exception:
		return 0


