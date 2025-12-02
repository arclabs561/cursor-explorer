
import pytest

from cursor_explorer import toolchat as toolchatmod
from cursor_explorer import index as indexmod


def test_hybrid_merge_prefers_join_by_id(monkeypatch):
    # Prepare stubbed sparse and vector results with overlapping and distinct IDs
    sparse_rows = [
        {"composer_id": "c1", "turn_index": 1, "user_head": "u1", "assistant_head": "a1", "score": 3},
        {"composer_id": "c2", "turn_index": 2, "user_head": "u2", "assistant_head": "a2", "score": 2},
    ]
    vec_rows = [
        {"id": "c1:1", "composer_id": "c1", "turn_index": 1, "user_head": "u1v", "assistant_head": "a1v", "distance": 0.12},
        {"id": "c3:3", "composer_id": "c3", "turn_index": 3, "user_head": "u3", "assistant_head": "a3", "distance": 0.2},
    ]

    monkeypatch.setattr(indexmod, "search_index", lambda p, q, k=8: sparse_rows)
    monkeypatch.setattr(indexmod, "vec_search", lambda db, table, q, top_k=8: vec_rows)

    out = toolchatmod._tool_hybrid_search({"query": "q", "index_jsonl": "x", "db": "y", "k": 5})
    items = out["items"]
    # Expect 3 merged results: c1:1 merged, c2:2 from sparse only, c3:3 from vec only
    ids = {f"{it['composer_id']}:{it['turn_index']}" for it in items}
    assert ids == {"c1:1", "c2:2", "c3:3"}
    # Merged item c1:1 should have both sparse_score and vec_distance
    merged = next(it for it in items if it["composer_id"] == "c1" and it["turn_index"] == 1)
    assert "sparse_score" in merged and "vec_distance" in merged


def test_vec_search_invalid_table_name_raises():
    with pytest.raises(ValueError):
        indexmod.vec_search("/tmp/db.sqlite", "bad;drop", "q", 5)


