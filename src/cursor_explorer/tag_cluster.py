from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import llm_helpers as llmmod
from .paths import expand_abs
from .embeddings import l2_normalize


def _kmeans_2(vectors: List[List[float]], iters: int = 15) -> Tuple[List[float], List[float], List[int]]:
    """Very small K=2 k-means for clustering tag embeddings."""
    if not vectors:
        return [], [], []
    # deterministic seeds: first and last
    c0 = vectors[0][:]
    c1 = vectors[-1][:]
    assign: List[int] = [0] * len(vectors)
    for _ in range(max(1, iters)):
        # assign
        for i, v in enumerate(vectors):
            d0 = sum((a - b) * (a - b) for a, b in zip(v, c0))
            d1 = sum((a - b) * (a - b) for a, b in zip(v, c1))
            assign[i] = 0 if d0 <= d1 else 1
        # update
        s0 = [0.0] * len(vectors[0])
        s1 = [0.0] * len(vectors[0])
        n0 = 0
        n1 = 0
        for v, a in zip(vectors, assign):
            if a == 0:
                s0 = [x + y for x, y in zip(s0, v)]
                n0 += 1
            else:
                s1 = [x + y for x, y in zip(s1, v)]
                n1 += 1
        if n0:
            c0 = [x / n0 for x in s0]
        if n1:
            c1 = [x / n1 for x in s1]
    return c0, c1, assign


def build_tag_clusters(index_jsonl: str, out_json: str, embed_model: str | None = None) -> Dict[str, str]:
    """Read JSONL index, collect unique tags, cluster into 2 groups, and write mapping."""
    index_jsonl = expand_abs(index_jsonl)
    out_json = expand_abs(out_json)
    tags: List[str] = []
    seen = set()
    with open(index_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            ann = obj.get("annotations") or {}
            for t in (ann.get("tags") or []):
                if isinstance(t, str) and t and t not in seen:
                    seen.add(t)
                    tags.append(t)
    if not tags:
        mapping: Dict[str, str] = {}
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        return mapping

    client = llmmod.require_client()
    model = embed_model or os.getenv("OPENAI_EMBED_MODEL", os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    res = client.embeddings.create(model=model, input=tags)
    vecs = [l2_normalize(list(d.embedding)) for d in res.data]
    _, _, assign = _kmeans_2(vecs)
    mapping = {t: ("clusterA" if a == 0 else "clusterB") for t, a in zip(tags, assign)}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    return mapping


def derive_tag_cluster_path(index_jsonl: str) -> str:
    base = expand_abs(index_jsonl)
    if base.endswith(".jsonl"):
        return base[:-6] + ".tags.json"
    return base + ".tags.json"


def load_tag_clusters(index_jsonl: str) -> Dict[str, str]:
    path = derive_tag_cluster_path(index_jsonl)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


