from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

from .paths import expand_abs
import llm_helpers as llmmod


_STOP = {
	"the","a","an","and","or","to","of","in","on","for","with","is","it","this","that",
	"we","i","you","our","let","lets","let's","be","as","at","by","from","are","was","were",
	"do","did","does","have","has","had","will","would","can","could","should","if","then","else",
	"about","into","over","under","up","down","out","when","where","how","what","why","which",
}


def _read_index(index_jsonl: str, limit: Optional[int]) -> List[Dict]:
	rows: List[Dict] = []
	with open(expand_abs(index_jsonl), "r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if limit is not None and i >= limit:
				break
			try:
				rows.append(json.loads(line))
			except Exception:
				continue
	return rows


def _tokens(text: str) -> List[str]:
	words = re.findall(r"[A-Za-z0-9_]{3,}", (text or "").lower())
	return [w for w in words if w not in _STOP]


def _make_ngrams(words: List[str], n_min: int, n_max: int) -> List[str]:
	n_min = max(1, int(n_min))
	n_max = max(n_min, int(n_max))
	feats: List[str] = []
	if not words:
		return feats
	for n in range(n_min, n_max + 1):
		if n == 1:
			feats.extend(words)
		else:
			for i in range(0, max(0, len(words) - n + 1)):
				feats.append("_".join(words[i:i+n]))
	return feats


def _jaccard(a: List[str], b: List[str]) -> float:
	sa, sb = set(a), set(b)
	if not sa and not sb:
		return 1.0
	if not sa or not sb:
		return 0.0
	return len(sa & sb) / float(max(1, len(sa | sb)))


def analyze_user_transitions(
	index_jsonl: str,
	out_json: str,
	limit: Optional[int] = None,
	min_similarity: float = 0.3,
	use_embeddings: bool = False,
	ngram_min: int = 1,
	ngram_max: int = 1,
	group_topk: int = 8,
) -> Dict:
	"""Build user 'streams' and label transitions between their messages across chats.

	- Groups adjacent user messages into streams by similarity
	- Emits transitions with similarity and heuristic labels
	"""
	rows = _read_index(index_jsonl, limit)
	# Group by composer_id
	by_cid: Dict[str, List[Tuple[int, str, str]]] = {}
	for r in rows:
		cid = r.get("composer_id")
		tix = int(r.get("turn_index") or 0)
		uid = f"{cid}:{tix}"
		uhead = r.get("user_head") or r.get("user") or ""
		by_cid.setdefault(cid, []).append((tix, uid, uhead))
	for cid in by_cid:
		by_cid[cid].sort(key=lambda t: t[0])

	# Optional embeddings
	vecs: Dict[str, List[float]] = {}
	if use_embeddings:
		try:
			from sentence_transformers import SentenceTransformer  # type: ignore
			st = SentenceTransformer(os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"))
			texts = [u for lst in by_cid.values() for (_, _, u) in lst]
			emb = st.encode(texts, show_progress_bar=False)
			idx = 0
			for lst in by_cid.values():
				for _, uid, _ in lst:
					vecs[uid] = list(map(float, emb[idx]))
					idx += 1
		except Exception:
			use_embeddings = False

	def cos(a: List[float], b: List[float]) -> float:
		if not a or not b or len(a) != len(b):
			return 0.0
		dot = sum(x*y for x,y in zip(a,b))
		n1 = sum(x*x for x in a) ** 0.5
		n2 = sum(y*y for y in b) ** 0.5
		return (dot / (n1 * n2)) if (n1 > 0 and n2 > 0) else 0.0

	streams: List[Dict] = []
	transitions: List[Dict] = []
	for cid, lst in by_cid.items():
		current_stream: Dict = {"composer_id": cid, "ids": [], "topic_hint": [], "__tokens": []}
		prev_tokens: List[str] = []
		prev_uid: Optional[str] = None
		for _, uid, utext in lst:
			base_toks = _tokens(utext)
			toks = _make_ngrams(base_toks, ngram_min, ngram_max)
			sim = 0.0
			if prev_uid is not None:
				if use_embeddings and prev_uid in vecs and uid in vecs:
					sim = cos(vecs.get(prev_uid) or [], vecs.get(uid) or [])
				else:
					sim = _jaccard(prev_tokens, toks)
				label = (
					"refine" if sim >= min_similarity else
					("switch" if toks and prev_tokens else "start")
				)
				transitions.append({"from": prev_uid, "to": uid, "similarity": round(sim, 3), "label": label})
			# Start new stream if similarity is low or first item
			if prev_uid is None or sim < min_similarity or not current_stream["ids"]:
				if current_stream["ids"]:
					# finalize hint
					all_toks = _tokens(" ".join(current_stream.get("topic_hint") or []))
					freq: Dict[str,int] = {}
					for w in all_toks:
						freq[w] = freq.get(w,0)+1
					hint = [w for w,_ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:5]]
					current_stream["topic_hint"] = hint
					# compute group-level ngrams over accumulated base tokens
					grp_tokens: List[str] = current_stream.get("__tokens") or []
					grp_ngrams = _make_ngrams(grp_tokens, ngram_min, ngram_max)
					gfreq: Dict[str,int] = {}
					for g in grp_ngrams:
						gfreq[g] = gfreq.get(g,0)+1
					current_stream["ngrams"] = [g for g,_ in sorted(gfreq.items(), key=lambda kv: kv[1], reverse=True)[: max(1, int(group_topk))]]
					current_stream.pop("__tokens", None)
					streams.append(current_stream)
				current_stream = {"composer_id": cid, "ids": [], "topic_hint": [], "__tokens": []}
			current_stream["ids"].append(uid)
			current_stream["topic_hint"].append(" ".join(toks[:10]))
			# accumulate base tokens for group-level ngrams
			current_stream["__tokens"].extend(base_toks)
			prev_tokens = toks
			prev_uid = uid
		# finalize last stream
		if current_stream["ids"]:
			all_toks = _tokens(" ".join(current_stream.get("topic_hint") or []))
			freq: Dict[str,int] = {}
			for w in all_toks:
				freq[w] = freq.get(w,0)+1
			hint = [w for w,_ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:5]]
			current_stream["topic_hint"] = hint
			# compute group-level ngrams over accumulated base tokens
			grp_tokens2: List[str] = current_stream.get("__tokens") or []
			grp_ngrams2 = _make_ngrams(grp_tokens2, ngram_min, ngram_max)
			gfreq2: Dict[str,int] = {}
			for g in grp_ngrams2:
				gfreq2[g] = gfreq2.get(g,0)+1
			current_stream["ngrams"] = [g for g,_ in sorted(gfreq2.items(), key=lambda kv: kv[1], reverse=True)[: max(1, int(group_topk))]]
			current_stream.pop("__tokens", None)
			streams.append(current_stream)

	data = {
		"streams": streams,
		"transitions": transitions,
		"meta": {"composer_count": len(by_cid), "stream_count": len(streams), "transition_count": len(transitions), "min_similarity": float(min_similarity), "embeddings": bool(use_embeddings), "ngram_min": int(ngram_min), "ngram_max": int(ngram_max), "group_topk": int(group_topk)},
	}
	with open(expand_abs(out_json), "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	return data


def summarize_streams(streams_json: str, out_json: str, model: Optional[str] = None, max_streams: Optional[int] = None, max_ids: int = 10) -> Dict:
	"""LLM summarize each stream into 'thoughts' with open questions and next steps.

	- model: preferred small/fast model; defaults to OPENAI_SMALL_MODEL or gpt-5-nano
	- max_streams: summarize only first N streams
	- max_ids: include up to N IDs per stream in prompt body
	"""
	with open(expand_abs(streams_json), "r", encoding="utf-8") as f:
		obj = json.load(f) or {}
	streams = obj.get("streams", [])
	if max_streams is not None:
		streams = streams[: max(0, int(max_streams))]
	client = llmmod.require_client()
	mdl = model or os.getenv("OPENAI_SMALL_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-nano"))
	for s in streams:
		ids = s.get("ids") or []
		hint = ", ".join(s.get("topic_hint") or [])
		instr = (
			"Summarize this thought stream in STRICT JSON: {topic: string, progress: string, open_questions: [string], next_steps: [string]}"
		)
		body = f"Hint: {hint}\nIDs: {', '.join(ids[: max(1, int(max_ids))])}"
		resp = client.chat.completions.create(model=mdl, messages=[{"role":"system","content":instr},{"role":"user","content":body}])
		text = resp.choices[0].message.content or "{}"
		try:
			objj = json.loads(text)
		except Exception:
			objj = {"raw": text}
		s["summary"] = objj
		s.pop("topic_hint", None)
	with open(expand_abs(out_json), "w", encoding="utf-8") as f:
		json.dump({"streams": streams, "meta": obj.get("meta", {})}, f, ensure_ascii=False, indent=2)
	return {"streams": streams, "meta": obj.get("meta", {})}



