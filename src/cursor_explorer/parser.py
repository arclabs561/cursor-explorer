import json
from typing import Iterable, List, Optional, Tuple

from . import db as dbmod
from .formatting import to_text


def parse_json(value: object) -> Optional[dict]:
	text = to_text(value)
	try:
		return json.loads(text)
	except Exception:
		return None


def list_composer_ids(conn) -> List[str]:
	keys = dbmod.composer_data_keys(conn, limit=10_000)
	ids: List[str] = []
	for k in keys:
		# Expect format composerData:<uuid>
		parts = k.split(":", 1)
		if len(parts) == 2 and parts[0] == "composerData" and parts[1]:
			ids.append(parts[1])
	return ids


def load_composer(conn, composer_id: str) -> Optional[dict]:
	val = dbmod.kv_value(conn, f"composerData:{composer_id}")
	if val is None:
		return None
	return parse_json(val)


def iter_bubble_headers(composer_obj: dict) -> Iterable[Tuple[str, Optional[int], Optional[str]]]:
	headers = composer_obj.get("fullConversationHeadersOnly") or []
	for h in headers:
		bubble_id = h.get("bubbleId")
		bubble_type = h.get("type")
		server_bubble_id = h.get("serverBubbleId")
		if bubble_id:
			yield bubble_id, bubble_type, server_bubble_id


def load_bubble(conn, composer_id: str, bubble_id: str) -> Optional[dict]:
	val = dbmod.kv_value(conn, f"bubbleId:{composer_id}:{bubble_id}")
	if val is None:
		return None
	return parse_json(val)


def bubble_role(bubble_type: Optional[int]) -> str:
	# Empirically: 1=user, 2=assistant
	return "user" if bubble_type == 1 else "assistant"


def reconstruct_conversation(conn, composer_id: str) -> List[dict]:
	composer = load_composer(conn, composer_id)
	if not composer:
		return []
	messages: List[dict] = []
	for bubble_id, bubble_type, server_bubble_id in iter_bubble_headers(composer):
		bubble = load_bubble(conn, composer_id, bubble_id)
		if not bubble:
			continue
		text = bubble.get("text") if isinstance(bubble, dict) else None
		if not text:
			# Fallback: some records might store content under alternate field names
			text = bubble.get("content") or ""
		messages.append({
			"composer_id": composer_id,
			"bubble_id": bubble_id,
			"server_bubble_id": server_bubble_id,
			"role": bubble_role(bubble_type),
			"text": text or "",
		})
	return messages


def _walk_dict(d):
	if isinstance(d, dict):
		for k, v in d.items():
			yield k, v
			for _ in _walk_dict(v):
				yield _
	elif isinstance(d, list):
		for it in d:
			for _ in _walk_dict(it):
				yield _


def extract_repo_hint(composer_obj: Optional[dict]) -> Optional[str]:
	"""Best-effort extraction of repository/workspace hint from a composer object.

	Heuristics:
	- Look for keys containing repo|repository|git|workspace|root|cwd|path|url
	- Prefer values that look like git remotes or filesystem paths
	- Return a short, human-friendly hint (basename or last two path segments)
	"""
	if not composer_obj:
		return None
	key_pat = ("repo", "repository", "git", "workspace", "root", "cwd", "path", "url")
	candidates: list[str] = []
	for k, v in _walk_dict(composer_obj):
		try:
			kl = str(k).lower() if k is not None else ""
			if any(p in kl for p in key_pat) and isinstance(v, str) and v:
				candidates.append(v)
		except Exception:
			continue
	# Rank candidates: git remotes > paths with separators > other strings
	def score(s: str) -> tuple[int, int]:
		is_git = ("github.com" in s.lower()) or s.lower().endswith(".git")
		is_path = ("/" in s) or ("\\" in s)
		return (2 if is_git else (1 if is_path else 0), -len(s))
	candidates.sort(key=score, reverse=True)
	for s in candidates:
		val = s.strip()
		low = val.lower()
		# If looks like a remote URL, extract repo name
		if "github.com" in low:
			parts = val.rstrip("/").split("/")
			if parts:
				name = parts[-1]
				if name.endswith(".git"):
					name = name[:-4]
				return name
		# If looks like a path, return last two segments
		if "/" in val or "\\" in val:
			sep = "/" if "/" in val else "\\"
			parts = [p for p in val.split(sep) if p]
			if parts:
				if len(parts) >= 2:
					return "/".join(parts[-2:])
				return parts[-1]
	# Fallback: first candidate as-is
	return candidates[0] if candidates else None


def _is_nonempty(text: str) -> bool:
	return bool(text and text.strip())


def coalesce_assistant_runs(messages: List[dict]) -> List[dict]:
	"""Merge consecutive assistant messages; drop empty assistant messages."""
	coalesced: List[dict] = []
	pending_assistant: Optional[dict] = None
	for m in messages:
		if m.get("role") == "assistant":
			if not _is_nonempty(m.get("text", "")):
				# Skip empty assistant bubbles
				continue
			if pending_assistant is None:
				pending_assistant = dict(m)
			else:
				pending_assistant["text"] = (pending_assistant.get("text", "") + "\n\n" + m.get("text", "")).strip()
		else:
			# Flush any pending assistant before a non-assistant
			if pending_assistant is not None:
				coalesced.append(pending_assistant)
				pending_assistant = None
			coalesced.append(m)
	# Flush tail
	if pending_assistant is not None:
		coalesced.append(pending_assistant)
	return coalesced


def build_qa_pairs(messages: List[dict]) -> List[dict]:
	"""Create user->assistant turn pairs with coalesced assistant content.

	Pairs are produced as soon as we encounter the next user, or at end.
	"""
	msgs = coalesce_assistant_runs(messages)
	pairs: List[dict] = []
	current_user: Optional[dict] = None
	current_assistant_text: List[str] = []
	turn_index = 0
	for m in msgs:
		role = m.get("role")
		text = m.get("text", "")
		if role == "user":
			# finalize previous turn
			if current_user is not None or current_assistant_text:
				pairs.append({
					"composer_id": current_user.get("composer_id") if current_user else m.get("composer_id"),
					"turn_index": turn_index,
					"user": current_user.get("text") if current_user else "",
					"assistant": "\n\n".join(current_assistant_text).strip(),
				})
				turn_index += 1
			current_user = m
			current_assistant_text = []
		elif role == "assistant":
			if _is_nonempty(text):
				current_assistant_text.append(text)
	# finalize last
	if current_user is not None or current_assistant_text:
		composer_id_value = ""
		if current_user is not None:
			composer_id_value = current_user.get("composer_id")
		elif messages:
			composer_id_value = messages[0].get("composer_id")
		pairs.append({
			"composer_id": composer_id_value,
			"turn_index": turn_index,
			"user": current_user.get("text") if current_user else "",
			"assistant": "\n\n".join(current_assistant_text).strip(),
		})
	return pairs
