import json
import sqlite3
from pathlib import Path

from cursor_explorer import index as indexmod
from cursor_explorer import toolchat as toolchatmod


def _write_jsonl(tmp_path: Path, items):
    p = tmp_path / "idx.jsonl"
    p.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
    return p


def test_sample_and_search_index(tmp_path):
    items = [
        {"composer_id": "c1", "turn_index": 1, "user": "api design", "assistant": "good", "user_head": "api", "assistant_head": "good", "annotations": {"tags": ["design"]}},
        {"composer_id": "c2", "turn_index": 2, "user": "code block", "assistant": "```bash\necho\n```", "user_head": "code", "assistant_head": "bash", "annotations": {"has_useful_output": True}},
    ]
    idx = _write_jsonl(tmp_path, items)
    # sample
    s = indexmod.sample_index(str(idx), 1)
    assert len(s) == 1 and s[0]["composer_id"] in {"c1", "c2"}
    # sparse search should find both
    hits = indexmod.search_index(str(idx), "api code design", k=5)
    ids = {(h.get("composer_id"), h.get("turn_index")) for h in hits}
    assert ("c1", 1) in ids and ("c2", 2) in ids


def test_tool_schemas_and_basic_handlers(tmp_path, monkeypatch):
    # schema contains expected tools
    names = {s["function"]["name"] for s in toolchatmod.get_tools_schema()}
    assert {"annotations_search", "sparse_search", "vec_db_search", "hybrid_search", "index_jsonl", "vec_db_index", "list_chats", "cat_chat", "fuzz_seeds"}.issubset(names)

    # build a tiny index jsonl
    items = [
        {"composer_id": "c1", "turn_index": 1, "user": "prompt injection", "assistant": "", "user_head": "prompt injection", "assistant_head": "", "annotations": {}},
        {"composer_id": "c2", "turn_index": 2, "user": "code block", "assistant": "", "user_head": "code block", "assistant_head": "", "annotations": {}},
    ]
    idx = _write_jsonl(tmp_path, items)

    # sparse tool direct
    out = toolchatmod._tool_sparse_search({"index_jsonl": str(idx), "query": "code prompt", "k": 3})
    assert out["items"] and len(out["items"]) >= 1

    # annotations_search in sparse mode
    out2 = toolchatmod._tool_annotations_search({"mode": "sparse", "index_jsonl": str(idx), "query": "prompt"})
    assert out2["mode"] == "sparse" and out2["items"]

    # list_chats/cat_chat against a temp sqlite with minimal structure
    dbp = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(dbp))
    cur = conn.cursor()
    cur.execute("CREATE TABLE cursorDiskKV(key TEXT PRIMARY KEY, value BLOB)")
    # composerData with headers referencing two bubbles
    composer_json = (
        '{"title":"T","fullConversationHeadersOnly":[{"bubbleId":"bid1","type":1,"serverBubbleId":0},{"bubbleId":"bid2","type":2,"serverBubbleId":0}]}'
    ).encode("utf-8")
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", ("composerData:cid1", composer_json))
    # bubbles content
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", ("bubbleId:cid1:bid1", b'{"text":"hello"}'))
    cur.execute("INSERT INTO cursorDiskKV(key, value) VALUES(?, ?)", ("bubbleId:cid1:bid2", b'{"text":"world"}'))
    conn.commit()
    conn.close()

    # list_chats should show cid1 title
    listing = toolchatmod._tool_list_chats({"db": str(dbp), "limit": 5})
    assert any(it.get("composer_id") == "cid1" for it in listing.get("items", []))
    # cat_chat pairs
    cat = toolchatmod._tool_cat_chat({"db": str(dbp), "composer_id": "cid1", "mode": "pairs", "offset": 0, "limit": 2})
    assert cat["mode"] == "pairs" and cat["items"] and cat["items"][0]["user_head"]
    # cat_chat messages
    catm = toolchatmod._tool_cat_chat({"db": str(dbp), "composer_id": "cid1", "mode": "messages", "offset": 0, "limit": 2})
    assert catm["mode"] == "messages" and len(catm["items"]) == 2


