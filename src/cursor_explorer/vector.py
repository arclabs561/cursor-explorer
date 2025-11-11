from __future__ import annotations

from typing import List, Tuple


def _dot(a: List[float], b: List[float]) -> float:
	return sum(x * y for x, y in zip(a, b))


def _norm(a: List[float]) -> float:
	s = sum(x * x for x in a)
	return s ** 0.5 if s > 0.0 else 0.0


def cosine_similarity(a: List[float], b: List[float]) -> float:
	"""Return cosine similarity in [-1, 1]. If a or b is zero, returns 0.0."""
	n1 = _norm(a)
	n2 = _norm(b)
	if n1 == 0.0 or n2 == 0.0:
		return 0.0
	return _dot(a, b) / (n1 * n2)


def topk(query_vec: List[float], corpus_vecs: List[List[float]], k: int) -> List[Tuple[int, float]]:
	"""Return top-k (index, score) by cosine similarity, descending."""
	scores: List[Tuple[int, float]] = []
	for idx, v in enumerate(corpus_vecs):
		s = cosine_similarity(query_vec, v)
		scores.append((idx, s))
	scores.sort(key=lambda x: x[1], reverse=True)
	return scores[: max(0, k)]


