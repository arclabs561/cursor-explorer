"""Multi-scale viewing and recursive summarization for conversations.

Provides unified access to conversation data at different levels of abstraction:
- Level 0: Individual messages/turns
- Level 1: Single conversation summaries
- Level 2: Corpus-level summaries
- Level 3+: Recursive summaries of summaries (RAPTOR-like)

Uses the standalone multiscale package for core RAPTOR functionality.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Any

try:
	from multiscale import recursive_summarize, view_scale as multiscale_view_scale
	_HAS_MULTISCALE = True
except ImportError:
	_HAS_MULTISCALE = False

from . import db as dbmod
from . import parser as parsermod
from . import annotate as annotatemod
from .paths import expand_abs, default_db_path
import llm_utils as llmmod


def view_scale(
	composer_id: Optional[str] = None,
	index_jsonl: Optional[str] = None,
	level: int = 1,
	model: Optional[str] = None,
	db_path: Optional[str] = None,
	fanout: int = 6,
	depth: Optional[int] = None,
	save_tree: Optional[str] = None,
) -> Dict[str, Any]:
	"""Unified multi-scale viewing of conversations.
	
	Args:
		composer_id: Single conversation ID (for level 0-1)
		index_jsonl: Path to corpus index (for level 2+)
		level: Scale level (0=message, 1=conversation, 2=corpus, 3+=recursive)
		model: LLM model for summarization
		db_path: Path to agent state database
		
	Returns:
		Dict with scale-appropriate data structure
	"""
	if level == 0:
		# Level 0: Individual messages/turns
		if not composer_id:
			raise ValueError("composer_id required for level 0")
		return _view_level_0(composer_id, db_path)
	elif level == 1:
		# Level 1: Single conversation summary
		if not composer_id:
			raise ValueError("composer_id required for level 1")
		return _view_level_1(composer_id, model, db_path)
	elif level == 2:
		# Level 2: Corpus-level summary
		if not index_jsonl:
			raise ValueError("index_jsonl required for level 2")
		return _view_level_2(index_jsonl, model)
	else:
		# Level 3+: Recursive summaries
		if not index_jsonl:
			raise ValueError("index_jsonl required for recursive levels")
		# Use level as depth, with minimum depth of 1
		recursive_depth = depth if depth is not None else max(1, level - 2)  # level 3 -> depth 1, level 4 -> depth 2, etc.
		result = _view_level_recursive(index_jsonl, recursive_depth, model, fanout)

		# Save tree if requested
		if save_tree:
			try:
				from multiscale import RaptorTree, SummaryLevel, save_tree as save_tree_func
				levels = [
					SummaryLevel(level=l["level"], items=l["items"])
					for l in result.get("levels", [])
				]
				tree = RaptorTree(levels=levels, meta=result.get("meta", {}))
				save_path = expand_abs(save_tree)
				save_tree_func(tree, save_path)
				result["saved_tree"] = save_path
			except Exception as e:
				result["save_error"] = str(e)

		return result


def _view_level_0(composer_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
	"""Level 0: Individual messages/turns from a conversation."""
	conn = dbmod.connect_readonly(expand_abs(db_path or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, composer_id)
	pairs = parsermod.build_qa_pairs(messages)

	return {
		"level": 0,
		"composer_id": composer_id,
		"turns": [
			{
				"turn_index": p.get("turn_index"),
				"user": p.get("user", ""),
				"assistant": p.get("assistant", ""),
			}
			for p in pairs
		],
		"count": len(pairs),
	}


def _view_level_1(composer_id: str, model: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
	"""Level 1: Single conversation summary (micro/meso/macro)."""
	conn = dbmod.connect_readonly(expand_abs(db_path or default_db_path()))
	messages = parsermod.reconstruct_conversation(conn, composer_id)
	pairs = parsermod.build_qa_pairs(messages)

	# Heuristic scales
	heuristic = annotatemod.annotate_conversation_scales(pairs)

	result: Dict[str, Any] = {
		"level": 1,
		"composer_id": composer_id,
		"heuristic": heuristic,
		"turn_count": len(pairs),
	}

	# LLM-based summary if model provided
	if model:
		try:
			client = llmmod.require_client()
			llm_summary = llmmod.summarize_conversation_llm(client, pairs, model)
			result["llm"] = llm_summary
		except Exception as e:
			result["llm_error"] = str(e)

	return result


def _view_level_2(index_jsonl: str, model: Optional[str] = None) -> Dict[str, Any]:
	"""Level 2: Corpus-level summary across all conversations."""
	index_path = expand_abs(index_jsonl)
	conversations: Dict[str, List[Dict]] = {}

	# Group by composer_id
	with open(index_path, "r", encoding="utf-8") as f:
		for line in f:
			try:
				item = json.loads(line)
				cid = item.get("composer_id")
				if cid:
					conversations.setdefault(cid, []).append(item)
			except Exception:
				continue

	# Build corpus-level summary
	corpus_data = {
		"level": 2,
		"conversation_count": len(conversations),
		"total_turns": sum(len(items) for items in conversations.values()),
		"conversations": {},
	}

	# Per-conversation summaries (heuristic)
	for cid, items in list(conversations.items())[:50]:  # Limit for performance
		pairs = []
		for item in sorted(items, key=lambda x: int(x.get("turn_index", 0))):
			pairs.append({
				"turn_index": item.get("turn_index"),
				"user": item.get("user", ""),
				"assistant": item.get("assistant", ""),
			})
		if pairs:
			heuristic = annotatemod.annotate_conversation_scales(pairs)
			corpus_data["conversations"][cid] = {
				"turn_count": len(pairs),
				"macro": heuristic.get("macro", ""),
			}

	# LLM-based corpus summary if model provided
	if model:
		try:
			client = llmmod.require_client()
			# Sample conversations for summary
			sample_convs = []
			for cid, items in list(conversations.items())[:20]:
				pairs = []
				for item in sorted(items, key=lambda x: int(x.get("turn_index", 0)))[:10]:
					pairs.append({
						"turn_index": item.get("turn_index"),
						"user": item.get("user", "")[:200],
						"assistant": item.get("assistant", "")[:400],
					})
				if pairs:
					heuristic = annotatemod.annotate_conversation_scales(pairs)
					sample_convs.append({
						"composer_id": cid,
						"macro": heuristic.get("macro", ""),
						"turn_count": len(pairs),
					})

			# Summarize corpus
			corpus_text = "\n\n".join([
				f"Conversation {c['composer_id']}: {c['macro']} ({c['turn_count']} turns)"
				for c in sample_convs
			])

			instructions = (
				"Summarize this corpus of conversations into STRICT JSON with keys: "
				"theme (overall theme across conversations), "
				"patterns (array of 5-10 common patterns), "
				"topics (array of 5-10 main topics)."
			)

			resp = client.chat.completions.create(
				model=model,
				messages=[
					{"role": "system", "content": instructions},
					{"role": "user", "content": corpus_text[:8000]},  # Limit length
				],
			)
			text = resp.choices[0].message.content or "{}"
			try:
				corpus_data["llm"] = json.loads(text)
			except Exception:
				corpus_data["llm_raw"] = text
		except Exception as e:
			corpus_data["llm_error"] = str(e)

	return corpus_data


def _view_level_recursive(
	index_jsonl: str,
	depth: int,
	model: Optional[str] = None,
	fanout: int = 6,
) -> Dict[str, Any]:
	"""Level 3+: Recursive summaries (RAPTOR-like hierarchical structure).
	
	Builds a tree where:
	- Level 0: Individual conversations
	- Level 1+: Recursive summaries of groups
	
	Uses the multiscale package if available, otherwise falls back to local implementation.
	"""
	index_path = expand_abs(index_jsonl)
	conversations: Dict[str, List[Dict]] = {}

	# Load conversations
	with open(index_path, "r", encoding="utf-8") as f:
		for line in f:
			try:
				item = json.loads(line)
				cid = item.get("composer_id")
				if cid:
					conversations.setdefault(cid, []).append(item)
			except Exception:
				continue

	# Prepare items for multiscale package
	items: List[Dict[str, Any]] = []
	for cid, items_list in list(conversations.items())[:100]:  # Limit for performance
		pairs = []
		for item in sorted(items_list, key=lambda x: int(x.get("turn_index", 0)))[:20]:
			pairs.append({
				"turn_index": item.get("turn_index"),
				"user": item.get("user", "")[:200],
				"assistant": item.get("assistant", "")[:400],
			})
		if pairs:
			# Build conversation text
			conv_text = "\n".join([
				f"Turn {p['turn_index']}: {p['user']}\n{p['assistant']}"
				for p in pairs
			])
			items.append({
				"id": cid,
				"text": conv_text,
				"composer_id": cid,
				"turn_count": len(pairs),
			})

	if not model:
		model = os.getenv("OPENAI_SMALL_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

	# Use multiscale package if available
	if _HAS_MULTISCALE:
		try:
			client = llmmod.require_client()
			tree = recursive_summarize(
				items=items,
				depth=depth,
				fanout=fanout,
				model=model,
				llm_client=client,
				text_extractor=lambda x: x.get("text", "") if isinstance(x, dict) else str(x),
			)
			return {
				"levels": [
					{"level": l.level, "items": l.items}
					for l in tree.levels
				],
				"meta": {
					**tree.meta,
					"conversation_count": len(conversations),
				},
			}
		except Exception:
			# Fall back to local implementation on error
			pass

	# Fallback: local implementation
	client = llmmod.require_client()

	# Level 0: Per-conversation summaries
	level_0: List[Dict] = []
	for item in items:
		cid = item.get("composer_id", item.get("id", ""))
		text = item.get("text", "")
		turn_count = item.get("turn_count", 0)

		heuristic = annotatemod.annotate_conversation_scales([
			{"turn_index": i, "user": "", "assistant": ""}
			for i in range(turn_count)
		])
		macro = heuristic.get("macro", "")

		# LLM summary if available
		summary_text = macro
		if text:
			try:
				conv_text = text[:500]
				system = "Return STRICT JSON: {theme: string, key_points: [string]} in <= 60 words."
				user = f"Conversation summary:\n{conv_text}"
				resp = client.chat.completions.create(
					model=model,
					messages=[
						{"role": "system", "content": system},
						{"role": "user", "content": user},
					],
				)
				text_resp = resp.choices[0].message.content or "{}"
				try:
					summary_obj = json.loads(text_resp)
					summary_text = summary_obj.get("theme", macro)
				except Exception:
					pass
			except Exception:
				pass

		level_0.append({
			"composer_id": cid,
			"turn_count": turn_count,
			"summary": summary_text,
		})

	levels: List[Dict] = [{"level": 0, "items": level_0}]

	# Recursive summarization
	current = level_0
	for d in range(max(0, depth - 3)):  # depth 3 = level 0, so subtract 3
		if len(current) <= 1:
			break

		# Group into fanout-sized chunks
		groups: List[List[Dict]] = []
		for i in range(0, len(current), fanout):
			groups.append(current[i:i+fanout])

		next_level: List[Dict] = []
		for grp in groups:
			# Summarize group
			group_text = "\n".join([
				f"[{i}] {item.get('summary', '')[:100]}"
				for i, item in enumerate(grp)
			])

			system = (
				"Merge these conversation summaries into STRICT JSON: "
				"{theme: string, patterns: [string], key_points: [string]}. "
				"Be concise, aggregate not repeat."
			)
			user = group_text

			try:
				resp = client.chat.completions.create(
					model=model,
					messages=[
						{"role": "system", "content": system},
						{"role": "user", "content": user},
					],
				)
				text = resp.choices[0].message.content or "{}"
				try:
					summary = json.loads(text)
				except Exception:
					summary = {"raw": text}
			except Exception as e:
				summary = {"error": str(e)}

			next_level.append({
				"children": grp,
				"summary": summary,
			})

		levels.append({"level": len(levels), "items": next_level})
		current = next_level

	return {
		"levels": levels,
		"meta": {
			"conversation_count": len(conversations),
			"depth": len(levels),
			"fanout": fanout,
		},
	}

