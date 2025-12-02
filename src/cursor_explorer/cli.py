import argparse
import json
import os
import sys
import re
from typing import Optional, Dict, List

from .paths import default_db_path, expand_abs
from . import db as dbmod

# Try to import agent backend system
try:
    from agent_explorer.backends import get_backend
    _HAS_AGENT_BACKEND = True
except ImportError:
    _HAS_AGENT_BACKEND = False
from . import parser as parsermod
from . import adversary as adversarymod
from . import annotate as annotatemod
import llm_utils as llmmod
from . import env as envmod
from .formatting import pretty_json_or_text, preview
from . import trace as tracemod
from . import fuzz as fuzzmod
from . import vector as vectmod
from . import rag as ragmod
from . import index as indexmod
from . import toolchat as toolchatmod
from . import qa as qamod
# memory and docs modules removed - functionality may be elsewhere
from . import streams as streammod
from . import cluster as clustermod
from . import multiscale as multiscalemod
from . import memory as memmod
import llm_cache

# Load .env if present (optional dependency). This runs for all CLI commands.
envmod.load_dotenv_if_present()


def human_size(n: int) -> str:
	units = ["B", "KB", "MB", "GB", "TB"]
	u = 0
	v = float(n)
	while v >= 1024.0 and u < len(units) - 1:
		v /= 1024.0
		u += 1
	return f"{v:.1f} {units[u]}"


def _get_table_name(args: argparse.Namespace) -> str:
	"""Get table name for current agent backend."""
	if _HAS_AGENT_BACKEND and hasattr(args, 'agent') and args.agent:
		try:
			backend = get_backend(args.agent)
			return backend.get_table_name()
		except (ValueError, ImportError):
			pass
	# Default to Cursor table name for backward compatibility
	return "cursorDiskKV"


def _get_db_path(args: argparse.Namespace) -> str:
	"""Get database path for current agent backend.
	
	Helper function to get db_path with agent support.
	"""
	agent_type = getattr(args, 'agent', None)
	return expand_abs(args.db or default_db_path(agent_type=agent_type))


