from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple, Any

import llm_helpers as llmmod
from .paths import expand_abs
from .embeddings import l2_normalize
# pyd_models removed - using dicts directly


def _build_text_from_item(obj: Dict[str, Any]) -> str:
	uh = obj.get("user_head") or obj.get("user") or ""
	ah = obj.get("assistant_head") or obj.get("assistant") or ""
	ann = obj.get("annotations") or {}
	meta_bits: List[str] = []
	for k in [
		"contains_design",
		"contains_preference",
		"contains_learning",
		"unfinished_thread",
		"has_useful_output",
	]:
		if ann.get(k):
			meta_bits.append(k)
	for t in (ann.get("tags") or []):
		if isinstance(t, str) and t:
			meta_bits.append(f"tag:{t}")
	meta_text = (" ".join(meta_bits)).strip()
	text = (uh + "\n" + ah + ("\n" + meta_text if meta_text else "")).strip()[:1200]
	return text


def _kmeans2(vecs: List[List[float]], iters: int = 15) -> Tuple[List[int], List[float], List[float]]:
	if not vecs:
		return [], [], []
	# seed with first/last
	c0 = vecs[0][:]
	c1 = vecs[-1][:]
	assign = [0] * len(vecs)
	for _ in range(max(1, iters)):
		# assign
		for i, v in enumerate(vecs):
			# use cosine distance on normalized vectors
			# vectors are normalized; cosine distance = 1 - dot
			d0 = 1.0 - sum(x*y for x,y in zip(v, c0))
			d1 = 1.0 - sum(x*y for x,y in zip(v, c1))
			assign[i] = 0 if d0 <= d1 else 1
		# update
		s0 = [0.0] * len(vecs[0])
		s1 = [0.0] * len(vecs[0])
		n0 = 0
		n1 = 0
		for v, a in zip(vecs, assign):
			if a == 0:
				s0 = [x + y for x, y in zip(s0, v)]
				n0 += 1
			else:
				s1 = [x + y for x, y in zip(s1, v)]
				n1 += 1
		if n0:
			c0 = [x / max(1, n0) for x in s0]
		if n1:
			c1 = [x / max(1, n1) for x in s1]
	return assign, c0, c1


def _bisect_recursive(vecs: List[List[float]], idxs: List[int], depth: int, min_size: int) -> Dict:
	if depth <= 0 or len(idxs) <= max(2, min_size):
		return {"size": len(idxs), "ids": idxs}
	# run k=2 on subset
	subset = [vecs[i] for i in idxs]
	assign, _, _ = _kmeans2(subset)
	left: List[int] = []
	right: List[int] = []
	for local_i, a in enumerate(assign):
		g = left if a == 0 else right
		g.append(idxs[local_i])
	# guard tiny splits
	if not left or not right:
		return {"size": len(idxs), "ids": idxs}
	return {
		"size": len(idxs),
		"left": _bisect_recursive(vecs, left, depth - 1, min_size),
		"right": _bisect_recursive(vecs, right, depth - 1, min_size),
	}


