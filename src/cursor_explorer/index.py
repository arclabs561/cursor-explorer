from __future__ import annotations

import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional

from . import db as dbmod
from . import parser as parsermod
from . import rag as ragmod
from .paths import expand_abs, default_db_path
from .embeddings import l2_normalize
import llm_utils as llmmod


def _load_sqlite_vec(conn) -> None:
	"""Load sqlite-vec extension with helpful error messages.
	
	Raises RuntimeError with installation instructions if extension cannot be loaded.
	"""
	try:
		import sqlite_vec  # type: ignore
		sqlite_vec.load(conn)
		return
	except ImportError:
		pass
	except Exception as e:
		# sqlite_vec package exists but failed to load
		raise RuntimeError(
			f"sqlite-vec package loaded but failed to initialize: {e}\n"
			"Try: pip install sqlite-vec or uv pip install sqlite-vec"
		) from e

	# Fallback to extension names
	try:
		conn.load_extension("vec0")
		return
	except Exception:
		pass

	try:
		conn.load_extension("sqlite-vec")
		return
	except Exception as e:
		raise RuntimeError(
			"sqlite-vec extension not found. Install it with:\n"
			"  pip install sqlite-vec\n"
			"  or\n"
			"  uv pip install sqlite-vec\n"
			"\n"
			"Alternatively, use sparse search mode instead of vector search.\n"
			f"Original error: {e}"
		) from e


def _composer_ids(conn) -> Iterable[str]:
	for k in dbmod.composer_data_keys(conn, limit=1000000):
		# keys like composerData:<uuid>
		try:
			cid = k.split(":", 1)[1]
			if cid:
				yield cid
		except Exception:
			continue


def build_index(out_path: str, db_path: Optional[str] = None, limit_composers: Optional[int] = None, max_turns_per: Optional[int] = None) -> int:
	"""Write a JSONL index of per-turn items for RAG over all chats.

	Each line: {composer_id, turn_index, user_head, assistant_head, annotations, user, assistant}
	"""
	conn = dbmod.connect_readonly(expand_abs(db_path or default_db_path()))
	out_path = expand_abs(out_path)
	os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
	count = 0
	with open(out_path, "w", encoding="utf-8") as f:
		for i, cid in enumerate(_composer_ids(conn)):
			if limit_composers is not None and i >= limit_composers:
				break
			msgs = parsermod.reconstruct_conversation(conn, cid)
			# Best-effort repo/workspace hint extraction
			try:
				composer_obj = parsermod.load_composer(conn, cid)
				repo_hint = parsermod.extract_repo_hint(composer_obj)
			except Exception:
				repo_hint = None
			items = ragmod.build_turn_items(msgs)
			if max_turns_per is not None:
				items = items[:max_turns_per]
			for it in items:
				if repo_hint:
					it["repo"] = repo_hint
				f.write(json.dumps(it, ensure_ascii=False) + "\n")
				count += 1
	# Close DB connection
	try:
		conn.close()
	except Exception:
		pass
	return count


def sample_index(index_path: str, n: int) -> List[Dict]:
	"""Reservoir sample n items from a JSONL index without loading it all."""
	index_path = expand_abs(index_path)
	reservoir: List[Dict] = []
	with open(index_path, "r", encoding="utf-8") as f:
		for t, line in enumerate(f, start=1):
			try:
				obj = json.loads(line)
			except Exception:
				continue
			if len(reservoir) < n:
				reservoir.append(obj)
			else:
				j = random.randint(1, t)
				if j <= n:
					reservoir[j - 1] = obj
	return reservoir


