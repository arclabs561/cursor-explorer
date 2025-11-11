"""Database utilities for agent state databases.

Provides read-only access to SQLite databases used by AI agents
to store conversation state and key-value data.
"""

import sqlite3
from typing import Optional, List, Tuple, Iterable


def connect_readonly(db_path: str) -> sqlite3.Connection:
	"""Open a read-only SQLite connection.
	
	Args:
		db_path: Path to SQLite database file
	
	Returns:
		Read-only database connection
	"""
	conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
	conn.row_factory = sqlite3.Row
	return conn


def list_tables(conn: sqlite3.Connection) -> List[str]:
	"""List all table names in the database.
	
	Args:
		conn: Database connection
	
	Returns:
		List of table names
	"""
	c = conn.cursor()
	c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
	return [row[0] for row in c.fetchall()]


def has_table(conn: sqlite3.Connection, table_name: str) -> bool:
	"""Check if a table exists.
	
	Args:
		conn: Database connection
		table_name: Name of table to check
	
	Returns:
		True if table exists, False otherwise
	"""
	c = conn.cursor()
	c.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
		(table_name,)
	)
	return c.fetchone() is not None


def table_info(conn: sqlite3.Connection, table_name: str) -> List[str]:
	"""Get column names for a table.
	
	Args:
		conn: Database connection
		table_name: Name of table
	
	Returns:
		List of column names
	"""
	c = conn.cursor()
	c.execute(f"PRAGMA table_info({table_name})")
	return [row[1] for row in c.fetchall()]


def kv_keys(
	conn: sqlite3.Connection,
	prefix: Optional[str] = None,
	like: Optional[str] = None,
	limit: Optional[int] = None,
	table: str = "cursorDiskKV"
) -> List[str]:
	"""List keys from key-value table.
	
	Args:
		conn: Database connection
		prefix: Optional key prefix filter (e.g., "composerData:")
		like: Optional LIKE pattern filter (e.g., "%foo%")
		limit: Optional maximum number of keys to return
		table: Table name (defaults to cursorDiskKV for backward compatibility)
	
	Returns:
		List of keys
	"""
	c = conn.cursor()
	query = f"SELECT key FROM {table}"
	params = []
	conditions = []
	
	if prefix:
		conditions.append("key LIKE ?")
		params.append(f"{prefix}%")
	if like:
		conditions.append("key LIKE ?")
		params.append(like)
	
	if conditions:
		query += " WHERE " + " AND ".join(conditions)
	
	query += " ORDER BY key"
	
	if limit:
		query += f" LIMIT {limit}"
	
	c.execute(query, params)
	return [row[0] for row in c.fetchall()]


def kv_value(conn: sqlite3.Connection, key: str, table: str = "cursorDiskKV") -> Optional[bytes]:
	"""Get value for a key from key-value table.
	
	Args:
		conn: Database connection
		key: Key to look up
		table: Table name (defaults to cursorDiskKV for backward compatibility)
	
	Returns:
		Value as bytes, or None if not found
	"""
	c = conn.cursor()
	c.execute(f"SELECT value FROM {table} WHERE key=?", (key,))
	row = c.fetchone()
	return row[0] if row else None


def search_kv(
	conn: sqlite3.Connection,
	key_like: Optional[str] = None,
	value_contains: Optional[str] = None,
	limit: Optional[int] = None,
	table: str = "cursorDiskKV"
) -> List[Tuple[str, int]]:
	"""Search key-value table by key pattern and/or value content.
	
	Args:
		conn: Database connection
		key_like: Optional LIKE pattern for keys (e.g., "%foo%")
		value_contains: Optional substring to search in values
		limit: Optional maximum number of results
		table: Table name (defaults to cursorDiskKV for backward compatibility)
	
	Returns:
		List of (key, value_size) tuples
	"""
	c = conn.cursor()
	query = f"SELECT key, LENGTH(value) as size FROM {table}"
	params = []
	conditions = []
	
	if key_like:
		conditions.append("key LIKE ?")
		params.append(key_like)
	if value_contains:
		conditions.append("value LIKE ?")
		params.append(f"%{value_contains}%")
	
	if conditions:
		query += " WHERE " + " AND ".join(conditions)
	
	query += " ORDER BY key"
	
	if limit:
		query += f" LIMIT {limit}"
	
	c.execute(query, params)
	return [(row[0], row[1]) for row in c.fetchall()]


def composer_data_keys(conn: sqlite3.Connection, limit: Optional[int] = None, table: str = "cursorDiskKV") -> Iterable[str]:
	"""Get all composerData:* keys.
	
	Args:
		conn: Database connection
		limit: Optional maximum number of keys
		table: Table name (defaults to cursorDiskKV for backward compatibility)
	
	Returns:
		Iterable of keys matching composerData:*
	"""
	return kv_keys(conn, prefix="composerData:", limit=limit, table=table)