def build_cluster_tree(index_jsonl: str, out_json: str, depth: int = 3, min_size: int = 20, embed_model: str | None = None, limit: int | None = None) -> Dict:
	index_jsonl = expand_abs(index_jsonl)
	out_json = expand_abs(out_json)
	# load items
	ids: List[str] = []
	texts: List[str] = []
	with open(index_jsonl, "r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if limit is not None and i >= limit:
				break
			try:
				obj = json.loads(line)
			except Exception:
				continue
			ident = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
			ids.append(ident)
			texts.append(_build_text_from_item(obj))
	# Embeddings backend selection: default to fast offline hashing.
	# Override via CLUSTER_EMBED_BACKEND=hash|st|openai
	backend = (os.getenv("CLUSTER_EMBED_BACKEND", "hash") or "hash").lower()
	vecs: List[List[float]] = []
	if backend == "hash":
		import hashlib
		def hv(t: str) -> List[float]:
			h = hashlib.sha256((t or "").encode("utf-8")).digest()
			arr = [float(int.from_bytes(h[i:i+2], "big")) for i in range(0, 32, 2)]
			s = sum(x*x for x in arr) ** 0.5 or 1.0
			return [x / s for x in arr]
		vecs = [hv(t) for t in texts]
	elif backend == "st":
		try:
			from sentence_transformers import SentenceTransformer  # type: ignore
			st_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
			st = SentenceTransformer(st_name)
			emb = st.encode(texts, show_progress_bar=False)
			vecs = [l2_normalize(list(map(float, v))) for v in emb]
		except Exception:
			# fallback to hash if ST unavailable
			backend = "hash"
			import hashlib
			def hv2(t: str) -> List[float]:
				h = hashlib.sha256((t or "").encode("utf-8")).digest()
				arr = [float(int.from_bytes(h[i:i+2], "big")) for i in range(0, 32, 2)]
				s = sum(x*x for x in arr) ** 0.5 or 1.0
				return [x / s for x in arr]
			vecs = [hv2(t) for t in texts]
	elif backend == "openai":
		try:
			client = llmmod.require_client()
			model = embed_model or os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
			res = client.embeddings.create(model=model, input=texts)
			vecs = [l2_normalize(list(d.embedding)) for d in res.data]
		except Exception:
			# fallback to hash
			import hashlib
			def hv3(t: str) -> List[float]:
				h = hashlib.sha256((t or "").encode("utf-8")).digest()
				arr = [float(int.from_bytes(h[i:i+2], "big")) for i in range(0, 32, 2)]
				s = sum(x*x for x in arr) ** 0.5 or 1.0
				return [x / s for x in arr]
			vecs = [hv3(t) for t in texts]
	# cluster
	root = _bisect_recursive(vecs, list(range(len(ids))), depth, min_size)
	# write
	data = {"ids": ids, "tree": root, "meta": {"depth": depth, "min_size": min_size, "count": len(ids)}}
	with open(out_json, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	return data


# ------------------- Toponymy naming (optional) -------------------

def build_toponymy_topics(
	index_jsonl: str,
	out_json: str,
	embed_model: str | None = None,
	limit: int | None = None,
	min_clusters: int = 4,
	umap_dim: int = 2,
	verbose: bool = False,
) -> Dict[str, Any]:
	"""Generate hierarchical topic names for documents using Toponymy.

	Reads items from a JSONL index, embeds them (cached), computes a low-dimensional
	map via UMAP, runs Toponymy to produce layered topic names, and writes a JSON.

	Optional dependency: requires 'toponymy', 'numpy', and 'umap-learn'. It will
	also require an LLM provider; we use OpenAI via Toponymy's wrapper and expect
	OPENAI_API_KEY to be set in the environment.
	"""
	try:
		import numpy as np  # type: ignore
		import umap  # type: ignore
		from toponymy import Toponymy, ToponymyClusterer  # type: ignore
		from toponymy.llm_wrappers import OpenAI as TopoOpenAI  # type: ignore
		try:
			from toponymy.embedding_wrappers import OpenAIEmbedder as TopoOpenAIEmbedder  # type: ignore
		except Exception:  # pragma: no cover - optional wrapper
			TopoOpenAIEmbedder = None  # type: ignore
	except Exception as e:  # pragma: no cover - environment dependent
		raise RuntimeError("toponymy (and numpy, umap-learn) are required: pip install toponymy numpy umap-learn") from e

	index_jsonl = expand_abs(index_jsonl)
	out_json = expand_abs(out_json)
	# load items
	ids: List[str] = []
	texts: List[str] = []
	with open(index_jsonl, "r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if limit is not None and i >= limit:
				break
			try:
				obj = json.loads(line)
			except Exception:
				continue
			ident = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
			ids.append(ident)
			texts.append(_build_text_from_item(obj))
	if not texts:
		data = {"ids": [], "layers": [], "topics_per_document": [], "meta": {"count": 0}}
		with open(out_json, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		return data

	# Document embeddings: prefer local SentenceTransformer to avoid API issues/costs
	try:
		from sentence_transformers import SentenceTransformer  # type: ignore
	except Exception as e:
		raise RuntimeError("sentence-transformers is required for Toponymy topics: pip install sentence_transformers") from e
	# Choose a small, widely available model
	st_model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
	st = SentenceTransformer(st_model_name)
	mat = st.encode(texts, show_progress_bar=bool(verbose))
	# Normalize vectors for cosine-based steps downstream
	try:
		mat = np.array([l2_normalize(list(v)) for v in mat], dtype=np.float32)
	except Exception:
		mat = np.array(mat, dtype=np.float32)

	# low-dimensional map for clustering (UMAP)
	um = umap.UMAP(metric='cosine', n_components=max(2, int(umap_dim)))
	coords = um.fit_transform(mat)

	# LLM wrapper (OpenAI via env key)
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise RuntimeError("OPENAI_API_KEY must be set for Toponymy naming")
	llm = TopoOpenAI(api_key)

	# Text embedding model for exemplar selection — reuse SentenceTransformer
	embedder = st

	# Clusterer and model
	clusterer = ToponymyClusterer(min_clusters=int(min_clusters), verbose=bool(verbose))
	top = Toponymy(
		llm_wrapper=llm,
		text_embedding_model=embedder,  # may be None; library may fall back
		clusterer=clusterer,
		object_description="chat turns",
		corpus_description="Cursor conversations",
		exemplar_delimiters=["<EXAMPLE_TURN>\n", "\n</EXAMPLE_TURN>\n\n"],
	)

	# Fit and extract topic names per layer
	# Toponymy expects: text (list[str]), document_vectors (np.ndarray), document_map (np.ndarray)
	top.fit(texts, mat, coords)
	# Collect names per layer and per-document labels per layer
	try:
		layers_names = top.topic_names_  # list[list[str]]
	except Exception:
		layers_names = []
	try:
		doc_topics_per_layer = [cl.topic_name_vector for cl in top.cluster_layers_]
	except Exception:
		doc_topics_per_layer = []

	data = {
		"ids": ids,
		"layers": [[str(n) for n in layer] for layer in (layers_names or [])],
		"topics_per_document": [list(map(lambda x: str(x), vec)) for vec in (doc_topics_per_layer or [])],
		"meta": {
			"count": len(ids),
			"embed_model": st_model_name,
			"library": "toponymy",
			"umap_dim": int(umap_dim),
			"min_clusters": int(min_clusters),
		},
	}
	with open(out_json, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	return data


def summarize_clusters(tree_json: str, index_jsonl: str, out_json: str, max_samples_per_node: int = 20, model: str | None = None) -> Dict:
	# Load tree and items
	with open(expand_abs(tree_json), "r", encoding="utf-8") as f:
		tree = json.load(f)
	items: Dict[str, Dict] = {}
	with open(expand_abs(index_jsonl), "r", encoding="utf-8") as f:
		for line in f:
			try:
				obj = json.loads(line)
			except Exception:
				continue
			ident = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
			items[ident] = obj
	client = llmmod.require_client()
	model = model or os.getenv("OPENAI_MODEL", "gpt-5")

	def collect_ids(node: Dict) -> List[str]:
		if "ids" in node:
			return [tree["ids"][i] for i in node["ids"]]
		ids_acc: List[str] = []
		if "left" in node:
			ids_acc.extend(collect_ids(node["left"]))
		if "right" in node:
			ids_acc.extend(collect_ids(node["right"]))
		return ids_acc

	def summarize_node(node: Dict) -> None:
		ids_here = collect_ids(node)
		samples = []
		for ident in ids_here[:max_samples_per_node]:
			obj = items.get(ident) or {}
			samples.append(_build_text_from_item(obj))
		body = "\n\n".join(samples)
		instr = (
			"Summarize this cluster: provide: title (short), themes (3-7 bullets), risks (2-5 bullets), and 5 short tag-like labels. "
			"Be specific and avoid generic terms. Return STRICT JSON with keys: title, themes, risks, labels."
		)
		resp = client.chat.completions.create(model=model, messages=[
			{"role": "system", "content": instr},
			{"role": "user", "content": body},
		])
		text = resp.choices[0].message.content or "{}"
		try:
			obj = json.loads(text)
			node["summary"] = obj
		except Exception:
			node["summary_raw"] = text
		if "left" in node:
			summarize_node(node["left"])
		if "right" in node:
			summarize_node(node["right"])

	summarize_node(tree["tree"])
	with open(expand_abs(out_json), "w", encoding="utf-8") as f:
		json.dump(tree, f, ensure_ascii=False, indent=2)
	return tree




# ------------------- EVōC clustering (optional) -------------------

def build_evoc_clusters(
	index_jsonl: str,
	out_json: str,
	embed_model: str | None = None,
	limit: int | None = None,
) -> Dict[str, Any]:
	"""Cluster embeddings with EVōC into multiple granularity layers.

	Reads items from a JSONL index, embeds them (cached), runs EVōC, and writes a
	JSON with cluster layers and optional hierarchy metadata.

	Requires the 'evoc' package. If not installed, raises a RuntimeError.
	"""
	try:
		import numpy as np  # type: ignore
		import evoc  # type: ignore
	except Exception as e:  # pragma: no cover - environment dependent
		raise RuntimeError("evoc (and numpy) are required: pip install evoc numpy") from e

	index_jsonl = expand_abs(index_jsonl)
	out_json = expand_abs(out_json)
	# load items
	ids: List[str] = []
	texts: List[str] = []
	with open(index_jsonl, "r", encoding="utf-8") as f:
		for i, line in enumerate(f):
			if limit is not None and i >= limit:
				break
			try:
				obj = json.loads(line)
			except Exception:
				continue
			ident = f"{obj.get('composer_id')}:{obj.get('turn_index')}"
			ids.append(ident)
			texts.append(_build_text_from_item(obj))
	if not texts:
		data = {"ids": [], "layers": [], "meta": {"count": 0}}
		with open(out_json, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		return data

	# embed with cache
	client = llmmod.require_client()
	model = embed_model or os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
	vecs = llmmod.embed_texts(client, texts, model=model, scope="evoc", id_prefix="it:")
	vecs = [l2_normalize(v) for v in vecs]
	mat = np.array(vecs, dtype=np.float32)

	# run EVōC
	clusterer = evoc.EVoC()
	labels = clusterer.fit_predict(mat)
	# Convert outputs to JSON-friendly
	layers = []
	if getattr(clusterer, "cluster_layers_", None) is not None:
		for layer in clusterer.cluster_layers_:
			try:
				layers.append([int(x) for x in list(layer)])
			except Exception:
				layers.append([int(x) for x in layer])
	finest = [int(x) for x in list(labels)]
	dups = None
	if getattr(clusterer, "duplicates_", None) is not None:
		try:
			dups = [int(x) for x in list(clusterer.duplicates_)]
		except Exception:
			pass
	# tree may be complex; include only if JSON-serializable
	tree = None
	if getattr(clusterer, "cluster_tree_", None) is not None:
		try:
			json.dumps(clusterer.cluster_tree_)
			tree = clusterer.cluster_tree_
		except Exception:
			# fallback: omit non-serializable content
			tree = None

	data = {
		"ids": ids,
		"finest_labels": finest,
		"layers": layers,
		"duplicates": dups,
		"tree": tree,
		"meta": {"count": len(ids), "embed_model": model, "library": "evoc"},
	}
	with open(out_json, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	return data
