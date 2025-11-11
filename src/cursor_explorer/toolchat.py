from __future__ import annotations

import json
import os
from typing import Dict, List, Any, Optional
import tempfile

import llm_helpers as llmmod
from . import index as indexmod
from . import db as dbmod
from . import parser as parsermod
from . import adversary as adversarymod
from . import fuzz as fuzzmod
from .paths import expand_abs, default_db_path
from . import trace as tracemod
from . import qa as qamod
from . import cluster as clustermod


def _default_index_path() -> str:
	return expand_abs(os.getenv("CURSOR_INDEX_JSONL", "./cursor_index.jsonl"))


def _default_vec_db_path() -> str:
	return expand_abs(os.getenv("CURSOR_VEC_DB", "./cursor_vec.db"))


def get_tools_schema() -> List[Dict[str, Any]]:
	"""Return tool definitions (JSON schema) for LLM tool calling."""
	return [
		{
			"type": "function",
			"function": {
				"name": "annotations_search",
				"description": "Search pre-indexed chat annotations and turn heads across all conversations.",
				"parameters": {
					"type": "object",
					"properties": {
						"mode": {
							"type": "string",
							"enum": ["vector", "sparse"],
							"description": "vector uses sqlite-vec DB; sparse searches JSONL index with token overlap",
						},
						"query": {"type": "string"},
						"k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 50},
						"index_jsonl": {"type": "string", "description": "Path to JSONL index (for sparse mode)"},
						"vec_db": {"type": "string", "description": "Path to sqlite-vec DB (for vector mode)"},
						"table": {"type": "string", "default": "vec_index"},
					},
					"required": ["mode", "query"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "list_chats",
				"description": "List chats from the Cursor DB with optional titles.",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"limit": {"type": "integer", "default": 100}
					},
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "cat_chat",
				"description": "Show a slice of a chat (pairs or messages) for inspection.",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"composer_id": {"type": "string"},
						"mode": {"type": "string", "enum": ["pairs", "messages"], "default": "pairs"},
						"offset": {"type": "integer", "default": 0},
						"limit": {"type": "integer", "default": 5}
					},
					"required": ["composer_id"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "index_jsonl",
				"description": "Build a JSONL index over all chats (for sparse search and sampling).",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"out": {"type": "string"},
						"limit_composers": {"type": "integer"},
						"max_turns": {"type": "integer"}
					},
					"required": ["out"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "vec_db_index",
				"description": "Build a sqlite-vec DB from a JSONL index (for vector search).",
				"parameters": {
					"type": "object",
					"properties": {
						"out_db": {"type": "string"},
						"index_jsonl": {"type": "string"}
					},
					"required": ["out_db", "index_jsonl"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "sparse_search",
				"description": "Search the JSONL index by token overlap.",
				"parameters": {
					"type": "object",
					"properties": {
						"index_jsonl": {"type": "string"},
						"query": {"type": "string"},
						"k": {"type": "integer", "default": 8}
					},
					"required": ["query"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "items_search",
				"description": "Sparse search over the SQLite items table.",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"table": {"type": "string", "default": "items"},
						"query": {"type": "string"},
						"k": {"type": "integer", "default": 8}
					},
					"required": ["query"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "vec_db_search",
				"description": "Vector search with sqlite-vec DB.",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"table": {"type": "string", "default": "vec_index"},
						"query": {"type": "string"},
						"k": {"type": "integer", "default": 8},
					},
					"required": ["query"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "hybrid_search",
				"description": "Run both vector and sparse search and merge results.",
				"parameters": {
					"type": "object",
					"properties": {
						"index_jsonl": {"type": "string"},
						"db": {"type": "string"},
						"table": {"type": "string", "default": "vec_index"},
						"query": {"type": "string"},
						"k": {"type": "integer", "default": 8}
					},
					"required": ["query"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "review_chat",
				"description": "Run adversarial review (base vs variants) and return compact diffs for a chat.",
				"parameters": {
					"type": "object",
					"properties": {
						"db": {"type": "string"},
						"composer_id": {"type": "string"},
						"limit_turns": {"type": "integer", "default": 5}
					},
					"required": ["composer_id"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "fuzz_seeds",
				"description": "Fuzz adversarial seeds and return a brief summary of issues.",
				"parameters": {
					"type": "object",
					"properties": {
						"seeds": {"type": "array", "items": {"type": "string"}},
						"iterations": {"type": "integer", "default": 1},
						"llm": {"type": "boolean", "default": True}
					},
					"required": ["seeds"],
				},
			},
		},
		{
			"type": "function",
			"function": {
				"name": "qa_index",
				"description": "Compute QA stats over a JSONL index (counts, missing keys, tag frequencies).",
				"parameters": {
					"type": "object",
					"properties": {
						"index_jsonl": {"type": "string"},
						"limit": {"type": "integer"}
					},
					"required": [],
				}
			}
		},
		{
			"type": "function",
			"function": {
				"name": "name_topics",
				"description": "Generate layered topic names with Toponymy (optional dependency).",
				"parameters": {
					"type": "object",
					"properties": {
						"index_jsonl": {"type": "string", "description": "Path to JSONL index"},
						"out_json": {"type": "string", "description": "Optional output JSON path"},
						"limit": {"type": "integer"},
						"embed_model": {"type": "string"},
						"min_clusters": {"type": "integer", "default": 4},
						"umap_dim": {"type": "integer", "default": 2},
						"verbose": {"type": "boolean", "default": False},
						"include_doc_topics": {"type": "boolean", "default": False},
						"max_layer_labels": {"type": "integer", "default": 50}
					},
					"required": [],
				}
			}
		},
	]


def _tool_annotations_search(args: Dict[str, Any]) -> Dict[str, Any]:
	mode = args.get("mode", "vector")
	query = args.get("query", "")
	k = max(1, min(int(args.get("k", 8)), 100))
	if mode == "vector":
		db = expand_abs(args.get("vec_db") or _default_vec_db_path())
		table = args.get("table") or "vec_index"
		rows = indexmod.vec_search(db, table, query, top_k=k)
		return {"mode": "vector", "items": rows}
	else:
		idx = expand_abs(args.get("index_jsonl") or _default_index_path())
		rows = indexmod.search_index(idx, query, k=k)
		# keep only essential fields in items
		simple = [{
			"id": f"{r.get('composer_id')}:{r.get('turn_index')}",
			"composer_id": r.get("composer_id"),
			"turn_index": r.get("turn_index"),
			"user_head": r.get("user_head"),
			"assistant_head": r.get("assistant_head"),
			"score": r.get("score", None),
			"annotations": r.get("annotations"),
		} for r in rows]
		return {"mode": "sparse", "items": simple}


def _tool_list_chats(args: Dict[str, Any]) -> Dict[str, Any]:
	conn = dbmod.connect_readonly(expand_abs(args.get("db") or default_db_path()))
	limit = max(1, int(args.get("limit", 100)))
	out: List[Dict[str, Any]] = []
	for k in dbmod.composer_data_keys(conn, limit=limit):
		try:
			cid = k.split(":", 1)[1]
		except Exception:
			cid = k
		title = ""
		val = dbmod.kv_value(conn, k)
		if val is not None:
			try:
				obj = json.loads(val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else str(val))
				title = obj.get("title") or obj.get("name") or obj.get("id") or ""
			except Exception:
				pass
		out.append({"composer_id": cid, "title": title})
	try:
		conn.close()
	except Exception:
		pass
	return {"items": out}


def _tool_cat_chat(args: Dict[str, Any]) -> Dict[str, Any]:
	conn = dbmod.connect_readonly(expand_abs(args.get("db") or default_db_path()))
	cid = args.get("composer_id")
	mode = (args.get("mode") or "pairs").lower()
	offset = max(0, int(args.get("offset", 0)))
	limit = max(1, min(50, int(args.get("limit", 5))))
	msgs = parsermod.reconstruct_conversation(conn, cid)
	if mode == "messages":
		slice_msgs = msgs[offset: offset + limit]
		items = [{"role": m.get("role"), "text": (m.get("text", "") or "")[:500]} for m in slice_msgs]
		try:
			conn.close()
		except Exception:
			pass
		return {"mode": "messages", "items": items}
	pairs = parsermod.build_qa_pairs(msgs)
	slice_pairs = pairs[offset: offset + limit]
	items = [{
		"turn_index": p.get("turn_index"),
		"user_head": (p.get("user") or "").splitlines()[0][:200],
		"assistant_head": (p.get("assistant") or "").splitlines()[0][:200],
	} for p in slice_pairs]
	try:
		conn.close()
	except Exception:
		pass
	return {"mode": "pairs", "items": items}


def _tool_index_jsonl(args: Dict[str, Any]) -> Dict[str, Any]:
	count = indexmod.build_index(args.get("out"), db_path=args.get("db"), limit_composers=args.get("limit_composers"), max_turns_per=args.get("max_turns"))
	return {"wrote": count, "path": expand_abs(args.get("out"))}


def _tool_vec_db_index(args: Dict[str, Any]) -> Dict[str, Any]:
	count = indexmod.build_embeddings_sqlite(args.get("out_db"), args.get("index_jsonl"))
	return {"wrote": count, "db": expand_abs(args.get("out_db"))}


def _tool_sparse_search(args: Dict[str, Any]) -> Dict[str, Any]:
	idx = expand_abs(args.get("index_jsonl") or _default_index_path())
	rows = indexmod.search_index(idx, args.get("query", ""), k=int(args.get("k", 8)))
	return {"items": rows}


def _tool_items_search(args: Dict[str, Any]) -> Dict[str, Any]:
	db = expand_abs(args.get("db") or _default_vec_db_path())
	table = args.get("table") or "items"
	rows = indexmod.items_search(db, table, args.get("query", ""), k=int(args.get("k", 8)))
	return {"items": rows}

def _tool_vec_db_search(args: Dict[str, Any]) -> Dict[str, Any]:
	rows = indexmod.vec_search(expand_abs(args.get("db") or _default_vec_db_path()), args.get("table") or "vec_index", args.get("query", ""), top_k=int(args.get("k", 8)))
	return {"items": rows}


def _tool_hybrid_search(args: Dict[str, Any]) -> Dict[str, Any]:
	query = args.get("query", "")
	idx = expand_abs(args.get("index_jsonl") or _default_index_path())
	db = expand_abs(args.get("db") or _default_vec_db_path())
	table = args.get("table") or "vec_index"
	k = int(args.get("k", 8))
	sp = indexmod.search_index(idx, query, k=k)
	vec = indexmod.vec_search(db, table, query, top_k=k)
	# merge by id
	merged: Dict[str, Dict[str, Any]] = {}
	for r in sp:
		idv = f"{r.get('composer_id')}:{r.get('turn_index')}"
		merged[idv] = {"id": idv, "composer_id": r.get("composer_id"), "turn_index": r.get("turn_index"), "user_head": r.get("user_head"), "assistant_head": r.get("assistant_head"), "sparse_score": r.get("score")}
	for r in vec:
		idv = r.get("id") or f"{r.get('composer_id')}:{r.get('turn_index')}"
		m = merged.get(idv) or {"id": idv, "composer_id": r.get("composer_id"), "turn_index": r.get("turn_index"), "user_head": r.get("user_head"), "assistant_head": r.get("assistant_head")}
		m["vec_distance"] = r.get("distance")
		merged[idv] = m
	items = list(merged.values())
	return {"items": items}


def _tool_review_chat(args: Dict[str, Any]) -> Dict[str, Any]:
	conn = dbmod.connect_readonly(expand_abs(args.get("db") or default_db_path()))
	cid = args.get("composer_id")
	limit_turns = max(1, min(20, int(args.get("limit_turns", 5))))
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	msgs = parsermod.reconstruct_conversation(conn, cid)
	pairs = parsermod.build_qa_pairs(msgs)[:limit_turns]
	out = []
	for p in pairs:
		base = llmmod.annotate_pair_llm(client, p, model)
		comp = []
		for v in adversarymod.generate_adversarials(p):
			va = llmmod.annotate_pair_llm(client, v, model)
			diff = adversarymod.compare_annotations(base if isinstance(base, dict) else {}, va if isinstance(va, dict) else {})
			comp.append({"attack": v.get("attack"), "diff": diff})
		out.append({"turn_index": p.get("turn_index"), "diffs": comp})
	return {"composer_id": cid, "turns": out}


def _tool_fuzz_seeds(args: Dict[str, Any]) -> Dict[str, Any]:
	seeds = list(args.get("seeds") or [])
	iterations = int(args.get("iterations", 1))
	use_llm = bool(args.get("llm", True))
	res = fuzzmod.run_fuzz(seeds, iterations=iterations, use_llm=use_llm)
	return {"summary": res.get("summary"), "runs": res.get("runs", [])[:1]}


def _tool_qa_index(args: Dict[str, Any]) -> Dict[str, Any]:
	idx = expand_abs(args.get("index_jsonl") or _default_index_path())
	lim = args.get("limit")
	return qamod.analyze_index(idx, lim)


def _tool_name_topics(args: Dict[str, Any]) -> Dict[str, Any]:
	idx = expand_abs(args.get("index_jsonl") or _default_index_path())
	out = args.get("out_json")
	if not out:
		fd, tmp_path = tempfile.mkstemp(prefix="topics_", suffix=".json")
		try:
			os.close(fd)
		except Exception:
			pass
		out = tmp_path
	limit = args.get("limit")
	embed_model = args.get("embed_model")
	min_clusters = int(args.get("min_clusters", 4))
	umap_dim = int(args.get("umap_dim", 2))
	verbose = bool(args.get("verbose", False))
	try:
		res = clustermod.build_toponymy_topics(idx, out, embed_model=embed_model, limit=limit, min_clusters=min_clusters, umap_dim=umap_dim, verbose=verbose)
		# Optionally trim doc topics for brevity
		if not bool(args.get("include_doc_topics", False)) and isinstance(res, dict):
			res = {**res}
			if "topics_per_document" in res:
				res["topics_per_document"] = []
			# Also clip overly long layer label lists
			max_labels = int(args.get("max_layer_labels", 50))
			layers = res.get("layers") if isinstance(res, dict) else None
			if isinstance(layers, list):
				res["layers"] = [layer[:max_labels] if isinstance(layer, list) else layer for layer in layers]
		return {"ok": True, "path": expand_abs(out), "result": res}
	except Exception as e:
		return {"ok": False, "error": str(e)}


def run_toolchat(prompt: str, index_jsonl: Optional[str] = None, vec_db: Optional[str] = None, use_vector: bool = True) -> str:
	"""Run a single chat turn where the model can call the annotations_search tool and respond."""
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	tools = get_tools_schema()

	messages = [{"role": "user", "content": prompt}]
	resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
	# trace first round
	try:
		usage = getattr(resp, "usage", None)
		tracemod.log_llm_event(
			endpoint="chat.completions",
			model=model,
			request_meta={"tools": True},
			response_meta={
				"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
				"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
				"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
			},
			pair=None,
			input_text=prompt,
			output_text=None,
			extra_meta={"op": "toolchat_round1"},
		)
	except Exception:
		pass
	choice = resp.choices[0]
	tool_calls = getattr(choice.message, "tool_calls", None)
	if tool_calls:
		outputs = []
		for tc in tool_calls:
			name = tc.function.name
			try:
				args = json.loads(tc.function.arguments or "{}")
			except Exception:
				args = {}
			# fill defaults from CLI params
			if index_jsonl and "index_jsonl" not in args:
				args["index_jsonl"] = index_jsonl
			if vec_db and "vec_db" not in args:
				args["vec_db"] = vec_db
			if "mode" not in args:
				args["mode"] = "vector" if use_vector else "sparse"
			if name == "annotations_search":
				result = _tool_annotations_search(args)
			elif name == "list_chats":
				result = _tool_list_chats(args)
			elif name == "cat_chat":
				result = _tool_cat_chat(args)
			elif name == "index_jsonl":
				result = _tool_index_jsonl(args)
			elif name == "vec_db_index":
				result = _tool_vec_db_index(args)
			elif name == "sparse_search":
				result = _tool_sparse_search(args)
			elif name == "vec_db_search":
				result = _tool_vec_db_search(args)
			elif name == "hybrid_search":
				result = _tool_hybrid_search(args)
			elif name == "items_search":
				result = _tool_items_search(args)
			elif name == "items_search":
				result = _tool_items_search(args)
			elif name == "items_search":
				result = _tool_items_search(args)
			elif name == "review_chat":
				result = _tool_review_chat(args)
			elif name == "fuzz_seeds":
				result = _tool_fuzz_seeds(args)
			elif name == "qa_index":
				result = _tool_qa_index(args)
			elif name == "name_topics":
				result = _tool_name_topics(args)
			else:
				result = {"error": f"unknown tool {name}"}
			outputs.append({"tool_call_id": tc.id, "name": name, "content": json.dumps(result, ensure_ascii=False)})
		# send tool outputs back
		messages.append({"role": "assistant", "tool_calls": tool_calls})
		for out in outputs:
			messages.append({"role": "tool", "tool_call_id": out["tool_call_id"], "name": out["name"], "content": out["content"]})
		resp2 = client.chat.completions.create(model=model, messages=messages)
		# trace second round
		try:
			usage2 = getattr(resp2, "usage", None)
			tracemod.log_llm_event(
				endpoint="chat.completions",
				model=model,
				request_meta={"tools_followup": True},
				response_meta={
					"prompt_tokens": getattr(usage2, "prompt_tokens", None) if usage2 else None,
					"completion_tokens": getattr(usage2, "completion_tokens", None) if usage2 else None,
					"total_tokens": getattr(usage2, "total_tokens", None) if usage2 else None,
				},
				pair=None,
				input_text=None,
				output_text=resp2.choices[0].message.content or "",
				extra_meta={"op": "toolchat_round2"},
			)
		except Exception:
			pass
		return resp2.choices[0].message.content or ""
	# no tool call, return model text
	return choice.message.content or ""


def run_query_fuzzer_agent(
	seed: str,
	steps: int = 3,
	index_jsonl: Optional[str] = None,
	vec_db: Optional[str] = None,
	use_vector: bool = True,
	table: str = "vec_index",
	qa_mode: bool = False,
) -> Dict[str, Any]:
	"""Iteratively refine a query via an LLM agent that can call search tools.

	At each step, the agent may call tools (sparse/vector/hybrid) to inspect results,
	then propose a next query. Returns an audit trail of steps.
	"""
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	tools = get_tools_schema()
	msgs: List[Dict[str, Any]] = []
	# System instruction guiding iterative retrieval and proposal
	if qa_mode:
		sys_text = (
			"You are a QA/data-quality agent. Goal: improve retrieval and annotation quality."
			" At each step: (1) call qa_index to inspect coverage/missing/tags, and a search tool to sample hits;"
			" (2) propose a refined next_query targeting low-coverage areas or poor ranking signals."
			" Respond STRICT JSON: {next_query: string, rationale: string, mode: 'vector'|'sparse'|'hybrid', k: integer}."
		)
	else:
		sys_text = (
			"You are an iterative retrieval agent. For each step: (1) call search tools to inspect the corpus,"
			" (2) propose a refined next_query and optional tool args. Respond with STRICT JSON:"
			" {next_query: string, rationale: string, mode: 'vector'|'sparse'|'hybrid', k: integer}."
		)
	msgs.append({"role": "system", "content": sys_text})
	current_query = seed
	trail: List[Dict[str, Any]] = []
	seen = {seed}
	idx = expand_abs(index_jsonl) if index_jsonl else _default_index_path()
	db = expand_abs(vec_db) if vec_db else _default_vec_db_path()

	for step in range(max(1, steps)):
		msgs.append({"role": "user", "content": f"Step {step+1}. Current query: {current_query}"})
		# In QA mode, front-load QA stats context
		if qa_mode:
			stats = qamod.analyze_index(idx, None)
			msgs.append({"role": "system", "content": f"QA stats: {json.dumps(stats)[:2000]}"})
		resp = client.chat.completions.create(model=model, messages=msgs, tools=tools)
		try:
			usage = getattr(resp, "usage", None)
			tracemod.log_llm_event(
				endpoint="chat.completions",
				model=model,
				request_meta={"tools": True, "agent_loop": True, "step": step+1},
				response_meta={
					"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
					"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
					"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
				},
				pair=None,
				input_text=msgs[-1]["content"],
				output_text=None,
				extra_meta={"op": "agent_round1"},
			)
		except Exception:
			pass
		choice = resp.choices[0]
		tool_calls = getattr(choice.message, "tool_calls", None)
		used_tools: List[Dict[str, Any]] = []
		if tool_calls:
			outputs = []
			for tc in tool_calls:
				name = tc.function.name
				try:
					args = json.loads(tc.function.arguments or "{}")
				except Exception:
					args = {}
				# fill defaults
				if index_jsonl and "index_jsonl" not in args:
					args["index_jsonl"] = idx
				if vec_db and "db" not in args and "vec_db" not in args:
					args["db"] = db
				if "table" not in args:
					args["table"] = table
				if "k" not in args:
					args["k"] = 8
				if "mode" not in args and name == "annotations_search":
					args["mode"] = ("vector" if use_vector else "sparse")
				# dispatch
				if name == "annotations_search":
					result = _tool_annotations_search(args)
				elif name == "sparse_search":
					result = _tool_sparse_search(args)
				elif name == "vec_db_search":
					result = _tool_vec_db_search(args)
				elif name == "hybrid_search":
					result = _tool_hybrid_search(args)
				else:
					result = {"error": f"unsupported tool in agent: {name}"}
				used_tools.append({"name": name, "args": args, "result_preview": json.dumps(result, ensure_ascii=False)[:800]})
				outputs.append({"tool_call_id": tc.id, "name": name, "content": json.dumps(result, ensure_ascii=False)})
			msgs.append({"role": "assistant", "tool_calls": tool_calls})
			for out in outputs:
				msgs.append({"role": "tool", "tool_call_id": out["tool_call_id"], "name": out["name"], "content": out["content"]})
			resp2 = client.chat.completions.create(model=model, messages=msgs)
			try:
				usage2 = getattr(resp2, "usage", None)
				tracemod.log_llm_event(
					endpoint="chat.completions",
					model=model,
					request_meta={"tools_followup": True, "agent_loop": True, "step": step+1},
					response_meta={
						"prompt_tokens": getattr(usage2, "prompt_tokens", None) if usage2 else None,
						"completion_tokens": getattr(usage2, "completion_tokens", None) if usage2 else None,
						"total_tokens": getattr(usage2, "total_tokens", None) if usage2 else None,
					},
					pair=None,
					input_text=None,
					output_text=resp2.choices[0].message.content or "",
					extra_meta={"op": "agent_round2"},
				)
			except Exception:
				pass
			text = resp2.choices[0].message.content or "{}"
		else:
			text = choice.message.content or "{}"
		# parse JSON
		try:
			obj = json.loads(text)
		except Exception:
			obj = {"next_query": current_query, "rationale": "parse_error"}
		next_query = str(obj.get("next_query") or current_query).strip()
		rationale = str(obj.get("rationale") or "").strip()
		trail.append({
			"step": step + 1,
			"query": current_query,
			"proposed_next": next_query,
			"rationale": rationale[:400],
			"used_tools": used_tools,
		})
		if next_query in seen:
			break
		seen.add(next_query)
		current_query = next_query

	return {"seed": seed, "final_query": current_query, "steps": trail}


def run_tool_agent(
	prompt: str,
	steps: int = 3,
	index_jsonl: Optional[str] = None,
	vec_db: Optional[str] = None,
	use_vector: bool = True,
	table: str = "vec_index",
) -> Dict[str, Any]:
	"""General agent loop that can call any tool in get_tools_schema().

	Returns a transcript of tool calls per step and the final assistant answer.
	"""
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	tools = get_tools_schema()
	msgs: List[Dict[str, Any]] = []
	sys_text = (
		"You are an assistant with tool use. When appropriate, call tools like annotations_search, hybrid_search, "
		"vec_db_search, index_jsonl, vec_db_index, qa_index, list_chats, cat_chat, and name_topics to gather evidence. "
		"Be decisive: only call tools when they will materially improve the answer. "
		"When you have enough evidence, provide a concise answer."
	)
	msgs.append({"role": "system", "content": sys_text})
	msgs.append({"role": "user", "content": prompt})
	trail: List[Dict[str, Any]] = []
	idx = expand_abs(index_jsonl) if index_jsonl else _default_index_path()
	db = expand_abs(vec_db) if vec_db else _default_vec_db_path()

	for step in range(max(1, steps)):
		resp = client.chat.completions.create(model=model, messages=msgs, tools=tools)
		try:
			usage = getattr(resp, "usage", None)
			tracemod.log_llm_event(
				endpoint="chat.completions",
				model=model,
				request_meta={"tools": True, "agent_loop": True, "step": step+1},
				response_meta={
					"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
					"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
					"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
				},
				pair=None,
				input_text=msgs[-1]["content"],
				output_text=None,
				extra_meta={"op": "tool_agent_round1"},
			)
		except Exception:
			pass
		choice = resp.choices[0]
		tool_calls = getattr(choice.message, "tool_calls", None)
		used_tools: List[Dict[str, Any]] = []
		if tool_calls:
			outputs = []
			for tc in tool_calls:
				name = tc.function.name
				try:
					args = json.loads(tc.function.arguments or "{}")
				except Exception:
					args = {}
				# fill defaults
				if index_jsonl and "index_jsonl" not in args:
					args["index_jsonl"] = idx
				if vec_db and "db" not in args and "vec_db" not in args:
					args["db"] = db
				if "table" not in args:
					args["table"] = table
				if "k" not in args:
					args["k"] = 8
				if "mode" not in args and name == "annotations_search":
					args["mode"] = ("vector" if use_vector else "sparse")
				# dispatch to existing handlers
				if name == "annotations_search":
					result = _tool_annotations_search(args)
				elif name == "list_chats":
					result = _tool_list_chats(args)
				elif name == "cat_chat":
					result = _tool_cat_chat(args)
				elif name == "index_jsonl":
					result = _tool_index_jsonl(args)
				elif name == "vec_db_index":
					result = _tool_vec_db_index(args)
				elif name == "sparse_search":
					result = _tool_sparse_search(args)
				elif name == "vec_db_search":
					result = _tool_vec_db_search(args)
				elif name == "hybrid_search":
					result = _tool_hybrid_search(args)
				elif name == "review_chat":
					result = _tool_review_chat(args)
				elif name == "fuzz_seeds":
					result = _tool_fuzz_seeds(args)
				elif name == "qa_index":
					result = _tool_qa_index(args)
				elif name == "name_topics":
					result = _tool_name_topics(args)
				else:
					result = {"error": f"unknown tool {name}"}
				used_tools.append({"name": name, "args": args, "result_preview": json.dumps(result, ensure_ascii=False)[:800]})
				outputs.append({"tool_call_id": tc.id, "name": name, "content": json.dumps(result, ensure_ascii=False)})
			msgs.append({"role": "assistant", "tool_calls": tool_calls})
			for out in outputs:
				msgs.append({"role": "tool", "tool_call_id": out["tool_call_id"], "name": out["name"], "content": out["content"]})
			resp2 = client.chat.completions.create(model=model, messages=msgs)
			try:
				usage2 = getattr(resp2, "usage", None)
				tracemod.log_llm_event(
					endpoint="chat.completions",
					model=model,
					request_meta={"tools_followup": True, "agent_loop": True, "step": step+1},
					response_meta={
						"prompt_tokens": getattr(usage2, "prompt_tokens", None) if usage2 else None,
						"completion_tokens": getattr(usage2, "completion_tokens", None) if usage2 else None,
						"total_tokens": getattr(usage2, "total_tokens", None) if usage2 else None,
					},
					pair=None,
					input_text=None,
					output_text=resp2.choices[0].message.content or "",
					extra_meta={"op": "tool_agent_round2"},
				)
			except Exception:
				pass
			answer = resp2.choices[0].message.content or ""
		else:
			answer = choice.message.content or ""
		trail.append({"step": step + 1, "used_tools": used_tools, "answer": answer[:800]})
		if answer and not tool_calls:
			break

	return {"prompt": prompt, "final_answer": trail[-1]["answer"] if trail else "", "steps": trail}


