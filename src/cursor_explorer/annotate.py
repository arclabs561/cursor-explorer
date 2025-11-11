from __future__ import annotations

from typing import Dict, List
import re


PREF_PATTERNS = [
	"prefer ",
	"my preference",
	"i like ",
	"i would rather",
	"we prefer",
	"we use ",
	"default to",
	"i want ",
]
DESIGN_PATTERNS = [
	"design",
	"architecture",
	"pattern",
	"abstraction",
	"contract",
	"api",
	"service",
	"schema",
	"storage",
	"embedding",
	"index",
]
LEARNING_PATTERNS = [
	"i learned",
	"lesson",
	"note to self",
	"remember to",
	"next time",
	"we found out",
]
UNFINISHED_PATTERNS = [
	"todo",
	"wip",
	"let me",
	"i'll ",
	"i will ",
	"next step",
	"follow up",
]
POSITIVE_WORDS = set(["great", "good", "nice", "love", "awesome", "cool", "works", "success"])  # minimal
NEGATIVE_WORDS = set(["bad", "broken", "fail", "hate", "issue", "bug", "problem", "worse"])  # minimal


def _contains_any(text: str, patterns: List[str]) -> bool:
	lower = text.lower()
	return any(p in lower for p in patterns)


def _has_code_or_commands(text: str) -> bool:
	return ("```" in text) or ("\n    " in text) or bool(re.search(r"\b(just|uv|pip|git|curl|python -m)\b", text))


def _clarity_bucket(text: str) -> str:
	"""Heuristic clarity: structure, bullets, code, or headings => higher clarity.

	Returns one of: low|medium|high
	"""
	low = (text or "")
	lines = low.splitlines()
	if "```" in low:
		return "high"
	bullet_or_numbered = any(re.match(r"^\s*(?:[-*]\s|\d+\.\s)", ln) for ln in lines)
	if bullet_or_numbered:
		return "high"
	if any(ln.strip().startswith(("###", "##", "# ")) for ln in lines):
		return "high"
	if re.search(r"\b(Summary:|Steps?:|Plan:|Next:)\b", low, flags=re.I):
		return "medium"
	if len(low) > 600 and not bullet_or_numbered:
		return "low"
	return "medium"


def _context_bucket(text: str) -> str:
	"""Heuristic context: cites files/paths/commands/links or gives rationale => higher context.

	Returns one of: low|medium|high
	"""
	low = (text or "")
	if "```" in low or re.search(r"\bhttps?://", low):
		return "high"
	if re.search(r"[`][^`]+[`]", low):  # inline code/backticks
		return "medium"
	if re.search(r"\b(src/|app/|/Users/|\.py\b|\.ts\b|\.tsx\b|\.js\b|\.md\b)", low):
		return "high"
	if re.search(r"\b(because|due to|so that|rationale|context)\b", low, flags=re.I):
		return "medium"
	return "low"


def _polarity(text: str) -> str:
	low = text.lower()
	pos = sum(1 for w in POSITIVE_WORDS if w in low)
	neg = sum(1 for w in NEGATIVE_WORDS if w in low)
	if pos > neg:
		return "positive"
	if neg > pos:
		return "negative"
	return "neutral"


def annotate_pair_simple(pair: Dict) -> Dict:
	"""Return lightweight annotations suitable for search filters.

	- length buckets
	- has_code
	- has_links
	- role counts
	"""
	user = pair.get("user", "") or ""
	assistant = pair.get("assistant", "") or ""
	combined = (user + "\n" + assistant).strip()

	def length_bucket(n: int) -> str:
		if n < 256:
			return "short"
		if n < 1024:
			return "medium"
		return "long"

	return {
		"length_bucket": length_bucket(len(combined)),
		"has_code": ("```" in combined) or ("\n    " in combined),
		"has_links": ("http://" in combined) or ("https://" in combined),
		"user_len": len(user),
		"assistant_len": len(assistant),
	}


def annotate_pair_rich(pair: Dict) -> Dict:
	user = pair.get("user", "") or ""
	assistant = pair.get("assistant", "") or ""
	combined = (user + "\n" + assistant).strip()
	annotations = annotate_pair_simple(pair)
	annotations.update({
		"user_polarity": _polarity(user),
		"assistant_polarity": _polarity(assistant),
		"unfinished_thread": _contains_any(assistant, UNFINISHED_PATTERNS) or assistant.strip().endswith("?"),
		"has_useful_output": _has_code_or_commands(assistant),
		"contains_preference": _contains_any(combined, PREF_PATTERNS),
		"contains_design": _contains_any(combined, DESIGN_PATTERNS),
		"contains_learning": _contains_any(combined, LEARNING_PATTERNS),
		"assistant_clarity": _clarity_bucket(assistant),
		"assistant_context": _context_bucket(assistant),
	})
	return annotations


def annotate_conversation_scales(pairs: List[Dict]) -> Dict:
	# Micro: per-turn heads
	micro = []
	for p in pairs[:10]:
		user_head = (p.get("user") or "").splitlines()[0][:120]
		assistant_head = (p.get("assistant") or "").splitlines()[0][:160]
		micro.append({"turn": p.get("turn_index"), "user_head": user_head, "assistant_head": assistant_head})

	# Meso: milestones (assistant imperative cues)
	milestones: List[str] = []
	starts = ["i'll", "let me", "now", "created", "added", "done", "next", "then", "updated"]
	for p in pairs:
		assistant_text = p.get("assistant") or ""
		for line in assistant_text.splitlines():
			strip_line = line.strip()
			if any(strip_line.lower().startswith(x) for x in starts):
				milestones.append(strip_line[:200])
				break

	# Macro: topic hint from earliest non-empty user
	macro = ""
	for p in pairs:
		u = (p.get("user") or "").strip()
		if u:
			macro = u[:200]
			break

	return {"micro": micro, "meso": milestones[:10], "macro": macro}