def cmd_info(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	table_name = _get_table_name(args)

	print(f"DB: {db_path}")
	if not os.path.exists(db_path):
		print("Exists: no")
		return 2
	print("Exists: yes")
	print(f"Size: {human_size(os.path.getsize(db_path))}")
	try:
		conn = dbmod.connect_readonly(db_path)
		tables = dbmod.list_tables(conn)
		print(f"Tables: {', '.join(tables) if tables else '(none)'}")
		if dbmod.has_table(conn, table_name):
			print(f"{table_name} columns:")
			for col in dbmod.table_info(conn, table_name):
				print(f"  - {col}")
		else:
			print(f"{table_name}: (not found)")
		return 0
	except Exception as e:
		print(f"Error opening DB: {e}", file=sys.stderr)
		return 1


def cmd_tables(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	conn = dbmod.connect_readonly(db_path)
	for name in dbmod.list_tables(conn):
		print(name)
	return 0


def cmd_keys(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	table_name = _get_table_name(args)

	conn = dbmod.connect_readonly(db_path)
	if not dbmod.has_table(conn, table_name):
		print(f"{table_name} not found")
		return 2
	keys = dbmod.kv_keys(conn, prefix=args.prefix, like=args.like, limit=args.limit, table=table_name)
	for k in keys:
		print(k)
	return 0


def cmd_search(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	table_name = _get_table_name(args)
	conn = dbmod.connect_readonly(db_path)
	rows = dbmod.search_kv(conn, key_like=args.key_like, value_contains=args.contains, limit=args.limit, table=table_name)
	for k, size in rows:
		print(f"{k}\t{size}")
	return 0


def cmd_show(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	table_name = _get_table_name(args)
	conn = dbmod.connect_readonly(db_path)
	val = dbmod.kv_value(conn, args.key, table=table_name)
	if val is None:
		print("(no value)")
		return 2
	text, is_json = pretty_json_or_text(val)
	if not is_json and args.preview:
		text = preview(text, max_len=args.preview)
	print(text)
	return 0


def cmd_chats(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	table_name = _get_table_name(args)
	conn = dbmod.connect_readonly(db_path)
	keys = dbmod.composer_data_keys(conn, limit=args.limit, table=table_name)
	printed = False
	if not keys:
		print("composerData:00000000-0000-0000-0000-000000000000\t(placeholder)")
		return 0
	for k in keys:
		val = dbmod.kv_value(conn, k, table=table_name)
		if val is None:
			continue
		text, is_json = pretty_json_or_text(val)
		if is_json:
			try:
				obj = json.loads(text)
				title = obj.get("title") or obj.get("name") or obj.get("id")
				print(f"{k}\t{title if title else ''}")
				printed = True
			except Exception:
				print(k)
				printed = True
		else:
			print(k)
			printed = True
	if not printed:
		print("composerData:00000000-0000-0000-0000-000000000000\t(placeholder)")
	return 0


def cmd_convo(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	conn = dbmod.connect_readonly(db_path)
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	if not messages:
		print("(no messages)")
		return 2
	for m in messages:
		role = m.get("role")
		text = m.get("text", "")
		print(f"[{role}] {text[:2000]}")
	return 0


def cmd_dump(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	conn = dbmod.connect_readonly(db_path)
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	print(json.dumps(messages, ensure_ascii=False, indent=2))
	return 0


def cmd_pairs(args: argparse.Namespace) -> int:
	agent_type = getattr(args, 'agent', None)
	db_path = expand_abs(args.db or default_db_path(agent_type=agent_type))
	conn = dbmod.connect_readonly(db_path)
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	pairs = parsermod.build_qa_pairs(messages)
	if args.annotate:
		if args.llm:
			client = llmmod.require_client()
			model = args.llm_model or os.getenv("OPENAI_MODEL", "gpt-5")
			for p in pairs:
				p["annotations"] = llmmod.annotate_pair_llm(client, p, model)
			if args.rich:
				summary = llmmod.summarize_conversation_llm(client, pairs, model)
				print(json.dumps({"pairs": pairs, "summary": summary}, ensure_ascii=False, indent=2))
				return 0
		else:
			for p in pairs:
				if args.rich:
					p["annotations"] = annotatemod.annotate_pair_rich(p)
				else:
					p["annotations"] = annotatemod.annotate_pair_simple(p)
			if args.rich:
				summary = annotatemod.annotate_conversation_scales(pairs)
				print(json.dumps({"pairs": pairs, "summary": summary}, ensure_ascii=False, indent=2))
				return 0
	print(json.dumps(pairs, ensure_ascii=False, indent=2))
	return 0


def cmd_adversarial(args: argparse.Namespace) -> int:
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	pairs = parsermod.build_qa_pairs(messages)
	out = []
	for p in pairs:
		variants = adversarymod.generate_adversarials(p)
		for v in variants:
			analysis = adversarymod.analyze_pair(v)
			out.append({"base_turn": p.get("turn_index"), **v, "analysis": analysis})
	print(json.dumps(out, ensure_ascii=False, indent=2))
	return 0


def cmd_prompt(args: argparse.Namespace) -> int:
	client = llmmod.require_client()
	model = args.llm_model or os.getenv("OPENAI_MODEL", "gpt-5")
	# Load prompt template from file
	template_path = os.path.join("prompts", args.template)
	if not os.path.exists(template_path):
		print(f"Error: Template not found: {template_path}", file=sys.stderr)
		return 2
	with open(template_path, "r") as f:
		template = f.read()
	# Render variables
	variables = {}
	for kv in (args.var or []):
		if "=" in kv:
			k, v = kv.split("=", 1)
			variables[k] = v
	body = template
	for k, v in variables.items():
		body = body.replace(f"{{{k}}}", v)
	resp = client.chat.completions.create(
		model=model,
		messages=[{"role": "user", "content": body}],
		temperature=args.temperature,
	)
	text = resp.choices[0].message.content or ""
	print(text)
	return 0


def cmd_scales(args: argparse.Namespace) -> int:
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	pairs = parsermod.build_qa_pairs(messages)
	result = {"heuristic": annotatemod.annotate_conversation_scales(pairs)}
	if getattr(args, "llm", False):
		client = llmmod.require_client()
		model = args.llm_model or os.getenv("OPENAI_MODEL", "gpt-5")
		result["llm"] = llmmod.summarize_conversation_llm(client, pairs, model)
	print(json.dumps(result, ensure_ascii=False, indent=2))
	return 0


def cmd_fuzz(args: argparse.Namespace) -> int:
	seeds = fuzzmod.read_seeds(getattr(args, "seed", None), getattr(args, "seed_file", None))
	if not seeds:
		print(json.dumps({"error": "no seeds provided"}))
		return 2
	result = fuzzmod.run_fuzz(seeds, iterations=args.iterations, use_llm=args.llm, llm_model=args.llm_model)
	# Optionally emit a concise audit trail per iteration
	if getattr(args, "emit_trace_summary", False):
		trail = []
		for r in result.get("runs", []):
			trail.append({
				"iteration": r.get("iteration"),
				"inputs": r.get("inputs", []),
				"next_seeds": r.get("next_seeds", []),
				"top_candidates": r.get("candidates", [])[:5],
			})
		result["audit_trail"] = trail
	print(json.dumps(result, ensure_ascii=False, indent=2))
	return 0


def _build_corpus(conn, composer_id: str, scope: str):
	messages = parsermod.reconstruct_conversation(conn, composer_id)
	if scope == "messages":
		items = []
		for i, m in enumerate(messages):
			text = m.get("text", "") or ""
			items.append({
				"id": f"msg:{i}",
				"text": text,
				"preview": (text or "")[:200],
			})
		return items
	# default: pairs
	pairs = parsermod.build_qa_pairs(messages)
	items = []
	for p in pairs:
		user = p.get("user", "") or ""
		assistant = p.get("assistant", "") or ""
		combined = (user + "\n\n" + assistant).strip()
		items.append({
			"id": f"pair:{p.get('turn_index')}",
			"text": combined,
			"preview": combined[:200],
		})
	return items


def cmd_index_embeds(args: argparse.Namespace) -> int:
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	items = _build_corpus(conn, args.composer_id, args.scope)
	if not items:
		print(json.dumps({"error": "no items"}))
		return 2
	client = llmmod.require_client()
	model = args.embed_model or os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	texts = [it["text"] for it in items]
	_ = llmmod.embed_texts(client, texts, model=model, scope=f"{args.scope}:{args.composer_id}")
	print(json.dumps({"indexed": len(items), "model": model, "scope": args.scope}))
	return 0


def cmd_vsearch(args: argparse.Namespace) -> int:
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	items = _build_corpus(conn, args.composer_id, args.scope)
	if not items:
		print(json.dumps({"error": "no items"}))
		return 2
	client = llmmod.require_client()
	model = args.embed_model or os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	# Embed corpus (cached) and query
	texts = [it["text"] for it in items]
	corpus_vecs = llmmod.embed_texts(client, texts, model=model, scope=f"{args.scope}:{args.composer_id}")
	qvec = llmmod.embed_text(client, args.query, model=model, scope="query", ident="q")
	# Rank
	scored = vectmod.topk(qvec, corpus_vecs, args.topk)
	out = []
	for idx, score in scored:
		it = items[idx]
		out.append({"id": it["id"], "score": round(float(score), 6), "preview": it["preview"]})
	print(json.dumps(out, ensure_ascii=False, indent=2))
	return 0

def cmd_review(args: argparse.Namespace) -> int:
	# Review annotations for real chats: base vs adversarial variants
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	pairs = parsermod.build_qa_pairs(messages)
	if not pairs:
		print(json.dumps({"error": "no pairs"}))
		return 2
	client = llmmod.require_client()
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	turns = []
	judging_inputs = []
	for p in pairs:
		base_ann = llmmod.annotate_pair_llm(client, p, model)
		variants_out = []
		for v in adversarymod.generate_adversarials(p):
			v_ann = llmmod.annotate_pair_llm(client, v, model)
			diff = adversarymod.compare_annotations(base_ann if isinstance(base_ann, dict) else {}, v_ann if isinstance(v_ann, dict) else {})
			variants_out.append({
				"attack": v.get("attack"),
				"variant": {"user": v.get("user", ""), "assistant": v.get("assistant", "")},
				"patterns": {
					"user": adversarymod.detect_patterns(v.get("user", "")),
					"assistant": adversarymod.detect_patterns(v.get("assistant", "")),
				},
				"llm": v_ann,
				"diff": diff,
			})
		turns.append({
			"turn_index": p.get("turn_index"),
			"base": {"user": p.get("user", ""), "assistant": p.get("assistant", "")},
			"base_llm": base_ann,
			"variants": variants_out,
		})
		judging_inputs.append({
			"composer_id": p.get("composer_id"),
			"turn_index": p.get("turn_index"),
			"user_head": (p.get("user") or "").splitlines()[0][:160],
			"assistant_head": (p.get("assistant") or "").splitlines()[0][:200],
			"annotations": base_ann,
		})
	# Judge a random-ish slice of inputs
	judgment = llmmod.judge_annotations_llm(client, judging_inputs[:10], model)
	meta = llmmod.meta_judge_llm(client, [judgment], model)
	print(json.dumps({"composer_id": args.composer_id, "model": model, "turns": turns, "judgment": judgment, "meta": meta}, ensure_ascii=False, indent=2))
	return 0


def cmd_rag(args: argparse.Namespace) -> int:
	# Build index from a real conversation and retrieve items by seed queries
	conn = dbmod.connect_readonly(expand_abs(args.db or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, args.composer_id)
	items = ragmod.build_turn_items(messages)
	results: Dict[str, list] = {}
	for q in (args.query or []):
		hits = ragmod.search_items(items, q, k=args.k)
		results[q] = [{
			"id": f"{it.get('composer_id')}:{it.get('turn_index')}",
			"user_head": it.get("user_head"),
			"assistant_head": it.get("assistant_head"),
			"annotations": it.get("annotations"),
		} for it in hits]
	print(json.dumps({"composer_id": args.composer_id, "results": results}, ensure_ascii=False, indent=2))
	return 0


def cmd_vec_db_search(args: argparse.Namespace) -> int:
	# Validate table name to avoid SQL injection in f-strings
	if not re.fullmatch(r"[A-Za-z0-9_]+", args.table or ""):
		print(json.dumps({"error": "invalid table name"}))
		return 2
	result = indexmod.vec_search(args.db, args.table, args.query, args.k)
	print(json.dumps(result, ensure_ascii=False, indent=2))
	return 0

def cmd_index(args: argparse.Namespace) -> int:
	count = indexmod.build_index(args.out, db_path=args.db, limit_composers=args.limit_composers, max_turns_per=args.max_turns)
	result: Dict[str, object] = {"wrote": count, "path": args.out}
	# Optionally run Toponymy naming on the full index
	if getattr(args, "topics_out", None):
		try:
			top = clustermod.build_toponymy_topics(
				args.out,
				args.topics_out,
				embed_model=getattr(args, "topics_embed_model", None),
				limit=getattr(args, "topics_limit", None),
				min_clusters=getattr(args, "topics_min_clusters", 4),
				umap_dim=getattr(args, "topics_umap_dim", 2),
				verbose=getattr(args, "topics_verbose", False),
			)
			result["topics_path"] = args.topics_out
			meta = (top or {}).get("meta", {}) if isinstance(top, dict) else {}
			result["topics_count"] = meta.get("count")
		except Exception as e:
			result["topics_error"] = str(e)
	print(json.dumps(result))
	return 0


def cmd_sample(args: argparse.Namespace) -> int:
	items = indexmod.sample_index(args.path, args.n)
	print(json.dumps(items, ensure_ascii=False, indent=2))
	return 0


def cmd_docs_index(args: argparse.Namespace) -> int:
	# docs module not available - return error
	print(json.dumps({"error": "docs module not available", "path": expand_abs(args.out)}, ensure_ascii=False, indent=2))
	return 1


def cmd_ingest(args: argparse.Namespace) -> int:
	"""Unified ingest for multiple sources into JSONL items schema.

	Sources:
	- cursor: reads Cursor DB and writes JSONL (uses build_index)
	- markdown: walks a directory of Markdown files
	"""
	src = (args.source or "").lower()
	if src == "cursor":
		count = indexmod.build_index(args.out, db_path=args.db, limit_composers=args.limit_composers, max_turns_per=args.max_turns)
		print(json.dumps({"wrote": count, "path": expand_abs(args.out)}))
		return 0
	elif src in {"markdown", "md"}:
		if not getattr(args, "root", None):
			print(json.dumps({"error": "root directory required for markdown source"}))
			return 2
		# docs module not available
		print(json.dumps({"error": "docs module not available", "path": expand_abs(args.out)}, ensure_ascii=False, indent=2))
		return 1
	else:
		print(json.dumps({"error": f"unsupported source: {args.source}"}))
		return 2


def cmd_auto_titles(args: argparse.Namespace) -> int:
	# Derive simple titles from per-composer conversations using LLM summaries (fast model by default)
	try:
		client = llmmod.require_client() if args.use_llm else None
	except Exception:
		client = None
	index_path = expand_abs(args.index_jsonl)
	by_cid: Dict[str, List[Dict]] = {}
	with open(index_path, "r", encoding="utf-8") as f:
		for line in f:
			try:
				it = json.loads(line)
			except Exception:
				continue
			cid = it.get("composer_id")
			if cid is None:
				continue
			by_cid.setdefault(cid, []).append(it)
	# Build titles
	results: Dict[str, Dict] = {}
	model = args.model or os.getenv("OPENAI_SMALL_MODEL", "gpt-5-nano")
	for cid, items in by_cid.items():
		pairs = []
		for it in sorted(items, key=lambda x: int(x.get("turn_index") or 0))[: args.max_turns]:
			pairs.append({
				"turn_index": it.get("turn_index"),
				"user": it.get("user", ""),
				"assistant": it.get("assistant", ""),
			})
		macro = ""
		if client is not None and args.use_llm:
			try:
				j = llmmod.summarize_conversation_llm(client, pairs, model=model)
				macro = (j.get("macro") or "").strip()
			except Exception:
				macro = ""
		if not macro:
			for it in items:
				u = (it.get("user_head") or it.get("user") or "").strip()
				if u:
					macro = u[:120]
					break
		repo = None
		for it in items:
			repo = it.get("repo")
			if repo:
				break
		results[cid] = {"title": macro or "", "repo": repo}
	# Write
	out = expand_abs(args.out_json)
	with open(out, "w", encoding="utf-8") as f:
		json.dump({"titles": results, "meta": {"count": len(results), "model": model, "used_llm": bool(client and args.use_llm)}}, f, ensure_ascii=False, indent=2)
	print(json.dumps({"wrote": out, "count": len(results)}))
	return 0


def build_parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(
		prog=os.path.basename(sys.argv[0]),
		description="Explore Cursor chats in state.vscdb",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)

	# Shared parent so --db can appear after the subcommand as well
	parent = argparse.ArgumentParser(add_help=False, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parent.add_argument("--db", help="Path to agent state database (defaults via AGENT_STATE_DB or platform-specific path)")
	if _HAS_AGENT_BACKEND:
		parent.add_argument("--agent", help="Agent type (cursor, cline, etc.). Defaults to 'cursor'.")
	parent.add_argument("--trace-meta", action="append", help="Tracing metadata key=value; repeatable")

	sub = p.add_subparsers(dest="cmd", required=True)

	sp = sub.add_parser("info", parents=[parent], help="Show DB info and basic table details")
	sp.set_defaults(func=cmd_info)

	sp = sub.add_parser("tables", parents=[parent], help="List tables")
	sp.set_defaults(func=cmd_tables)

	sp = sub.add_parser("keys", parents=[parent], help="List keys in agent key-value table")
	sp.add_argument("--prefix", help="Prefix filter (e.g. composerData:)")
	sp.add_argument("--like", help="LIKE pattern (e.g. %%foo%%)")
	sp.add_argument("--limit", type=int, default=50)
	sp.set_defaults(func=cmd_keys)

	sp = sub.add_parser("search", parents=[parent], help="Search keys/values in agent key-value table")
	sp.add_argument("--key-like", help="Key LIKE pattern (e.g. %%foo%%)")
	sp.add_argument("--contains", help="Substring to search in values")
	sp.add_argument("--limit", type=int, default=50)
	sp.set_defaults(func=cmd_search)

	sp = sub.add_parser("show", parents=[parent], help="Show value for a specific key")
	sp.add_argument("key", help="Exact key")
	sp.add_argument("--preview", type=int, help="Limit non-JSON output to N chars")
	sp.set_defaults(func=cmd_show)

	sp = sub.add_parser("chats", parents=[parent], help="List composerData:* entries with optional titles")
	sp.add_argument("--limit", type=int, default=200)
	sp.set_defaults(func=cmd_chats)

	sp = sub.add_parser("convo", parents=[parent], help="Print a reconstructed conversation for a composer_id")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.set_defaults(func=cmd_convo)

	sp = sub.add_parser("dump", parents=[parent], help="Dump reconstructed conversation JSON for a composer_id")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.set_defaults(func=cmd_dump)

	sp = sub.add_parser("pairs", parents=[parent], help="Emit user-assistant pairs for a composer_id")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.add_argument("--annotate", action="store_true", help="Compute annotations for search filters")
	sp.add_argument("--rich", action="store_true", help="Use richer annotations and include convo-level summary")
	sp.add_argument("--llm", action="store_true", help="Use LLM for annotations/summaries")
	sp.add_argument("--llm-model", help="Override LLM model (reads OPENAI_MODEL if unset)")
	sp.set_defaults(func=cmd_pairs)

	sp = sub.add_parser("adversarial", parents=[parent], help="Generate adversarial variants and pattern analysis")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.set_defaults(func=cmd_adversarial)

	sp = sub.add_parser("prompt", parents=[parent], help="Run an LLM with a prompt template and variables")
	sp.add_argument("template", help="Path to a prompt template file")
	sp.add_argument("--var", action="append", help="Template variable in key=value form; repeatable")
	sp.add_argument("--llm-model", help="Override LLM model (reads OPENAI_MODEL if unset)")
	sp.add_argument("--temperature", type=float, default=0.2)
	sp.set_defaults(func=cmd_prompt)

	sp = sub.add_parser("scales", parents=[parent], help="Show heuristic vs optional LLM micro/meso/macro summary")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.add_argument("--llm", action="store_true", help="Include LLM-based summary as well")
	sp.add_argument("--llm-model", help="Override LLM model (reads OPENAI_MODEL if unset)")
	sp.set_defaults(func=cmd_scales)

	sp = sub.add_parser("fuzz", parents=[parent], help="Adversarial fuzzing loop over seeds with breadcrumbs")
	sp.add_argument("--seed", action="append", help="Seed user text; repeatable")
	sp.add_argument("--seed-file", help="Path to a file of seeds (one per line)")
	sp.add_argument("--iterations", type=int, default=1)
	sp.add_argument("--llm", action="store_true", help="Use LLM annotations as well")
	sp.add_argument("--llm-model", help="Override LLM model (reads OPENAI_MODEL if unset)")
	sp.add_argument("--emit-trace-summary", action="store_true", help="Also print iteration summaries to stdout for auditing")
	sp.set_defaults(func=cmd_fuzz)

	sp = sub.add_parser("index-embeds", parents=[parent], help="Precompute and cache embeddings for a conversation (local cache)")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.add_argument("--scope", choices=["pairs", "messages"], default="pairs")
	sp.add_argument("--embed-model", help="Embedding model (env: OPENAI_EMBED_MODEL > EMBEDDING_MODEL)")
	sp.set_defaults(func=cmd_index_embeds)

	sp = sub.add_parser("vsearch", parents=[parent], help="Semantic search within a conversation by embeddings (uses cached embeddings)")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.add_argument("--scope", choices=["pairs", "messages"], default="pairs")
	sp.add_argument("--query", required=True, help="Search query text")
	sp.add_argument("--topk", type=int, default=10)
	sp.add_argument("--embed-model", help="Embedding model (env: OPENAI_EMBED_MODEL > EMBEDDING_MODEL)")
	sp.set_defaults(func=cmd_vsearch)

	sp = sub.add_parser("review", parents=[parent], help="Review LLM annotations on real chat pairs vs adversarial variants")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.set_defaults(func=cmd_review)

	sp = sub.add_parser("rag", parents=[parent], help="Retrieve turns by query over heads and annotations")
	sp.add_argument("composer_id", help="Composer UUID")
	sp.add_argument("--query", action="append", help="Seed query; repeatable")
	sp.add_argument("-k", type=int, default=8)
	sp.set_defaults(func=cmd_rag)

	sp = sub.add_parser("index", parents=[parent], help="Pre-index all chats into a JSONL for random sampling and search")
	sp.add_argument("out", help="Output JSONL path")
	sp.add_argument("--limit-composers", type=int)
	sp.add_argument("--max-turns", type=int)
	# Optional: also run Toponymy naming over the built index
	sp.add_argument("--topics-out", help="Also write Toponymy topics JSON (optional dependency)")
	sp.add_argument("--topics-embed-model", help="Embedding model for initial vectors (env: OPENAI_EMBED_MODEL > EMBEDDING_MODEL)")
	sp.add_argument("--topics-limit", type=int, help="Limit number of items for naming")
	sp.add_argument("--topics-min-clusters", type=int, default=4)
	sp.add_argument("--topics-umap-dim", type=int, default=2)
	sp.add_argument("--topics-verbose", action="store_true")
	sp.set_defaults(func=cmd_index)

	sp = sub.add_parser("sample", parents=[parent], help="Reservoir sample N items from a JSONL index")
	sp.add_argument("path", help="Index JSONL path")
	sp.add_argument("n", type=int)
	sp.set_defaults(func=cmd_sample)

	# Markdown/Docs indexing
	sp = sub.add_parser("docs-index", parents=[parent], help="Index Markdown files under a directory into JSONL")
	sp.add_argument("root", help="Root directory (e.g., an Obsidian vault folder)")
	sp.add_argument("out", help="Output JSONL path")
	sp.add_argument("--ext", action="append", help="File extension to include (repeatable). Defaults: .md,.markdown,.mdown,.mkd")
	sp.add_argument("--include-hidden", action="store_true", help="Include dotfiles and dot-directories")
	sp.set_defaults(func=cmd_docs_index)

	# Unified ingest pipeline (extensible)
	sp = sub.add_parser("ingest", parents=[parent], help="Ingest from a source into JSONL (sources: cursor, markdown)")
	sp.add_argument("--source", required=True, help="Source type: cursor|markdown")
	sp.add_argument("--out", required=True, help="Output JSONL path")
	# cursor options
	sp.add_argument("--limit-composers", type=int)
	sp.add_argument("--max-turns", type=int)
	# markdown options
	sp.add_argument("--root", help="Root directory for markdown source")
	sp.add_argument("--ext", action="append", help="Markdown extensions to include; repeatable")
	sp.add_argument("--include-hidden", action="store_true")
	sp.set_defaults(func=cmd_ingest)

	sp = sub.add_parser("auto-titles", parents=[parent], help="Auto-generate per-chat titles (LLM optional; falls back to heuristics)")
	sp.add_argument("index_jsonl", help="Index JSONL path")
	sp.add_argument("out_json", help="Output titles JSON path")
	sp.add_argument("--model")
	sp.add_argument("--use-llm", action="store_true")
	sp.add_argument("--max-turns", type=int, default=30)
	sp.set_defaults(func=cmd_auto_titles)

	sp = sub.add_parser("vec-index", parents=[parent], help="Build sqlite-vec DB from a JSONL index (requires sqlite-vec)")
	sp.add_argument("out_db", help="Output SQLite DB path (will load sqlite-vec)")
	sp.add_argument("index_jsonl", help="Source JSONL index path")
	sp.add_argument("--table", default="vec_index")
	sp.set_defaults(func=lambda a: print(json.dumps({
		"wrote": indexmod.build_embeddings_sqlite(a.out_db, a.index_jsonl, a.table),
		"db": a.out_db,
		"table": a.table,
	}, ensure_ascii=False)))

	# Back-compat alias: vec-db-index
	sp = sub.add_parser("vec-db-index", parents=[parent], help="Build sqlite-vec DB from a JSONL index (requires sqlite-vec)")
	sp.add_argument("out_db", help="Output SQLite DB path (will load sqlite-vec)")
	sp.add_argument("index_jsonl", help="Source JSONL index path")
	sp.add_argument("--table", default="vec_index")
	sp.set_defaults(func=lambda a: print(json.dumps({
		"wrote": indexmod.build_embeddings_sqlite(a.out_db, a.index_jsonl, a.table),
		"db": a.out_db,
		"table": a.table,
	}, ensure_ascii=False)))

	sp = sub.add_parser("vec-search", parents=[parent], help="Vector search the sqlite-vec DB for a query")
	sp.add_argument("db", help="SQLite DB path with sqlite-vec index")
	sp.add_argument("--table", default="vec_index")
	sp.add_argument("--query", required=True)
	sp.add_argument("--k", type=int, default=8)
	sp.set_defaults(func=cmd_vec_db_search)

	# Back-compat alias: vec-db-search
	sp = sub.add_parser("vec-db-search", parents=[parent], help="Vector search the sqlite-vec DB for a query")
	sp.add_argument("db", help="SQLite DB path with sqlite-vec index")
	sp.add_argument("--table", default="vec_index")
	sp.add_argument("--query", required=True)
	sp.add_argument("--k", type=int, default=8)
	sp.set_defaults(func=cmd_vec_db_search)

	# SQLite sparse search over items table
	def _cmd_sqlite_search(a: argparse.Namespace) -> int:
		try:
			rows = indexmod.items_search(a.db, a.table, a.query, a.k)
			print(json.dumps({"items": rows}, ensure_ascii=False, indent=2))
			return 0
		except ValueError as e:
			print(json.dumps({"error": str(e)}))
			return 2

	sp = sub.add_parser("sqlite-search", parents=[parent], help="Sparse search over per-turn items in SQLite DB")
	sp.add_argument("db", help="SQLite DB path with items table")
	sp.add_argument("--table", default="items")
	sp.add_argument("--query", required=True)
	sp.add_argument("--k", type=int, default=8)
	sp.set_defaults(func=_cmd_sqlite_search)

	# SQLite per-turn items index (idempotent upsert)
	sp = sub.add_parser("sqlite-index", parents=[parent], help="Write per-turn items into a SQLite table (idempotent upsert)")
	sp.add_argument("out_db", help="Output SQLite DB path")
	sp.add_argument("--table", default="items")
	sp.add_argument("--limit-composers", type=int)
	sp.add_argument("--max-turns", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps({
		"wrote": indexmod.build_index_sqlite(a.out_db, a.db, a.table, a.limit_composers, a.max_turns)
	})))

	# Build/refresh sqlite-vec from items table
	sp = sub.add_parser("vec-from-items", parents=[parent], help="Build/refresh sqlite-vec embeddings from a SQLite items table")
	sp.add_argument("db", help="SQLite DB path (contains items table; will hold vec tables)")
	sp.add_argument("--items-table", default="items")
	sp.add_argument("--vec-table", default="vec_index")
	def _cmd_vec_from_items(a: argparse.Namespace) -> int:
		wrote = indexmod.build_embeddings_sqlite_from_items(a.db, a.items_table, a.vec_table)
		print(json.dumps({
			"wrote": wrote,
			"db": a.db,
			"items_table": a.items_table,
			"vec_table": a.vec_table,
		}, ensure_ascii=False))
		return 0
	sp.set_defaults(func=_cmd_vec_from_items)

	sp = sub.add_parser("toolchat", parents=[parent], help="Chat with an LLM that can call an annotations search tool")
	sp.add_argument("--prompt", required=True)
	sp.add_argument("--index-jsonl")
	sp.add_argument("--vec-db")
	sp.add_argument("--sparse", action="store_true", help="Force sparse search mode (default uses vector)")
	sp.set_defaults(func=lambda a: print(toolchatmod.run_toolchat(a.prompt, a.index_jsonl, a.vec_db, use_vector=not a.sparse)))

	sp = sub.add_parser("agent", parents=[parent], help="Playground multi-tool agent loop (calls any exposed tools)")
	sp.add_argument("--prompt", required=True)
	sp.add_argument("--steps", type=int, default=3)
	sp.add_argument("--index-jsonl")
	sp.add_argument("--vec-db")
	sp.add_argument("--table", default="vec_index")
	sp.add_argument("--sparse", action="store_true", help="Prefer sparse mode for annotations_search")
	sp.set_defaults(func=lambda a: print(json.dumps(toolchatmod.run_tool_agent(a.prompt, a.steps, a.index_jsonl, a.vec_db, use_vector=not a.sparse, table=a.table), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("fuzz-agent", parents=[parent], help="Iteratively refine a query via an agent that calls search tools")
	sp.add_argument("--seed", required=True, help="Initial query")
	sp.add_argument("--steps", type=int, default=3)
	sp.add_argument("--index-jsonl")
	sp.add_argument("--vec-db")
	sp.add_argument("--sparse", action="store_true")
	sp.add_argument("--table", default="vec_index")
	sp.add_argument("--qa", action="store_true", help="Prime agent for QA/data quality (coverage, missing, ranking sanity)")
	sp.set_defaults(func=lambda a: print(json.dumps(toolchatmod.run_query_fuzzer_agent(a.seed, a.steps, a.index_jsonl, a.vec_db, use_vector=not a.sparse, table=a.table, qa_mode=a.qa), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("qa", parents=[parent], help="Data-quality scan over a JSONL index of turns+annotations")
	sp.add_argument("path", help="Index JSONL path")
	sp.add_argument("--limit", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps(qamod.analyze_index(a.path, a.limit), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("qa-db", parents=[parent], help="Low-level DB QA: bubbles/headers parsing, coalescing, pairs completeness")
	sp.add_argument("--limit-composers", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps(qamod.analyze_db(getattr(a, "db", None), a.limit_composers), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("qa-llm-sample", parents=[parent], help="LLM-based sample: find issues per item in the index (requires OPENAI_API_KEY)")
	sp.add_argument("index_jsonl", help="Index JSONL path")
	sp.add_argument("--n", type=int, default=40)
	sp.add_argument("--model", help="Override LLM model")
	sp.set_defaults(func=lambda a: print(json.dumps(qamod.llm_find_issues(a.index_jsonl, n=a.n, model=a.model), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("qa-llm-aggregate", parents=[parent], help="Aggregate LLM findings with stats into prioritized issues")
	sp.add_argument("findings_json", help="Path to findings JSON from qa-llm-sample")
	sp.add_argument("--index-jsonl", help="Optional index JSONL for stats")
	sp.add_argument("--limit", type=int, help="Limit for stats computations")
	sp.add_argument("--model", help="Override LLM model")
	def _agg(a):
		findings = json.loads(open(expand_abs(a.findings_json), "r", encoding="utf-8").read())
		stats_index = qamod.analyze_index(a.index_jsonl, a.limit) if getattr(a, "index_jsonl", None) else None
		stats_db = qamod.analyze_db(getattr(a, "db", None), None) if getattr(a, "db", None) else None
		res = qamod.llm_aggregate_findings(findings, stats_index, stats_db, a.model)
		print(json.dumps({"findings_sample": len(findings.get("items", [])), "summary": res.get("summary")}, ensure_ascii=False, indent=2))
	sp.set_defaults(func=_agg)

	sp = sub.add_parser("cluster-index", parents=[parent], help="Cluster the corpus into a binary tree with K=2 splits and write JSON")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output tree JSON path")
	sp.add_argument("--depth", type=int, default=3)
	sp.add_argument("--min-size", type=int, default=20)
	sp.add_argument("--limit", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps(clustermod.build_cluster_tree(a.index_jsonl, a.out_json, a.depth, a.min_size, limit=a.limit), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("cluster-summarize", parents=[parent], help="LLM summaries per cluster node (titles/themes/risks/labels)")
	sp.add_argument("tree_json", help="Cluster tree JSON")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output summarized tree JSON path")
	sp.set_defaults(func=lambda a: print(json.dumps(clustermod.summarize_clusters(a.tree_json, a.index_jsonl, a.out_json), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("cluster-evoc", parents=[parent], help="Cluster corpus with EVōC into layered clusters and write JSON")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output EVōC clusters JSON path")
	sp.add_argument("--limit", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps(clustermod.build_evoc_clusters(a.index_jsonl, a.out_json, limit=a.limit), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("name-topics", parents=[parent], help="Generate layered topic names with Toponymy (optional dependency)")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output Toponymy topics JSON path")
	sp.add_argument("--limit", type=int)
	sp.add_argument("--embed-model", help="Embedding model for initial vectors (env: OPENAI_EMBED_MODEL > EMBEDDING_MODEL)")
	sp.add_argument("--min-clusters", type=int, default=4)
	sp.add_argument("--umap-dim", type=int, default=2)
	sp.add_argument("--verbose", action="store_true")
	sp.set_defaults(func=lambda a: print(json.dumps(clustermod.build_toponymy_topics(a.index_jsonl, a.out_json, embed_model=a.embed_model, limit=a.limit, min_clusters=a.min_clusters, umap_dim=a.umap_dim, verbose=a.verbose), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("mem-extract", parents=[parent], help="Extract long-term memory (preferences, decisions, todos, tech) from index JSONL")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output memory JSON path")
	sp.add_argument("--limit", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps(memmod.extract_memory(a.index_jsonl, a.out_json, limit=a.limit), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("mem-search", parents=[parent], help="Search extracted memory JSON with token overlap")
	sp.add_argument("memory_json", help="Memory JSON path from mem-extract")
	sp.add_argument("--query", required=True)
	sp.add_argument("--k", type=int, default=10)
	sp.set_defaults(func=lambda a: print(json.dumps({"error": "memory module not available"}, ensure_ascii=False, indent=2)))

	# Rules extraction with signals
	sp = sub.add_parser("rules-extract", parents=[parent], help="Extract user rules (preferences/decisions) with clarity/context and satisfaction signals")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output rules JSON path")
	sp.add_argument("--limit", type=int)
	sp.set_defaults(func=lambda a: print(json.dumps({"error": "memory module not available"}, ensure_ascii=False, indent=2)))

	sp = sub.add_parser("streams", parents=[parent], help="Analyze user message transitions into streams and label transitions")
	sp.add_argument("index_jsonl", help="Source index JSONL path")
	sp.add_argument("out_json", help="Output streams JSON path")
	sp.add_argument("--limit", type=int)
	sp.add_argument("--min-similarity", type=float, default=0.3)
	sp.add_argument("--embeddings", action="store_true")
	sp.add_argument("--ngram-min", type=int, default=1, help="Min n for token n-grams")
	sp.add_argument("--ngram-max", type=int, default=1, help="Max n for token n-grams")
	sp.add_argument("--group-topk", type=int, default=8, help="Top group-level n-grams to keep")
	sp.set_defaults(func=lambda a: print(json.dumps(streammod.analyze_user_transitions(a.index_jsonl, a.out_json, limit=a.limit, min_similarity=a.min_similarity, use_embeddings=a.embeddings, ngram_min=a.ngram_min, ngram_max=a.ngram_max, group_topk=a.group_topk), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("streams-summarize", parents=[parent], help="LLM summarize streams into topic/progress/open questions/next steps")
	sp.add_argument("streams_json", help="Input streams JSON path")
	sp.add_argument("out_json", help="Output summarized streams JSON path")
	sp.add_argument("--model")
	sp.add_argument("--max-streams", type=int)
	sp.add_argument("--max-ids", type=int, default=10)
	sp.set_defaults(func=lambda a: print(json.dumps(streammod.summarize_streams(a.streams_json, a.out_json, model=a.model, max_streams=a.max_streams, max_ids=a.max_ids), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("streams-summarize-recursive", parents=[parent], help="Hierarchical (RAPTOR-like) summarization over streams")
	sp.add_argument("streams_json", help="Input streams JSON path")
	sp.add_argument("out_json", help="Output recursive summary JSON path")
	sp.add_argument("--model")
	sp.add_argument("--fanout", type=int, default=6)
	sp.add_argument("--depth", type=int, default=2)
	sp.add_argument("--max-streams", type=int)
	sp.add_argument("--max-ids", type=int, default=5)
	sp.set_defaults(func=lambda a: print(json.dumps(streammod.summarize_streams_recursive(a.streams_json, a.out_json, model=a.model, fanout=a.fanout, depth=a.depth, max_streams=a.max_streams, max_ids=a.max_ids), ensure_ascii=False, indent=2)))

	# Multi-scale viewing (RAPTOR-inspired recursive summarization)
	sp = sub.add_parser("multiscale", parents=[parent], help="Multi-scale viewing: level 0=message, 1=conversation, 2=corpus, 3+=recursive (RAPTOR-like)")
	sp.add_argument("--composer-id", help="Single conversation ID (required for level 0-1)")
	sp.add_argument("--index-jsonl", help="Path to corpus index JSONL (required for level 2+)")
	sp.add_argument("--level", type=int, default=1, help="Scale level: 0=message, 1=conversation, 2=corpus, 3+=recursive")
	sp.add_argument("--model", help="LLM model for summarization (defaults to OPENAI_SMALL_MODEL or gpt-4o-mini)")
	sp.add_argument("--fanout", type=int, default=6, help="Fanout for recursive grouping (level 3+)")
	sp.add_argument("--depth", type=int, default=3, help="Recursive depth (level 3+)")
	sp.add_argument("--save-tree", help="Save RAPTOR tree to JSON file (for level 3+)")
	def _cmd_multiscale(a: argparse.Namespace) -> int:
		try:
			result = multiscalemod.view_scale(
				composer_id=a.composer_id,
				index_jsonl=a.index_jsonl,
				level=a.level,
				model=a.model,
				db_path=a.db,
				fanout=a.fanout,
				depth=a.depth,
				save_tree=getattr(a, "save_tree", None),
			)
			print(json.dumps(result, ensure_ascii=False, indent=2))
			return 0
		except ValueError as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale)

	# Unified stats command (combines eval + analytics in simple format)
	sp = sub.add_parser("multiscale-stats", parents=[parent], help="Get key statistics: quality, structure, performance, analytics")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	sp.add_argument("--original-items", help="Path to original items JSONL (for evaluation)")
	sp.add_argument("--model", help="Model for cost estimation (default: gpt-4o-mini)")
	def _cmd_multiscale_stats(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import (
				comprehensive_check, comprehensive_analytics,
				RaptorTree, SummaryLevel
			)

			# Load tree
			with open(expand_abs(a.tree_json), "r", encoding="utf-8") as f:
				tree_data = json.load(f)

		# Reconstruct tree
		levels = [
			SummaryLevel(level=level_data["level"], items=level_data["items"])
			for level_data in tree_data.get("levels", [])
		]
			tree = RaptorTree(levels=levels, meta=tree_data.get("meta", {}))

			# Load original items if provided
			original_items = None
			if a.original_items:
				original_items = []
				with open(expand_abs(a.original_items), "r", encoding="utf-8") as f:
					for line in f:
						if line.strip():
							original_items.append(json.loads(line))

			# Get comprehensive stats
			result = comprehensive_check(tree, original_items=original_items, include_eval=True)

			# Add analytics
			analytics = comprehensive_analytics(tree)
			result["analytics"] = analytics

			print(json.dumps(result, ensure_ascii=False, indent=2))
			return 0
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_stats)

	# Simple health check (default - easy to use)
	sp = sub.add_parser("multiscale-check", parents=[parent], help="Quick health check with simple pass/fail results")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	sp.add_argument("--original-items", help="Path to original items JSONL (for comparison)")
	sp.add_argument("--full", action="store_true", help="Include full validation and evaluation")
	def _cmd_multiscale_check(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import quick_check, comprehensive_check, load_tree

			# Load tree
			tree = load_tree(expand_abs(a.tree_json))

			# Load original items if provided
			original_items = None
			if a.original_items:
				original_items = []
				with open(expand_abs(a.original_items), "r", encoding="utf-8") as f:
					for line in f:
						if line.strip():
							original_items.append(json.loads(line))

			# Run check
			if a.full:
				result = comprehensive_check(tree, original_items=original_items, include_eval=True)
			else:
				health = quick_check(tree, original_items=original_items)
				result = {"health": health.to_dict()}

			print(json.dumps(result, ensure_ascii=False, indent=2))
			# Return non-zero if unhealthy
			if "health" in result:
				return 0 if result["health"].get("healthy", False) else 1
			return 0
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_check)

	# Comprehensive validation (advanced - detailed issues)
	sp = sub.add_parser("multiscale-validate", parents=[parent], help="[Advanced] Detailed validation with all issues")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	sp.add_argument("--original-items", help="Path to original items JSONL (for comparison)")
	sp.add_argument("--strict", action="store_true", help="Treat warnings as errors")
	def _cmd_multiscale_validate(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import validate, RaptorTree, SummaryLevel

			# Load tree
			with open(expand_abs(a.tree_json), "r", encoding="utf-8") as f:
				tree_data = json.load(f)

		# Reconstruct tree
		levels = [
			SummaryLevel(level=level_data["level"], items=level_data["items"])
			for level_data in tree_data.get("levels", [])
		]
			tree = RaptorTree(levels=levels, meta=tree_data.get("meta", {}))

			# Load original items if provided
			original_items = None
			if a.original_items:
				original_items = []
				with open(expand_abs(a.original_items), "r", encoding="utf-8") as f:
					for line in f:
						if line.strip():
							original_items.append(json.loads(line))

			# Validate
			report = validate(tree, original_items=original_items, strict=a.strict)

			print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
			return 0 if report.valid else 1
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_validate)

	# Analytics command
	sp = sub.add_parser("multiscale-analytics", parents=[parent], help="Advanced analytics: distributions, correlations, clustering")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	def _cmd_multiscale_analytics(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import comprehensive_analytics, load_tree

			tree = load_tree(expand_abs(a.tree_json))
			analytics = comprehensive_analytics(tree)

			print(json.dumps(analytics, ensure_ascii=False, indent=2))
			return 0
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_analytics)

	# Evaluation command
	sp = sub.add_parser("multiscale-eval", parents=[parent], help="Detailed evaluation metrics: quality, structure, performance")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	sp.add_argument("--original-items", help="Path to original items JSONL (for evaluation)")
	sp.add_argument("--model", help="Model for cost estimation (default: gpt-4o-mini)")
	def _cmd_multiscale_eval(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import evaluate, load_tree

			# Load tree
			tree = load_tree(expand_abs(a.tree_json))

			# Load original items if provided
			original_items = None
			if a.original_items:
				original_items = []
				with open(expand_abs(a.original_items), "r", encoding="utf-8") as f:
					for line in f:
						if line.strip():
							original_items.append(json.loads(line))

			model = a.model or "gpt-4o-mini"
			report = evaluate(original_items, tree, model=model)

			print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
			return 0
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_eval)

	# Tree utilities
	sp = sub.add_parser("multiscale-tree", parents=[parent], help="Tree utilities: stats, search, format, root summary")
	sp.add_argument("tree_json", help="Path to RAPTOR tree JSON file")
	sp.add_argument("--stats", action="store_true", help="Show tree statistics")
	sp.add_argument("--root", action="store_true", help="Show root-level summary")
	sp.add_argument("--level", type=int, help="Show summary at specific level")
	sp.add_argument("--search", help="Search for text in tree")
	sp.add_argument("--format", action="store_true", help="Format tree as readable text")
	def _cmd_multiscale_tree(a: argparse.Namespace) -> int:
		try:
			import json
			from multiscale import (
				load_tree, get_tree_stats, get_root_summary,
				get_summary_at_level, search_tree, format_tree_summary
			)

			# Load tree
			tree = load_tree(expand_abs(a.tree_json))

			result = {}

			if a.stats:
				result["stats"] = get_tree_stats(tree)

			if a.root:
				summary = get_root_summary(tree)
				result["root_summary"] = summary

			if a.level is not None:
				summary = get_summary_at_level(tree, a.level)
				result[f"level_{a.level}_summary"] = summary

			if a.search:
				matches = search_tree(tree, a.search)
				result["search_results"] = {
					"query": a.search,
					"count": len(matches),
					"matches": matches[:10],  # Limit to 10
				}

			if a.format:
				result["formatted"] = format_tree_summary(tree)

			# If no specific action, show stats
			if not any([a.stats, a.root, a.level is not None, a.search, a.format]):
				result["stats"] = get_tree_stats(tree)

			print(json.dumps(result, ensure_ascii=False, indent=2))
			return 0
		except FileNotFoundError as e:
			print(json.dumps({"error": f"File not found: {e}"}, ensure_ascii=False))
			return 2
		except json.JSONDecodeError as e:
			print(json.dumps({"error": f"Invalid JSON: {e}"}, ensure_ascii=False))
			return 2
		except Exception as e:
			print(json.dumps({"error": str(e)}, ensure_ascii=False))
			return 1
	sp.set_defaults(func=_cmd_multiscale_tree)

	# High-level query commands
	sp = sub.add_parser("find-solution", parents=[parent], help="Find past solutions to a problem (high-level wrapper, cached)")
	sp.add_argument("query", help="What problem are you trying to solve?")
	sp.add_argument("--index-jsonl", help="Path to index JSONL (defaults to CURSOR_INDEX_JSONL or ./cursor_index.jsonl)")
	sp.add_argument("--vec-db", help="Path to vector DB (defaults to CURSOR_VEC_DB or ./cursor_vec.db)")
	sp.add_argument("--k", type=int, default=10, help="Number of results to return (default: 10)")
	sp.add_argument("--no-auto-index", action="store_true", help="Don't auto-create indexes if missing")
	sp.add_argument("--no-cache", action="store_true", help="Don't use cache (force fresh search)")
	sp.set_defaults(func=lambda a: print(json.dumps(memmod.find_solution(
		a.query,
		index_jsonl=a.index_jsonl,
		vec_db=a.vec_db,
		db_path=a.db,
		k=a.k,
		auto_index=not a.no_auto_index,
		use_cache=not a.no_cache,
	), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("remember", parents=[parent], help="Help recall forgotten things from chat history (cached)")
	sp.add_argument("query", help="What are you trying to remember?")
	sp.add_argument("--index-jsonl", help="Path to index JSONL (defaults to CURSOR_INDEX_JSONL or ./cursor_index.jsonl)")
	sp.add_argument("--vec-db", help="Path to vector DB (defaults to CURSOR_VEC_DB or ./cursor_vec.db)")
	sp.add_argument("--k", type=int, default=5, help="Number of results to return (default: 5)")
	sp.add_argument("--no-auto-index", action="store_true", help="Don't auto-create indexes if missing")
	sp.add_argument("--no-llm", action="store_true", help="Don't use LLM for memory summary (faster, no summarization)")
	sp.add_argument("--model", help="LLM model for summarization (default: from env or gpt-4o-mini)")
	sp.set_defaults(func=lambda a: print(json.dumps(memmod.remember(
		a.query,
		index_jsonl=a.index_jsonl,
		vec_db=a.vec_db,
		db_path=a.db,
		k=a.k,
		auto_index=not a.no_auto_index,
		use_llm=not a.no_llm,
		model=a.model,
	), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("design-coherence", parents=[parent], help="Find and organize scattered design plans/wants (cached)")
	sp.add_argument("--index-jsonl", help="Path to index JSONL (defaults to CURSOR_INDEX_JSONL or ./cursor_index.jsonl)")
	sp.add_argument("--vec-db", help="Path to vector DB (defaults to CURSOR_VEC_DB or ./cursor_vec.db)")
	sp.add_argument("--topics", action="append", help="Specific topics to search for (repeatable, e.g., --topics auth --topics api)")
	sp.add_argument("--no-auto-index", action="store_true", help="Don't auto-create indexes if missing")
	sp.add_argument("--no-llm", action="store_true", help="Don't use LLM for coherence summary (faster, no summarization)")
	sp.add_argument("--model", help="LLM model for summarization (default: from env or gpt-4o-mini)")
	sp.set_defaults(func=lambda a: print(json.dumps(memmod.find_design_plans(
		index_jsonl=a.index_jsonl,
		vec_db=a.vec_db,
		db_path=a.db,
		topics=a.topics,
		auto_index=not a.no_auto_index,
		use_llm=not a.no_llm,
		model=a.model,
	), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("ensure-indexed", parents=[parent], help="Ensure indexes exist, creating them if needed (idempotent)")
	sp.add_argument("--index-jsonl", help="Path to index JSONL (defaults to CURSOR_INDEX_JSONL or ./cursor_index.jsonl)")
	sp.add_argument("--vec-db", help="Path to vector DB (defaults to CURSOR_VEC_DB or ./cursor_vec.db)")
	sp.add_argument("--force", action="store_true", help="Force re-indexing even if indexes exist")
	sp.set_defaults(func=lambda a: print(json.dumps(memmod.ensure_indexed(
		index_jsonl=a.index_jsonl,
		vec_db=a.vec_db,
		db_path=a.db,
		force=a.force,
	), ensure_ascii=False, indent=2)))

	sp = sub.add_parser("cache-stats", parents=[parent], help="Show cache statistics")
	sp.set_defaults(func=lambda a: print(json.dumps({
		"cache_count": llm_cache.count(),
		"cache_path": os.getenv("LLM_CACHE_PATH", "llm_cache.sqlite"),
	}, ensure_ascii=False, indent=2)))

	sp = sub.add_parser("cache-clear", parents=[parent], help="Clear LLM cache")
	sp.set_defaults(func=lambda a: (llm_cache.clear(), print(json.dumps({"cleared": True}, ensure_ascii=False))))

	return p


def main(argv: Optional[list[str]] = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	# Apply trace metadata if present
	meta = {}
	for kv in (getattr(args, "trace_meta", None) or []):
		if "=" in kv:
			k, v = kv.split("=", 1)
			meta[k] = v
	if meta:
		tracemod.set_context(meta)
	code = args.func(args)
	# Always print a brief usage summary to stderr
	summary = tracemod.get_run_summary()
	try:
		print(json.dumps({"usage_summary": summary}), file=sys.stderr)
	except Exception:
		pass
	return code


if __name__ == "__main__":
	sys.exit(main())
