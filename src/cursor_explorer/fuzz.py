from __future__ import annotations

import os
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import adversary as adversarymod
from . import annotate as annotatemod
from . import trace as tracemod
from . import pyd_models as pmodels
import llm_helpers as llmmod


def _score_variant(annotations: Dict) -> float:
	# Simple heuristic score to prioritize interesting cases
	score = 0.0
	if annotations.get("has_useful_output"):
		score += 1.0
	if annotations.get("contains_design"):
		score += 0.5
	if annotations.get("unfinished_thread"):
		score += 0.2
	return score


def _read_seeds(seed_args: List[str] | None, seed_file: str | None) -> List[str]:
	seeds: List[str] = []
	if seed_args:
		seeds.extend([s for s in seed_args if s])
	if seed_file and os.path.exists(seed_file):
		with open(seed_file, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if line:
					seeds.append(line)
	return seeds


def read_seeds(seed_args: List[str] | None, seed_file: str | None) -> List[str]:
	"""Public wrapper for reading seeds (preferred for external callers)."""
	return _read_seeds(seed_args, seed_file)


def _validate_llm_schema(obj: Dict) -> List[str]:
	# Prefer Pydantic models when available
	if pmodels.have_pydantic():
		ok, _ = pmodels.validate_annotation(obj)
		return [] if ok else ["pydantic_error"]
	required = [
		"user_summary",
		"assistant_summary",
		"user_polarity",
		"assistant_polarity",
		"unfinished_thread",
		"has_useful_output",
		"contains_preference",
		"contains_design",
		"contains_learning",
		"tags",
	]
	return [f"missing:{k}" for k in required if k not in obj]


def run_fuzz(
	seed_texts: List[str],
	iterations: int = 1,
	use_llm: bool = False,
	llm_model: str | None = None,
) -> Dict[str, Any]:
	client = None
	if use_llm:
		client = llmmod.require_client()
		model = llm_model or os.getenv("OPENAI_MODEL", "gpt-5")

	runs: List[Dict[str, Any]] = []
	current_seeds = list(seed_texts)
	for it in range(max(1, iterations)):
		iteration_log: Dict[str, Any] = {"iteration": it + 1, "inputs": list(current_seeds), "variants": []}
		for seed in current_seeds:
			pair = {"user": seed, "assistant": ""}
			variants = adversarymod.generate_adversarials(pair)
			# Heuristic annotations first
			base_entries: List[Dict[str, Any]] = []
			for v in variants:
				ann = annotatemod.annotate_pair_rich(v)
				base_entries.append({"variant": v, "heuristic": ann})

			# LLM annotations with light concurrency (up to 4 workers)
			if client is not None and base_entries:
				def task(e: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict], Optional[str], List[str]]:
					try:
						llm_ann = llmmod.annotate_pair_llm(client, e["variant"], model)
						issues = _validate_llm_schema(llm_ann) if isinstance(llm_ann, dict) else ["not_dict"]
						return e, llm_ann, None, issues
					except Exception as ex:
						return e, None, str(ex), []

				worker_count = min(4, len(base_entries))
				if worker_count > 1:
					with ThreadPoolExecutor(max_workers=worker_count) as pool:
						futs = [pool.submit(task, e) for e in base_entries]
						for fut in as_completed(futs):
							e, llm_ann, err, issues = fut.result()
							if llm_ann is not None:
								e["llm"] = llm_ann
							if err:
								e["llm_error"] = err
							if issues:
								e.setdefault("llm_issues", issues)
				else:
					for e in base_entries:
						be, llm_ann, err, issues = task(e)
						if llm_ann is not None:
							be["llm"] = llm_ann
						if err:
							be["llm_error"] = err
						if issues:
							be.setdefault("llm_issues", issues)

			for e in base_entries:
				# Compute and record a simple score for auditing/selection transparency
				score_val = _score_variant(e.get("heuristic", {}))
				e["score"] = score_val
				iteration_log["variants"].append(e)
				tracemod.log_event("fuzz_variant", {"iteration": it + 1, **e})
		runs.append(iteration_log)
		# Choose next seeds: top-scoring variant user texts, distinct
		candidates: List[Tuple[float, str]] = []
		for entry in iteration_log["variants"]:
			score = _score_variant(entry.get("heuristic", {}))
			user_text = entry["variant"].get("user", "")
			if user_text:
				candidates.append((score, user_text))
		# sort by score descending then pick top few
		candidates.sort(key=lambda x: x[0], reverse=True)
		next_seeds = []
		seen = set()
		for _, text in candidates[:5]:
			if text not in seen:
				next_seeds.append(text)
				seen.add(text)
		# Log iteration summary for audit trail
		iteration_summary = {
			"iteration": it + 1,
			"inputs": list(iteration_log.get("inputs", [])),
			"candidates": [{"text": t, "score": s} for s, t in candidates[:20]],
			"next_seeds": list(next_seeds),
		}
		iteration_log["next_seeds"] = list(next_seeds)
		iteration_log["candidates"] = iteration_summary["candidates"]
		tracemod.log_event("fuzz_iteration_summary", iteration_summary)
		current_seeds = next_seeds or current_seeds

	# Summarize surfaced issues to guide improvements
	issues_summary = {"llm_error": 0, "llm_issues": 0}
	for r in runs:
		for e in r.get("variants", []):
			if "llm_error" in e:
				issues_summary["llm_error"] += 1
			if e.get("llm_issues"):
				issues_summary["llm_issues"] += 1

	return {"runs": runs, "summary": issues_summary}


