from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

_context: Dict[str, str] = {}
_run_counters: Dict[str, int] = {
	"events": 0,
	"cache_hits": 0,
	"cache_stores": 0,
	"prompt_tokens": 0,
	"completion_tokens": 0,
	"total_tokens": 0,
}


def set_context(meta: Dict[str, str]) -> None:
	# Merge, last-write-wins
	for k, v in (meta or {}).items():
		if v is None:
			continue
		_context[str(k)] = str(v)


def _log_path() -> str:
	return os.getenv("LLM_LOG_PATH", "llm_usage.jsonl")


def _should_log(flag_env: str, default: bool = True) -> bool:
	val = os.getenv(flag_env)
	if val is None:
		return default
	return val.strip() not in ("0", "false", "False", "no", "NO")


def _truncate(text: Optional[str]) -> Optional[str]:
	if text is None:
		return None
	limit_str = os.getenv("LLM_LOG_TRUNCATE", "2000")
	try:
		limit = int(limit_str)
	except Exception:
		limit = 2000
	if len(text) <= limit:
		return text
	return text[:limit] + "\n... [truncated]"


def _write_event(event: Dict) -> None:
	try:
		with open(_log_path(), "a", encoding="utf-8") as f:
			f.write(json.dumps(event, ensure_ascii=False) + "\n")
	except Exception:
		return


def log_llm_event(
	endpoint: str,
	model: str,
	request_meta: Dict,
	response_meta: Dict,
	pair: Optional[Dict] = None,
	input_text: Optional[str] = None,
	output_text: Optional[str] = None,
	extra_meta: Optional[Dict] = None,
) -> None:
	"""Log an LLM call with rich metadata.

	Always logs to JSONL with ts and global context, with optional input/output previews
	controlled by LLM_LOG_INPUT/LLM_LOG_OUTPUT.
	"""
	event: Dict = {
		"ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
		"endpoint": endpoint,
		"model": model,
		"request": request_meta or {},
		"response": response_meta or {},
		"context": dict(_context),
	}
	if extra_meta:
		event["meta"] = extra_meta
	if pair is not None:
		event["composer_id"] = pair.get("composer_id")
		event["turn_index"] = pair.get("turn_index")
		# Include variant attack label if present for audit trails
		attack = pair.get("attack") if isinstance(pair, dict) else None
		if attack:
			event["attack"] = attack
	if _should_log("LLM_LOG_INPUT", True):
		event["input_preview"] = _truncate(input_text or "")
	if _should_log("LLM_LOG_OUTPUT", True):
		event["output_preview"] = _truncate(output_text or "")
	_write_event(event)
	# update counters from response_meta if present
	pt = response_meta.get("prompt_tokens") if isinstance(response_meta, dict) else None
	ct = response_meta.get("completion_tokens") if isinstance(response_meta, dict) else None
	tt = response_meta.get("total_tokens") if isinstance(response_meta, dict) else None
	if isinstance(pt, int):
		_run_counters["prompt_tokens"] += pt
	if isinstance(ct, int):
		_run_counters["completion_tokens"] += ct
	if isinstance(tt, int):
		_run_counters["total_tokens"] += tt
	_run_counters["events"] += 1


def log_event(kind: str, data: Dict) -> None:
	"""Log a generic event with current context."""
	event = {
		"ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
		"kind": kind,
		"context": dict(_context),
		"data": data or {},
	}
	_write_event(event)
	_run_counters["events"] += 1


def note_cache_hit() -> None:
	_run_counters["cache_hits"] += 1


def note_cache_store() -> None:
	_run_counters["cache_stores"] += 1


def get_run_summary() -> Dict:
	return {
		"events": _run_counters["events"],
		"cache": {
			"hits": _run_counters["cache_hits"],
			"stores": _run_counters["cache_stores"],
		},
		"tokens": {
			"prompt": _run_counters["prompt_tokens"],
			"completion": _run_counters["completion_tokens"],
			"total": _run_counters["total_tokens"],
		},
	}


