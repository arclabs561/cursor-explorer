
import sqlite3

from cursor_explorer import parser as parsermod


def _mk_conn():
    # in-memory DB; we'll stub kv_value via connection cursor monkeypatching in tests that need it
    return sqlite3.connect(":memory:")


def test_parse_json_handles_invalid_and_bytes():
    assert parsermod.parse_json(b"{\"a\":1}") == {"a": 1}
    assert parsermod.parse_json("not-json") is None


def test_list_composer_ids_filters_prefix(monkeypatch):
    calls = {"ran": False}

    def fake_composer_data_keys(conn, limit=10000):  # type: ignore
        calls["ran"] = True
        return [
            "composerData:cid1",
            "misc:foo",
            "composerData:cid2",
            "composerData:",
            "composerData:0",
        ]

    monkeypatch.setattr("cursor_explorer.db.composer_data_keys", fake_composer_data_keys)
    conn = _mk_conn()
    ids = parsermod.list_composer_ids(conn)
    assert calls["ran"] and ids == ["cid1", "cid2", "0"]


def test_reconstruct_conversation_fallbacks_and_roles(monkeypatch):
    # Provide composer with two bubbles; second bubble has content under 'content' field; skip missing bubble
    composer = {
        "fullConversationHeadersOnly": [
            {"bubbleId": "b1", "type": 1, "serverBubbleId": 0},
            {"bubbleId": "b2", "type": 2, "serverBubbleId": 1},
            {"bubbleId": "missing", "type": 2, "serverBubbleId": 2},
        ]
    }

    def fake_kv_value(conn, key):  # type: ignore
        if key == "composerData:cid":
            import json

            return json.dumps(composer).encode("utf-8")
        if key == "bubbleId:cid:b1":
            return b'{"text":"hello"}'
        if key == "bubbleId:cid:b2":
            return b'{"content":"world"}'
        return None

    monkeypatch.setattr("cursor_explorer.db.kv_value", fake_kv_value)
    conn = _mk_conn()
    msgs = parsermod.reconstruct_conversation(conn, "cid")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user" and msgs[0]["text"] == "hello"
    assert msgs[1]["role"] == "assistant" and msgs[1]["text"] == "world"
    # server_bubble_id preserved
    assert msgs[0]["server_bubble_id"] == 0
    assert msgs[1]["server_bubble_id"] == 1


def test_coalesce_and_pairs_edge_cases():
    # assistant-first; empty assistant should be dropped; trailing assistant merged and finalized
    messages = [
        {"composer_id": "c", "role": "assistant", "text": ""},
        {"composer_id": "c", "role": "assistant", "text": "A1"},
        {"composer_id": "c", "role": "assistant", "text": "A2"},
        {"composer_id": "c", "role": "user", "text": "U1"},
        {"composer_id": "c", "role": "assistant", "text": "A3"},
        {"composer_id": "c", "role": "assistant", "text": "A4"},
    ]
    co = parsermod.coalesce_assistant_runs(messages)
    # first empty assistant dropped; first two assistants merged
    assert sum(1 for m in co if m["role"] == "assistant") == 2
    assert "A1" in co[0]["text"] and "A2" in co[0]["text"]

    pairs = parsermod.build_qa_pairs(messages)
    # since conversation starts with assistant, first pair has empty user
    assert pairs[0]["user"] == ""
    # trailing assistants merged into the last pair
    assert pairs[-1]["assistant"].endswith("A4")


