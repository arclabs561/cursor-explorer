from __future__ import annotations

import json
import os
import hashlib
from typing import Dict, List, Optional, Any
from cursor_explorer import trace as tracemod

try:
	from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore

import llm_cache


class LLMNotAvailable(RuntimeError):
	pass


def require_client() -> Any:
	"""Get LLM client - delegates to llm-helpers package."""
	# Import from standalone llm-helpers package (no name conflict now)
	from llm_helpers import require_client as _require_client
	return _require_client()


def _ensure_json_object(text: str) -> Dict:
	try:
		return json.loads(text)
	except Exception:
		# attempt to extract first {...}
		start = text.find("{")
		end = text.rfind("}")
		if start != -1 and end != -1 and end > start:
			try:
				return json.loads(text[start : end + 1])
			except Exception:
				pass
	return {"raw": text}


# ------------------- cache helpers -------------------

def _hash_key(parts: list[str]) -> str:
	h = hashlib.sha256()
	for p in parts:
		h.update(p.encode("utf-8"))
	return h.hexdigest()


# ------------------- core calls -------------------

def annotate_pair_llm(
	client: Any,
	pair: Dict,
	model: str,
	reasoning_effort: Optional[str] = None,
	verbosity: Optional[str] = None,
) -> Dict:
	user = pair.get("user", "") or ""
	assistant = pair.get("assistant", "") or ""
	instructions = (
		"You annotate a user-assistant exchange. Return STRICT JSON with keys: "
		"user_summary, assistant_summary (short strings); user_polarity, assistant_polarity "
		"('positive'|'neutral'|'negative'); unfinished_thread (bool); has_useful_output (bool); "
		"contains_preference (bool); contains_design (bool); contains_learning (bool); tags (array of short strings)."
	)
	prompt = f"User:\n{user}\n\nAssistant:\n{assistant}"
	cache_key = _hash_key(["annotate_pair_llm", model, instructions, user, assistant])
	cached = llm_cache.get(cache_key)
	if cached is not None:
		meta = llm_cache.get_meta(cache_key) or {}
		if meta:
			tracemod.log_event("cache_hit_meta", {"key": cache_key, **meta})
		tracemod.note_cache_hit()
		return _ensure_json_object(cached)
	extra: Dict[str, Any] = {}
	if reasoning_effort in {"minimal", "medium", "high"}:
		extra["reasoning"] = {"effort": reasoning_effort}
	if verbosity in {"low", "medium", "high"} and str(model).startswith("gpt-5"):
		extra["verbosity"] = verbosity
	# Some GPT-5 variants only support default temperature; omit explicit temperature for gpt-5*
	is_gpt5 = str(model).startswith("gpt-5")
	call_kwargs: Dict[str, Any] = {
		"model": model,
		"messages": [
			{"role": "system", "content": instructions},
			{"role": "user", "content": prompt},
		],
		**extra,
	}
	if not is_gpt5:
		call_kwargs["temperature"] = 0.2
	resp = client.chat.completions.create(**call_kwargs)
	text = resp.choices[0].message.content or "{}"
	usage = getattr(resp, "usage", None)
	llm_cache.set(
		cache_key,
		text,
		prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
		completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
		total_tokens=getattr(usage, "total_tokens", None) if usage else None,
	)
	# usage log
	response_meta = {
		"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
		"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
		"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
	}
	tracemod.log_llm_event(
		endpoint="chat.completions",
		model=model,
		request_meta={"temperature": 0.2, **({"reasoning_effort": reasoning_effort} if reasoning_effort else {})},
		response_meta=response_meta,
		pair=pair,
		input_text=prompt,
		output_text=text,
		extra_meta={"op": "annotate_pair_llm"},
	)
	return _ensure_json_object(text)