def search_index(index_path: str, query: str, k: int = 10) -> List[Dict]:
	index_path = expand_abs(index_path)
	from .rag import _score  # reuse simple scorer
	buf: List[Dict] = []
	with open(index_path, "r", encoding="utf-8") as f:
		for line in f:
			try:
				obj = json.loads(line)
			except Exception:
				continue
			base_text = (obj.get("user", "") + "\n" + obj.get("assistant", "")).strip()
			ann = obj.get("annotations") or {}
			meta_bits = []
			for meta_key in [
				"contains_design",
				"contains_preference",
				"contains_learning",
				"unfinished_thread",
				"has_useful_output",
			]:
				if ann.get(meta_key):
					meta_bits.append(meta_key)
			for t in (ann.get("tags") or []):
				if isinstance(t, str) and t:
					meta_bits.append(f"tag:{t}")
			meta_text = (" ".join(meta_bits)).strip()
			text = (base_text + ("\n" + meta_text if meta_text else "")).strip()
			s = _score(query, text)
			if s > 0:
				buf.append({"score": s, **obj})
	buf.sort(key=lambda o: o["score"], reverse=True)
	return buf[:k]


def build_embeddings_sqlite(db_path: str, index_path: str, table: str = "vec_index", changed_only: bool = False) -> int:
	"""Create a SQLite+sqlite-vec DB and populate embeddings for items in the JSONL index.

	This expects the sqlite-vec extension to be available; if not, it will raise at runtime.
	"""
	import sqlite3
	import array
	import re
	import time

	# Validate table name to avoid SQL injection in DDL/DML
	if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
		raise ValueError("invalid table name")

	conn = sqlite3.connect(expand_abs(db_path))
	conn.enable_load_extension(True)
	_load_sqlite_vec(conn)

	c = conn.cursor()
	# Determine embedding dimension dynamically from the selected model, cached in a side table
	client = llmmod.require_client()
	model = os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	# Use a table name unlikely to conflict with sqlite-vec internals
	c.execute(f"CREATE TABLE IF NOT EXISTS {table}_dims(model TEXT, dim INTEGER)")
	info = None
	try:
		info = c.execute(f"SELECT model, dim FROM {table}_dims LIMIT 1").fetchone()
	except Exception:
		info = None
	if info and info[1]:
		dim = int(info[1])
	else:
		try:
			probe = client.embeddings.create(model=model, input=["dimension_probe"])
			dim = len(probe.data[0].embedding)
			c.execute(f"DELETE FROM {table}_dims")
			c.execute(f"INSERT INTO {table}_dims(model, dim) VALUES(?,?)", (model, dim))
		except Exception:
			# As a last resort, fall back to creating the vec table without caching
			probe = client.embeddings.create(model=model, input=["dimension_probe"])
			dim = len(probe.data[0].embedding)
	c.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0(embedding float[{dim}])")
	c.execute(f"CREATE TABLE IF NOT EXISTS {table}_meta(vec_rowid INTEGER PRIMARY KEY, id TEXT UNIQUE, composer_id TEXT, turn_index INTEGER, user_head TEXT, assistant_head TEXT)")

	# Embed items
	inserted = 0
	updated = 0
	skipped_empty = 0
	with open(expand_abs(index_path), "r", encoding="utf-8") as f:
		BATCH_SIZE = max(1, int(os.getenv("EMBED_BATCH", "16")))
		batch_ids: List[str] = []
		batch_texts: List[str] = []
		batch_meta: List[Dict] = []

		def _embed_with_retry(inputs: List[str]):
			retries = 4
			delay = 1.0
			for attempt in range(retries + 1):
				try:
					return client.embeddings.create(model=model, input=inputs)
				except Exception as e:
					if attempt >= retries:
						raise
					if os.getenv("EMBED_VERBOSE"):
						print(f"embed batch failed: {e}; retry in {delay:.1f}s", file=sys.stderr)
					time.sleep(delay)
					delay *= 1.6

		for line in f:
			try:
				obj = json.loads(line)
			except Exception:
				continue
			ident = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
			uh = obj.get("user_head") or obj.get("user") or ""
			ah = obj.get("assistant_head") or obj.get("assistant") or ""
			ann = obj.get("annotations") or {}
			meta_bits = []
			for meta_key in [
				"contains_design",
				"contains_preference",
				"contains_learning",
				"unfinished_thread",
				"has_useful_output",
			]:
				if ann.get(meta_key):
					meta_bits.append(meta_key)
			for t in (ann.get("tags") or []):
				if isinstance(t, str) and t:
					meta_bits.append(f"tag:{t}")
			meta_text = (" ".join(meta_bits)).strip()
			text = (uh + "\n" + ah + ("\n" + meta_text if meta_text else "")).strip()[:1200]
			if not text:
				skipped_empty += 1
				continue
			batch_ids.append(ident)
			batch_texts.append(text)
			batch_meta.append(obj)
			if len(batch_texts) >= BATCH_SIZE:
				# call embedding API
				res = _embed_with_retry(batch_texts)
				for ident2, meta2, data in zip(batch_ids, batch_meta, res.data):
					vec = l2_normalize(list(data.embedding))
					blob = sqlite3.Binary(array.array('f', vec).tobytes())
					# Upsert: check existing meta row for id
					row = c.execute(f"SELECT vec_rowid FROM {table}_meta WHERE id= ?", (ident2,)).fetchone()
					if row:
						vec_rowid = int(row[0])
						c.execute(f"UPDATE {table} SET embedding=? WHERE rowid=?", (blob, vec_rowid))
						c.execute(f"UPDATE {table}_meta SET composer_id=?, turn_index=?, user_head=?, assistant_head=? WHERE vec_rowid= ?",
							(meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head"), vec_rowid))
						updated += 1
					else:
						c.execute(f"INSERT INTO {table}(embedding) VALUES(?)", (blob,))
						vec_rowid = c.lastrowid
						c.execute(f"INSERT INTO {table}_meta(vec_rowid, id, composer_id, turn_index, user_head, assistant_head) VALUES(?,?,?,?,?,?)",
							(vec_rowid, ident2, meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head")))
						inserted += 1
				batch_ids, batch_texts, batch_meta = [], [], []

	if batch_texts:
		res = _embed_with_retry(batch_texts)
		for ident2, meta2, data in zip(batch_ids, batch_meta, res.data):
			vec = l2_normalize(list(data.embedding))
			blob = sqlite3.Binary(array.array('f', vec).tobytes())
			row = c.execute(f"SELECT vec_rowid FROM {table}_meta WHERE id= ?", (ident2,)).fetchone()
			if row:
				vec_rowid = int(row[0])
				c.execute(f"UPDATE {table} SET embedding=? WHERE rowid=?", (blob, vec_rowid))
				c.execute(f"UPDATE {table}_meta SET composer_id=?, turn_index=?, user_head=?, assistant_head=? WHERE vec_rowid= ?",
					(meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head"), vec_rowid))
				updated += 1
			else:
				c.execute(f"INSERT INTO {table}(embedding) VALUES(?)", (blob,))
				vec_rowid = c.lastrowid
				c.execute(f"INSERT INTO {table}_meta(vec_rowid, id, composer_id, turn_index, user_head, assistant_head) VALUES(?,?,?,?,?,?)",
					(vec_rowid, ident2, meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head")))
				inserted += 1

	if os.getenv("EMBED_VERBOSE"):
		print(json.dumps({"inserted": inserted, "updated": updated, "skipped_empty": skipped_empty}), file=sys.stderr)
	conn.commit()
	conn.close()
	return inserted + updated


def vec_search(db_path: str, index_table: str, query: str, top_k: int = 10) -> List[Dict]:
	"""Search sqlite-vec DB and return matches joined with meta rows."""
	import sqlite3
	import array
	import re

	if not re.fullmatch(r"[A-Za-z0-9_]+", index_table or ""):
		raise ValueError("invalid table name")

	conn = sqlite3.connect(expand_abs(db_path))
	conn.enable_load_extension(True)
	_load_sqlite_vec(conn)

	client = llmmod.require_client()
	model = os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	res = client.embeddings.create(model=model, input=[query])
	vec = l2_normalize(list(res.data[0].embedding))
	blob = sqlite3.Binary(array.array('f', vec).tobytes())
	c = conn.cursor()
	rows = c.execute(f"SELECT rowid, distance FROM {index_table} WHERE embedding MATCH ? ORDER BY distance LIMIT ?", (blob, top_k)).fetchall()
	out: List[Dict] = []
	for rowid, distance in rows:
		meta = c.execute(f"SELECT id, composer_id, turn_index, user_head, assistant_head FROM {index_table}_meta WHERE vec_rowid = ?", (rowid,)).fetchone()
		if meta:
			idv, cid, tix, uh, ah = meta
			out.append({"id": idv, "composer_id": cid, "turn_index": tix, "user_head": uh, "assistant_head": ah, "distance": float(distance)})
	conn.close()
	return out




def items_search(db_path: str, table: str = "items", query: str = "", k: int = 10) -> List[Dict]:
	"""Sparse search over the SQLite items table using simple token-overlap scoring.

	Returns top-k items with fields: composer_id, turn_index, user_head, assistant_head, score.
	"""
	import sqlite3
	import re

	if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
		raise ValueError("invalid table name")
	from .rag import _score  # reuse simple scorer

	conn = sqlite3.connect(expand_abs(db_path))
	c = conn.cursor()
	buf: List[Dict] = []
	for row in c.execute(
		f"SELECT composer_id, turn_index, user, assistant, user_head, assistant_head, annotations FROM {table} ORDER BY composer_id, turn_index"
	):
		cid, tix, user, assistant, uh, ah, ann_text = row
		base_text = ((user or "") + "\n" + (assistant or "")).strip()
		ann = {}
		try:
			ann = json.loads(ann_text) if ann_text else {}
		except Exception:
			ann = {}
		meta_bits: List[str] = []
		for meta_key in [
			"contains_design",
			"contains_preference",
			"contains_learning",
			"unfinished_thread",
			"has_useful_output",
		]:
			if isinstance(ann, dict) and ann.get(meta_key):
				meta_bits.append(meta_key)
		for t in (ann.get("tags") or []) if isinstance(ann, dict) else []:
			if isinstance(t, str) and t:
				meta_bits.append(f"tag:{t}")
		meta_text = (" ".join(meta_bits)).strip()
		text = (base_text + ("\n" + meta_text if meta_text else "")).strip()
		s = _score(query, text)
		if s > 0:
			buf.append({
				"composer_id": cid,
				"turn_index": int(tix),
				"user_head": (uh or (user or "").splitlines()[0][:160]) if isinstance(uh, str) else (user or "")[:160],
				"assistant_head": (ah or (assistant or "").splitlines()[0][:200]) if isinstance(ah, str) else (assistant or "")[:200],
				"score": int(s),
			})
	buf.sort(key=lambda o: o["score"], reverse=True)
	conn.close()
	return buf[:k]

def build_index_sqlite(
	out_db_path: str,
	db_path: Optional[str] = None,
	table: str = "items",
	limit_composers: Optional[int] = None,
	max_turns_per: Optional[int] = None,
) -> int:
	"""Write a SQLite index (table of per-turn items) over all chats.

	Schema (default table "items"):
	  - composer_id TEXT
	  - turn_index INTEGER
	  - user TEXT
	  - assistant TEXT
	  - user_head TEXT
	  - assistant_head TEXT
	  - annotations TEXT (JSON)
	PRIMARY KEY (composer_id, turn_index)
	"""
	import sqlite3
	import re

	if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
		raise ValueError("invalid table name")

	src = dbmod.connect_readonly(expand_abs(db_path or default_db_path()))
	out_db = expand_abs(out_db_path)
	os.makedirs(os.path.dirname(out_db) or ".", exist_ok=True)
	conn = sqlite3.connect(out_db)
	# Performance-friendly defaults for bulk writes
	try:
		conn.execute("PRAGMA journal_mode=WAL")
		conn.execute("PRAGMA synchronous=NORMAL")
	except Exception:
		pass
	c = conn.cursor()
	# Create table
	c.execute(
		f"CREATE TABLE IF NOT EXISTS {table} (\n"
		f"  composer_id TEXT NOT NULL,\n"
		f"  turn_index INTEGER NOT NULL,\n"
		f"  user TEXT,\n"
		f"  assistant TEXT,\n"
		f"  user_head TEXT,\n"
		f"  assistant_head TEXT,\n"
		f"  annotations TEXT,\n"
		f"  PRIMARY KEY (composer_id, turn_index)\n"
		f")"
	)

	count = 0
	for i, cid in enumerate(_composer_ids(src)):
		if limit_composers is not None and i >= limit_composers:
			break
		msgs = parsermod.reconstruct_conversation(src, cid)
		# Best-effort repo/workspace hint extraction
		try:
			composer_obj = parsermod.load_composer(src, cid)
			repo_hint = parsermod.extract_repo_hint(composer_obj)
		except Exception:
			repo_hint = None
		items = ragmod.build_turn_items(msgs)
		if max_turns_per is not None:
			items = items[:max_turns_per]
		for it in items:
			if repo_hint:
				it["repo"] = repo_hint
			c.execute(
				f"INSERT INTO {table} (composer_id, turn_index, user, assistant, user_head, assistant_head, annotations)\n"
				f"VALUES (?, ?, ?, ?, ?, ?, ?)\n"
				f"ON CONFLICT(composer_id, turn_index) DO UPDATE SET\n"
				f"  user=excluded.user,\n"
				f"  assistant=excluded.assistant,\n"
				f"  user_head=excluded.user_head,\n"
				f"  assistant_head=excluded.assistant_head,\n"
				f"  annotations=excluded.annotations",
				(
					it.get("composer_id"),
					it.get("turn_index"),
					it.get("user", ""),
					it.get("assistant", ""),
					it.get("user_head", ""),
					it.get("assistant_head", ""),
					json.dumps(it.get("annotations") or {}, ensure_ascii=False),
				),
			)
			count += 1

	# Close source DB connection
	try:
		src.close()
	except Exception:
		pass
	conn.commit()
	conn.close()
	return count


def build_embeddings_sqlite_from_items(
	db_path: str,
	items_table: str = "items",
	vec_table: str = "vec_index",
	changed_only: bool = False,
) -> int:
	"""Populate sqlite-vec embeddings using texts from a SQLite items table.

	- db_path: SQLite DB that contains the items table and will hold vec tables
	- items_table: source per-turn items (schema from build_index_sqlite)
	- vec_table: target sqlite-vec table name
	"""
	import sqlite3
	import array
	import re
	import time

	if not re.fullmatch(r"[A-Za-z0-9_]+", items_table or ""):
		raise ValueError("invalid items table name")
	if not re.fullmatch(r"[A-Za-z0-9_]+", vec_table or ""):
		raise ValueError("invalid vec table name")

	conn = sqlite3.connect(expand_abs(db_path))
	conn.enable_load_extension(True)
	_load_sqlite_vec(conn)

	c = conn.cursor()
	# Ensure items table exists
	row = c.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name= ?", (items_table,)
	).fetchone()
	if not row:
		conn.close()
		raise ValueError(f"items table not found: {items_table}")

	# Create vec tables (detect embedding dim dynamically with caching); avoid conflicting table names
	client = llmmod.require_client()
	model = os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	c.execute(f"CREATE TABLE IF NOT EXISTS {vec_table}_dims(model TEXT, dim INTEGER)")
	info = None
	try:
		info = c.execute(f"SELECT model, dim FROM {vec_table}_dims LIMIT 1").fetchone()
	except Exception:
		info = None
	if info and info[1]:
		dim = int(info[1])
	else:
		probe = client.embeddings.create(model=model, input=["dimension_probe"])
		dim = len(probe.data[0].embedding)
		try:
			c.execute(f"DELETE FROM {vec_table}_dims")
			c.execute(f"INSERT INTO {vec_table}_dims(model, dim) VALUES(?,?)", (model, dim))
		except Exception:
			pass
	c.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} USING vec0(embedding float[{dim}])")
	c.execute(
		f"CREATE TABLE IF NOT EXISTS {vec_table}_meta(\n"
		f"  vec_rowid INTEGER PRIMARY KEY,\n"
		f"  id TEXT UNIQUE,\n"
		f"  composer_id TEXT,\n"
		f"  turn_index INTEGER,\n"
		f"  user_head TEXT,\n"
		f"  assistant_head TEXT\n"
		f")"
	)

	# Read items and embed in batches
	BATCH_SIZE = max(1, int(os.getenv("EMBED_BATCH", "16")))
	inserted = 0
	updated = 0
	skipped_empty = 0
	b_ids: List[str] = []
	b_texts: List[str] = []
	b_meta: List[Dict] = []

	def _embed_with_retry(inputs: List[str]):
		retries = 4
		delay = 1.0
		for attempt in range(retries + 1):
			try:
				return client.embeddings.create(model=model, input=inputs)
			except Exception as e:
				if attempt >= retries:
					raise
				if os.getenv("EMBED_VERBOSE"):
					print(f"embed batch failed: {e}; retry in {delay:.1f}s", file=sys.stderr)
				time.sleep(delay)
				delay *= 1.6

	def _flush_batch() -> None:
		nonlocal inserted, updated, skipped_empty, b_ids, b_texts, b_meta
		if not b_texts:
			return
		res = _embed_with_retry(b_texts)
		for ident2, meta2, data in zip(b_ids, b_meta, res.data):
			vec = l2_normalize(list(data.embedding))
			blob = sqlite3.Binary(array.array('f', vec).tobytes())
			row2 = c.execute(f"SELECT vec_rowid FROM {vec_table}_meta WHERE id= ?", (ident2,)).fetchone()
			if row2:
				vec_rowid = int(row2[0])
				c.execute(f"UPDATE {vec_table} SET embedding=? WHERE rowid=?", (blob, vec_rowid))
				c.execute(
					f"UPDATE {vec_table}_meta SET composer_id=?, turn_index=?, user_head=?, assistant_head=? WHERE vec_rowid=?",
					(meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head"), vec_rowid),
				)
				updated += 1
			else:
				c.execute(f"INSERT INTO {vec_table}(embedding) VALUES(?)", (blob,))
				vec_rowid = c.lastrowid
				c.execute(
					f"INSERT INTO {vec_table}_meta(vec_rowid, id, composer_id, turn_index, user_head, assistant_head) VALUES(?,?,?,?,?,?)",
					(vec_rowid, ident2, meta2.get("composer_id"), meta2.get("turn_index"), meta2.get("user_head"), meta2.get("assistant_head")),
				)
				inserted += 1
		b_ids, b_texts, b_meta = [], [], []

	# Stream rows from a separate cursor
	c_read = conn.cursor()
	for row in c_read.execute(
		f"SELECT composer_id, turn_index, user_head, assistant_head, user, assistant, annotations FROM {items_table} ORDER BY composer_id, turn_index"
	):
		cid, tidx, uh, ah, user, assistant, ann_text = row
		try:
			ann = json.loads(ann_text) if ann_text else {}
		except Exception:
			ann = {}
		meta_bits: List[str] = []
		for meta_key in [
			"contains_design",
			"contains_preference",
			"contains_learning",
			"unfinished_thread",
			"has_useful_output",
		]:
			if isinstance(ann, dict) and ann.get(meta_key):
				meta_bits.append(meta_key)
		for t in (ann.get("tags") or []) if isinstance(ann, dict) else []:
			if isinstance(t, str) and t:
				meta_bits.append(f"tag:{t}")
		meta_text = (" ".join(meta_bits)).strip()
		text = ((uh or user or "") + "\n" + (ah or assistant or "") + ("\n" + meta_text if meta_text else "")).strip()[:1200]
		if not text:
			skipped_empty += 1
			continue
		ident = f"{cid}:{tidx}"
		b_ids.append(ident)
		b_texts.append(text)
		# safe heads
		user_text = (user or "").strip()
		assist_text = (assistant or "").strip()
		user_head = (uh or (user_text.splitlines()[0] if user_text else ""))[:160]
		assistant_head = (ah or (assist_text.splitlines()[0] if assist_text else ""))[:200]
		b_meta.append({
			"composer_id": cid,
			"turn_index": tidx,
			"user_head": user_head,
			"assistant_head": assistant_head,
		})
		if len(b_texts) >= BATCH_SIZE:
			_flush_batch()

	_flush_batch()
	if os.getenv("EMBED_VERBOSE"):
		print(json.dumps({"inserted": inserted, "updated": updated, "skipped_empty": skipped_empty}), file=sys.stderr)
	conn.commit()
	conn.close()
	return inserted + updated