def _llm_json(client, model: str, system: str, user: str) -> Dict:
	resp = client.chat.completions.create(model=model, messages=[{"role":"system","content":system},{"role":"user","content":user}])
	text = resp.choices[0].message.content or "{}"
	try:
		return json.loads(text)
	except Exception:
		return {"raw": text}


def summarize_streams_recursive(streams_json: str, out_json: str, model: Optional[str] = None, fanout: int = 6, depth: int = 2, max_streams: Optional[int] = None, max_ids: int = 5) -> Dict:
	"""Hierarchical (RAPTOR-like) summarization over streams.

	- Produces level 0 per-stream summaries, then recursively summarizes groups of `fanout` into higher levels.
	- Keeps prompts tiny for speed; defaults to OPENAI_SMALL_MODEL.
	"""
	with open(expand_abs(streams_json), "r", encoding="utf-8") as f:
		obj = json.load(f) or {}
	streams = obj.get("streams", [])
	if max_streams is not None:
		streams = streams[: max(0, int(max_streams))]
	client = llmmod.require_client()
	mdl = model or os.getenv("OPENAI_SMALL_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-nano"))

	# Level 0: leaf summaries (very concise)
	leaves: List[Dict] = []
	for s in streams:
		ids = s.get("ids") or []
		hint = ", ".join(s.get("topic_hint") or [])
		system = "Return STRICT JSON: {topic, progress, open_questions:[string], next_steps:[string]} in <= 60 words total."
		user = f"Hint:{hint}\nIDs:{', '.join(ids[: max(1, int(max_ids))])}"
		summ = _llm_json(client, mdl, system, user)
		leaves.append({"ids": ids[: max(1, int(max_ids))], "summary": summ})

	levels: List[Dict] = [{"level": 0, "items": leaves}]

	current = leaves
	for d in range(max(0, int(depth))):
		if not current:
			break
		groups: List[List[Dict]] = []
		chunk = max(1, int(fanout))
		for i in range(0, len(current), chunk):
			groups.append(current[i:i+chunk])
		next_level: List[Dict] = []
		for grp in groups:
			# Build a compact meta-summary prompt from child summaries
			def _stringify(val, lim: int = 160) -> str:
				try:
					if isinstance(val, dict):
						val = json.dumps(val, ensure_ascii=False)
					elif isinstance(val, list):
						val = ", ".join([str(x) for x in val])
					else:
						val = str(val)
				except Exception:
					val = str(val)
				return (val if len(val) <= lim else (val[: lim - 3] + "..."))

			parts = []
			for idx, item in enumerate(grp[:chunk]):
				js = item.get("summary")
				if isinstance(js, dict):
					topic = _stringify(js.get("topic", ""), 80)
					progress = _stringify(js.get("progress", ""), 120)
				else:
					topic = _stringify(js, 80)
					progress = ""
				parts.append(f"[{idx}] topic:{topic} progress:{progress}")
			system = "Merge child topics into STRICT JSON {topic, progress, open_questions:[string], next_steps:[string]}. Be concise, aggregate not repeat."
			user = "\n".join(parts)
			summ = _llm_json(client, mdl, system, user)
			next_level.append({"children": grp, "summary": summ})
		levels.append({"level": len(levels), "items": next_level})
		current = next_level

	out = {"levels": levels, "meta": obj.get("meta", {})}
	with open(expand_abs(out_json), "w", encoding="utf-8") as f:
		json.dump(out, f, ensure_ascii=False, indent=2)
	return out

