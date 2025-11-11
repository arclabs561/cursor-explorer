from __future__ import annotations

import json
from typing import Dict, List, Optional
import os
import re
from . import db as dbmod
from . import parser as parsermod
from .paths import default_db_path
import llm_helpers as llmmod
from . import index as indexmod
from .paths import expand_abs


def _safe_bool(x) -> bool:
	return bool(x) is True


def analyze_index(index_path: str, limit: int | None = None) -> Dict:
	"""Compute simple data-quality metrics over a JSONL index of per-turn items.

	Returns counts for tags and booleans, missing annotation keys, and head lengths.
	"""
	index_path = expand_abs(index_path)
	keys_bool = [
		"contains_design",
		"contains_preference",
		"contains_learning",
		"unfinished_thread",
		"has_useful_output",
	]
	metrics: Dict[str, int] = {
		"turns": 0,
		"user_head_empty": 0,
		"assistant_head_empty": 0,
	}
	for k in keys_bool:
		metrics[f"ann_{k}"] = 0
	missing_keys: Dict[str, int] = {}
	tag_counts: Dict[str, int] = {}
	user_head_total = 0
	assistant_head_total = 0

	with open(index_path, "r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if limit is not None and i >= limit:
				break
			try:
				obj = json.loads(line)
			except Exception:
				continue
			metrics["turns"] += 1
			uh = (obj.get("user_head") or "").strip()
			ah = (obj.get("assistant_head") or "").strip()
			user_head_total += len(uh)
			assistant_head_total += len(ah)
			if not uh:
				metrics["user_head_empty"] += 1
			if not ah:
				metrics["assistant_head_empty"] += 1
			ann = obj.get("annotations") or {}
			for k in keys_bool:
				if _safe_bool(ann.get(k)):
					metrics[f"ann_{k}"] += 1
			# missing keys
			for k in keys_bool:
				if k not in ann:
					missing_keys[k] = missing_keys.get(k, 0) + 1
			# tags
			for t in (ann.get("tags") or []):
				if isinstance(t, str) and t:
					tag_counts[t] = tag_counts.get(t, 0) + 1

	avg_user_head = (user_head_total / metrics["turns"]) if metrics["turns"] else 0.0
	avg_assistant_head = (assistant_head_total / metrics["turns"]) if metrics["turns"] else 0.0

	return {
		"counts": metrics,
		"avg_head_len": {"user": round(avg_user_head, 2), "assistant": round(avg_assistant_head, 2)},
		"missing_keys": missing_keys,
		"tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)),
	}



def _detect_patterns(text: str) -> Dict[str, bool]:
	code = bool(re.search(r"```[\s\S]*?```", text))
	url = bool(re.search(r"https?://", text))
	json_like = bool(re.search(r"\{\s*\"[A-Za-z0-9_]+\"\s*:\s*", text))
	zwc = "\u200b" in text or "\u200c" in text or "\u200d" in text
	rtl = "\u202e" in text
	return {"has_code": code, "has_urls": url, "has_json_like": json_like, "has_zero_width": zwc, "has_rtl": rtl}


def analyze_db(db_path: Optional[str] = None, limit_composers: Optional[int] = None) -> Dict:
	"""Inspect raw DB-level parsing health: bubbles/headers, roles, empties, coalescing, pairs completeness.

	Returns aggregate metrics and a small list of anomalous composer_ids.
	"""
	conn = dbmod.connect_readonly(expand_abs(db_path or default_db_path()))
	composer_ids = parsermod.list_composer_ids(conn)
	if limit_composers is not None:
		composer_ids = composer_ids[: max(0, int(limit_composers))]

	metrics: Dict[str, float] = {
		"chats": 0,
		"headers_total": 0,
		"bubbles_loaded": 0,
		"bubbles_missing": 0,
		"messages_total": 0,
		"messages_empty_text": 0,
		"user_msgs": 0,
		"assistant_msgs": 0,
		"assistant_msgs_after_coalesce": 0,
		"pairs_total": 0,
		"pairs_user_empty": 0,
		"pairs_assistant_empty": 0,
	}
	pattern_counts = {"has_code": 0, "has_urls": 0, "has_json_like": 0, "has_zero_width": 0, "has_rtl": 0}
	anomalies: List[Dict] = []

	for cid in composer_ids:
		composer = parsermod.load_composer(conn, cid)
		if not composer:
			continue
		headers = list(parsermod.iter_bubble_headers(composer))
		metrics["chats"] += 1
		metrics["headers_total"] += len(headers)
		loaded_count = 0
		messages: List[dict] = []
		for bubble_id, bubble_type, server_bubble_id in headers:
			bubble = parsermod.load_bubble(conn, cid, bubble_id)
			if bubble:
				loaded_count += 1
				text = (bubble.get("text") or bubble.get("content") or "") if isinstance(bubble, dict) else ""
				role = parsermod.bubble_role(bubble_type)
				messages.append({"role": role, "text": text})
		metrics["bubbles_loaded"] += loaded_count
		metrics["bubbles_missing"] += max(0, len(headers) - loaded_count)
		metrics["messages_total"] += len(messages)
		for m in messages:
			if not (m.get("text") or "").strip():
				metrics["messages_empty_text"] += 1
			if m.get("role") == "user":
				metrics["user_msgs"] += 1
			else:
				metrics["assistant_msgs"] += 1
			p = _detect_patterns(m.get("text") or "")
			for k, v in p.items():
				if v:
					pattern_counts[k] += 1
		# Coalesce and pairs
		coalesced = parsermod.coalesce_assistant_runs([
			{"role": m.get("role"), "text": m.get("text") or ""} for m in messages
		])
		metrics["assistant_msgs_after_coalesce"] += sum(1 for m in coalesced if m.get("role") == "assistant")
		pairs = parsermod.build_qa_pairs([
			{"role": m.get("role"), "text": m.get("text") or "", "composer_id": cid} for m in messages
		])
		metrics["pairs_total"] += len(pairs)
		pairs_user_empty = sum(1 for p in pairs if not (p.get("user") or "").strip())
		pairs_assistant_empty = sum(1 for p in pairs if not (p.get("assistant") or "").strip())
		metrics["pairs_user_empty"] += pairs_user_empty
		metrics["pairs_assistant_empty"] += pairs_assistant_empty
		# Anomaly heuristics per chat
		miss_rate = (len(headers) - loaded_count) / len(headers) if headers else 0.0
		empty_msg_rate = (metrics["messages_empty_text"]) / metrics["messages_total"] if metrics["messages_total"] else 0.0
		if miss_rate > 0.1 or pairs_user_empty or pairs_assistant_empty:
			anomalies.append({"composer_id": cid, "missing_bubbles_rate": round(miss_rate, 3), "pairs_user_empty": int(pairs_user_empty), "pairs_assistant_empty": int(pairs_assistant_empty)})

	# Ratios
	out = {
		"counts": {k: int(v) for k, v in metrics.items()},
		"ratios": {
			"missing_bubbles": round((metrics["bubbles_missing"] / metrics["headers_total"]) if metrics["headers_total"] else 0.0, 4),
			"assistant_coalesce_factor": round(((metrics["assistant_msgs"] or 1) / (metrics["assistant_msgs_after_coalesce"] or 1)), 3),
			"pairs_user_empty": round((metrics["pairs_user_empty"] / metrics["pairs_total"]) if metrics["pairs_total"] else 0.0, 4),
			"pairs_assistant_empty": round((metrics["pairs_assistant_empty"] / metrics["pairs_total"]) if metrics["pairs_total"] else 0.0, 4),
		},
		"patterns": pattern_counts,
		"anomalies": anomalies[:20],
	}
	return out


def _build_item_snippet(obj: Dict) -> str:
	idv = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
	uh = (obj.get("user_head") or "").strip()
	ah = (obj.get("assistant_head") or "").strip()
	ann = obj.get("annotations") or {}
	flags = _detect_patterns("\n".join([uh, ah]))
	return (
		f"ID: {idv}\n"
		f"User: {uh[:300]}\nAssistant: {ah[:400]}\n"
		f"Annotations: {json.dumps(ann, ensure_ascii=False)}\n"
		f"Heuristics: {json.dumps(flags)}\n"
	)


def llm_find_issues(index_jsonl: str, n: int = 40, model: Optional[str] = None, seed: Optional[int] = None) -> Dict:
	"""Randomly sample items and ask an LLM to find problems and fixes per item.

	Returns: { items: [{id, issues:[..], severity, suggestions:[..]}], prompt_tokens, completion_tokens }
	"""
	index_jsonl = expand_abs(index_jsonl)
	items = indexmod.sample_index(index_jsonl, max(1, int(n)))
	if not items:
		return {"items": [], "sample_count": 0}
	client = llmmod.require_client()
	mdl = model or os.getenv("OPENAI_MODEL", "gpt-5")
	# Build compact prompt
	snippets = [_build_item_snippet(it) for it in items]
	body = ("\n\n".join(snippets))[:12000]
	instructions = (
		"You are a data-quality auditor. For each item below, find concrete problems and fixes. "
		"Return STRICT JSON array of objects: {id: string, issues: [short strings], severity: 'low'|'medium'|'high', suggestions: [short strings]}. "
		"Only include fields specified."
	)
	resp = client.chat.completions.create(
		model=mdl,
		messages=[{"role": "system", "content": instructions}, {"role": "user", "content": body}],
	)
	text = resp.choices[0].message.content or "[]"
	try:
		parsed = json.loads(text)
	except Exception:
		parsed = []
	usage = getattr(resp, "usage", None)
	return {
		"items": parsed if isinstance(parsed, list) else [],
		"sample_count": len(items),
		"usage": {
			"prompt": getattr(usage, "prompt_tokens", None) if usage else None,
			"completion": getattr(usage, "completion_tokens", None) if usage else None,
		},
	}


def llm_aggregate_findings(findings: Dict, stats_index: Optional[Dict] = None, stats_db: Optional[Dict] = None, model: Optional[str] = None) -> Dict:
	"""Aggregate item-level findings into prioritized issues and actions via an LLM."""
	client = llmmod.require_client()
	mdl = model or os.getenv("OPENAI_MODEL", "gpt-5")
	# Compose a compact context with top-line stats
	parts = []
	if stats_index:
		parts.append("Index stats:" + json.dumps(stats_index.get("counts", {})))
		parts.append("Head lens:" + json.dumps(stats_index.get("avg_head_len", {})))
		if stats_index.get("tag_counts"):
			# include top 10 tags
			items = list(stats_index.get("tag_counts", {}).items())[:10]
			parts.append("Top tags:" + json.dumps(dict(items)))
	if stats_db:
		parts.append("DB counts:" + json.dumps(stats_db.get("counts", {})))
		parts.append("DB ratios:" + json.dumps(stats_db.get("ratios", {})))
		parts.append("Patterns:" + json.dumps(stats_db.get("patterns", {})))
	# Findings compacted (cap to last 50)
	items = findings.get("items", [])[-50:]
	context = ("\n".join(parts) + "\nFindings:" + json.dumps(items, ensure_ascii=False))[:12000]
	instr = (
		"Aggregate the findings into STRICT JSON: "
		"{themes: [string], top_issues: [string], root_causes: [string], recommended_actions: [string], questions_for_engineers: [string]}. "
		"Prioritize specificity and actionable items."
	)
	resp = client.chat.completions.create(model=mdl, messages=[{"role": "system", "content": instr}, {"role": "user", "content": context}])
	text = resp.choices[0].message.content or "{}"
	try:
		agg = json.loads(text)
	except Exception:
		agg = {"raw": text}
	return {"summary": agg, "usage": getattr(resp, "usage", None)}

