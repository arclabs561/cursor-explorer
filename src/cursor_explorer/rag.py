from __future__ import annotations

from typing import Dict, List, Tuple

from . import parser as parsermod
from . import annotate as annotatemod


def _head(text: str, n: int) -> str:
	lines = (text or "").strip().splitlines()
	if not lines:
		return ""
	return lines[0][:n]


def build_turn_items(messages: List[Dict]) -> List[Dict]:
	pairs = parsermod.build_qa_pairs(messages)
	items: List[Dict] = []
	for p in pairs:
		ann = annotatemod.annotate_pair_rich(p)
		items.append({
			"composer_id": p.get("composer_id"),
			"turn_index": p.get("turn_index"),
			"user": p.get("user", ""),
			"assistant": p.get("assistant", ""),
			"user_head": _head(p.get("user", ""), 160),
			"assistant_head": _head(p.get("assistant", ""), 200),
			"annotations": ann,
		})
	return items


def _score(query: str, text: str) -> int:
	q = query.lower().split()
	low = (text or "").lower()
	return sum(1 for token in q if token and token in low)


def search_items(items: List[Dict], query: str, k: int = 10) -> List[Dict]:
	scored: List[Tuple[int, Dict]] = []
	for it in items:
		text = (it.get("user", "") + "\n" + it.get("assistant", "")).strip()
		s = _score(query, text)
		# light boost for tags
		ann = it.get("annotations") or {}
		tags = ann.get("tags") or []
		for t in tags:
			if t and t.lower() in query.lower():
				s += 2
		scored.append((s, it))
	scored.sort(key=lambda x: x[0], reverse=True)
	return [it for s, it in scored[:k] if s > 0]


