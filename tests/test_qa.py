import json
from pathlib import Path


from cursor_explorer import qa as qamod


def _write_jsonl(tmp_path: Path, lines: list[dict | str]) -> Path:
    p = tmp_path / "qa_idx.jsonl"
    out_lines: list[str] = []
    for it in lines:
        if isinstance(it, str):
            out_lines.append(it)
        else:
            out_lines.append(json.dumps(it))
    p.write_text("\n".join(out_lines), encoding="utf-8")
    return p


def test_analyze_index_counts_missing_and_tags_and_avg(tmp_path):
    # include one invalid JSON line, mixed truthy annotation values, and tags
    items = [
        {"user_head": "hello", "assistant_head": "world", "annotations": {"contains_design": True, "tags": ["design", "api"]}},
        {"user_head": "", "assistant_head": "A", "annotations": {"contains_preference": 1, "contains_learning": "yes", "tags": ["api"]}},
        {"user_head": "U2", "assistant_head": "", "annotations": {}},
    ]
    idx = _write_jsonl(tmp_path, [items[0], "not-json", items[1], items[2]])

    res = qamod.analyze_index(str(idx))
    counts = res["counts"]
    # total turns should skip invalid line => 3
    assert counts["turns"] == 3
    # empty head counters
    assert counts["user_head_empty"] == 1
    assert counts["assistant_head_empty"] == 1
    # boolean annotations treat any truthy as true
    assert counts["ann_contains_design"] == 1
    assert counts["ann_contains_preference"] == 1
    assert counts["ann_contains_learning"] == 1
    # missing_keys should count per line where key is absent
    missing = res["missing_keys"]
    # every item contributes missing counts for absent keys
    for k in [
        "contains_design",
        "contains_preference",
        "contains_learning",
        "unfinished_thread",
        "has_useful_output",
    ]:
        assert k in missing
    # tag_counts sorted, with 'api' appearing twice
    assert list(res["tag_counts"].items())[0][0] == "api"
    assert res["tag_counts"]["api"] == 2
    # avg head lengths rounded to 2 decimals
    avg = res["avg_head_len"]
    assert isinstance(avg["user"], float) and isinstance(avg["assistant"], float)


