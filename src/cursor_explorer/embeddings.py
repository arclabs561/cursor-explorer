from __future__ import annotations

from typing import List


def l2_normalize(vec: List[float]) -> List[float]:
	"""Return an L2-normalized copy of the vector. If norm is zero, return original.

	Cosine helpers live in `cursor_explorer.vector` to avoid duplication.
	"""
	sum_sq = sum((x * x) for x in vec)
	if sum_sq <= 0.0:
		return list(vec)
	den = sum_sq ** 0.5
	if den == 0.0:
		return list(vec)
	return [x / den for x in vec]