def summarize_conversation_llm(
	client: Any,
	pairs: List[Dict],
	model: str,
	reasoning_effort: Optional[str] = None,
	verbosity: Optional[str] = None,
) -> Dict:
	turns = []
	for p in pairs[:50]:  # cap
		idx = p.get("turn_index")
		u = (p.get("user") or "").strip()
		a = (p.get("assistant") or "").strip()
		turns.append(f"Turn {idx} - U: {u[:300]}\nA: {a[:600]}")
	body = "\n\n".join(turns)
	instructions = (
		"Summarize the conversation into STRICT JSON with keys: "
		"micro (array of at most 10 short bullet strings), "
		"meso (array of at most 10 short milestone strings), "
		"macro (one-sentence theme). Keep it concise."
	)
	cache_key = _hash_key(["summarize_conversation_llm", model, instructions, body])
	cached = llm_cache.get(cache_key)
	if cached is not None:
		meta = llm_cache.get_meta(cache_key) or {}
		if meta:
			tracemod.log_event("cache_hit_meta", {"key": cache_key, **meta})
		tracemod.note_cache_hit()
		return _ensure_json_object(cached)
	extra: Dict[str, Any] = {}
	if reasoning_effort in {"minimal", "medium", "high"}:
		extra["reasoning"] = {"effort": reasoning_effort}
	if verbosity in {"low", "medium", "high"} and str(model).startswith("gpt-5"):
		extra["verbosity"] = verbosity
	is_gpt5 = str(model).startswith("gpt-5")
	call_kwargs: Dict[str, Any] = {
		"model": model,
		"messages": [
			{"role": "system", "content": instructions},
			{"role": "user", "content": body},
		],
		**extra,
	}
	if not is_gpt5:
		call_kwargs["temperature"] = 0.2
	resp = client.chat.completions.create(**call_kwargs)
	text = resp.choices[0].message.content or "{}"
	usage = getattr(resp, "usage", None)
	llm_cache.set(
		cache_key,
		text,
		prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
		completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
		total_tokens=getattr(usage, "total_tokens", None) if usage else None,
	)
	usage = getattr(resp, "usage", None)
	response_meta = {
		"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
		"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
		"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
	}
	tracemod.log_llm_event(
		endpoint="chat.completions",
		model=model,
		request_meta={"temperature": 0.2, "turns": min(len(pairs), 50), **({"reasoning_effort": reasoning_effort} if reasoning_effort else {})},
		response_meta=response_meta,
		pair=None,
		input_text=body,
		output_text=text,
		extra_meta={"op": "summarize_conversation_llm"},
	)
	return _ensure_json_object(text)


# ------------------- judging helpers -------------------

def judge_annotations_llm(
	client: Any,
	items: List[Dict],
	model: str,
	reasoning_effort: Optional[str] = None,
	verbosity: Optional[str] = None,
) -> Dict:
	"""Judge quality of annotations for a small batch of items.

	Each item: {composer_id, turn_index, user_head, assistant_head, annotations}
	Returns STRICT JSON with keys: per_item (array of {id, scores, issues, suggestions}),
	common_issues (array of strings), suggested_queries (array of strings)
	"""
	# Build prompt
	lines = []
	for it in items[:20]:  # cap
		cid = it.get("composer_id")
		tidx = it.get("turn_index")
		uh = (it.get("user_head") or "")[:300]
		ah = (it.get("assistant_head") or "")[:400]
		ann = json.dumps(it.get("annotations") or {}, ensure_ascii=False)
		lines.append(f"ID {cid}:{tidx}\nUser: {uh}\nAssistant: {ah}\nAnnotations: {ann}")
	body = "\n\n".join(lines)

	instructions = (
		"You are a critical judge of annotation quality for chat QA pairs. "
		"For each item, score 0-1: accuracy, completeness, consistency; list concrete issues; suggest 1-2 fixes. "
		"Return STRICT JSON: {per_item: [{id, scores: {accuracy, completeness, consistency}, issues: [..], suggestions: [..]}], "
		"common_issues: [..], suggested_queries: [..]}"
	)

	# Cache key
	parts = ["judge_annotations_llm", model, instructions]
	for it in items[:20]:
		parts.append(str(it.get("composer_id")))
		parts.append(str(it.get("turn_index")))
		parts.append((it.get("user_head") or "")[:120])
		parts.append((it.get("assistant_head") or "")[:160])
	parts_key = _hash_key(parts)
	cached = llm_cache.get(parts_key)
	if cached is not None:
		tracemod.note_cache_hit()
		return _ensure_json_object(cached)

	extra: Dict[str, Any] = {}
	if reasoning_effort in {"minimal", "medium", "high"}:
		extra["reasoning"] = {"effort": reasoning_effort}
	if verbosity in {"low", "medium", "high"} and str(model).startswith("gpt-5"):
		extra["verbosity"] = verbosity
	is_gpt5 = str(model).startswith("gpt-5")
	call_kwargs: Dict[str, Any] = {
		"model": model,
		"messages": [
			{"role": "system", "content": instructions},
			{"role": "user", "content": body},
		],
		**extra,
	}
	if not is_gpt5:
		call_kwargs["temperature"] = 0.2
	resp = client.chat.completions.create(**call_kwargs)
	text = resp.choices[0].message.content or "{}"
	usage = getattr(resp, "usage", None)
	llm_cache.set(
		parts_key,
		text,
		prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
		completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
		total_tokens=getattr(usage, "total_tokens", None) if usage else None,
	)
	response_meta = {
		"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
		"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
		"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
	}
	tracemod.log_llm_event(
		endpoint="chat.completions",
		model=model,
		request_meta={"op": "judge_annotations", **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}), **({"verbosity": verbosity} if verbosity else {})},
		response_meta=response_meta,
		pair=None,
		input_text=body,
		output_text=text,
		extra_meta={"op": "judge_annotations"},
	)
	return _ensure_json_object(text)


# ------------------- embedding helpers -------------------

def _embedding_cache_key(model: str, scope: str, ident: str, text: str) -> str:
	# Use sha256 of text to keep keys small
	h = hashlib.sha256(text.encode("utf-8")).hexdigest()
	return _hash_key(["embed", model, scope, ident, h])


def embed_texts(client: Any, texts: List[str], model: Optional[str] = None, scope: str = "generic", id_prefix: str = "") -> List[List[float]]:
	"""Embed a list of texts with caching and tracing.

	- client: OpenAI client from require_client()
	- texts: list of strings
	- model: embedding model name; defaults to env EMBEDDING_MODEL or OpenAI default
	- scope/id_prefix: optional tags for cache keys
	"""
	if model is None:
		model = os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	results: List[List[float]] = []
	missing: List[tuple[int, str]] = []
	# First pass: try cache
	for i, t in enumerate(texts):
		key = _embedding_cache_key(model, scope, f"{id_prefix}{i}", t)
		cached = llm_cache.get(key)
		if cached is not None:
			try:
				vec = json.loads(cached)
				if isinstance(vec, list):
					results.append(vec)
					tracemod.note_cache_hit()
					continue
			except Exception:
				pass
		# mark as missing
		results.append([])
		missing.append((i, t))

	if missing:
		# Batch embed the missing items in manageable chunks
		try:
			max_batch_size = int(os.getenv("EMBED_BATCH", "128"))
		except Exception:
			max_batch_size = 128
		start_index = 0
		while start_index < len(missing):
			chunk = missing[start_index : start_index + max_batch_size]
			inputs = [t for _, t in chunk]
			resp = client.embeddings.create(model=model, input=inputs)
			# OpenAI returns data in order
			vecs = [d.embedding for d in resp.data]
			for (idx, text), vec in zip(chunk, vecs):
				results[idx] = list(vec)
				key = _embedding_cache_key(model, scope, f"{id_prefix}{idx}", text)
				try:
					llm_cache.set(key, json.dumps(results[idx]))
					tracemod.note_cache_store()
				except Exception:
					pass
			# trace this batch
			usage = getattr(resp, "usage", None)
			meta = {
				"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
				"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
				"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
			}
			tracemod.log_llm_event(
				endpoint="embeddings.create",
				model=model,
				request_meta={"count": len(inputs), "scope": scope},
				response_meta=meta,
				pair=None,
				input_text="\n".join(t[:200] for t in inputs[:3]),
				output_text=None,
				extra_meta={"op": "embed_batch"},
			)
			start_index += max_batch_size

	return results


def embed_text(client: Any, text: str, model: Optional[str] = None, scope: str = "generic", ident: str = "0") -> List[float]:
	vecs = embed_texts(client, [text], model=model, scope=scope, id_prefix=ident + ":")
	return vecs[0] if vecs else []


def meta_judge_llm(
	client: Any,
	judgments: List[Dict],
	model: str,
	reasoning_effort: Optional[str] = None,
	verbosity: Optional[str] = None,
) -> Dict:
	"""Summarize many judgment objects into prioritized problems and next queries."""
	snippets = []
	for j in judgments[-10:]:  # cap
		common = j.get("common_issues") or []
		suggest = j.get("suggested_queries") or []
		snippets.append(json.dumps({"common_issues": common, "suggested_queries": suggest}, ensure_ascii=False))
	body = "\n".join(snippets) or "{}"
	instructions = (
		"You are a meta-judge. Given multiple judge results, aggregate: top_issues (ranked), "
		"root_causes (short), recommended_queries (deduped), and action_items (succinct). Return STRICT JSON."
	)

	parts_key = _hash_key(["meta_judge_llm", model, instructions, body[:2000]])
	cached = llm_cache.get(parts_key)
	if cached is not None:
		tracemod.note_cache_hit()
		return _ensure_json_object(cached)

	extra: Dict[str, Any] = {}
	if reasoning_effort in {"minimal", "medium", "high"}:
		extra["reasoning"] = {"effort": reasoning_effort}
	if verbosity in {"low", "medium", "high"} and str(model).startswith("gpt-5"):
		extra["verbosity"] = verbosity
	is_gpt5 = str(model).startswith("gpt-5")
	call_kwargs: Dict[str, Any] = {
		"model": model,
		"messages": [
			{"role": "system", "content": instructions},
			{"role": "user", "content": body},
		],
		**extra,
	}
	if not is_gpt5:
		call_kwargs["temperature"] = 0.2
	resp = client.chat.completions.create(**call_kwargs)
	text = resp.choices[0].message.content or "{}"
	usage = getattr(resp, "usage", None)
	llm_cache.set(
		parts_key,
		text,
		prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
		completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
		total_tokens=getattr(usage, "total_tokens", None) if usage else None,
	)
	response_meta = {
		"prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
		"completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
		"total_tokens": getattr(usage, "total_tokens", None) if usage else None,
	}
	tracemod.log_llm_event(
		endpoint="chat.completions",
		model=model,
		request_meta={"op": "meta_judge", **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}), **({"verbosity": verbosity} if verbosity else {})},
		response_meta=response_meta,
		pair=None,
		input_text=body,
		output_text=text,
		extra_meta={"op": "meta_judge"},
	)
	return _ensure_json_object(text)

