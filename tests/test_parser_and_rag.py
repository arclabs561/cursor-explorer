from cursor_explorer import parser as parsermod
from cursor_explorer import rag as ragmod


def test_coalesce_and_pairs_basic():
    messages = [
        {"composer_id": "c1", "role": "user", "text": "Hello"},
        {"composer_id": "c1", "role": "assistant", "text": "Hi"},
        {"composer_id": "c1", "role": "assistant", "text": "How can I help?"},
        {"composer_id": "c1", "role": "user", "text": "Do X"},
        {"composer_id": "c1", "role": "assistant", "text": "Done"},
    ]
    co = parsermod.coalesce_assistant_runs(messages)
    # consecutive assistant merges into one
    assert sum(1 for m in co if m["role"] == "assistant") == 2
    pairs = parsermod.build_qa_pairs(messages)
    assert len(pairs) == 2
    assert pairs[0]["assistant"].startswith("Hi") and "How can I help?" in pairs[0]["assistant"]
    assert pairs[0]["turn_index"] == 0
    assert pairs[1]["turn_index"] == 1


def test_build_turn_items_and_search_scoring():
    messages = [
        {"composer_id": "c2", "role": "user", "text": "Discuss API design for service"},
        {"composer_id": "c2", "role": "assistant", "text": "We can define a simple contract"},
    ]
    items = ragmod.build_turn_items(messages)
    assert len(items) == 1
    it = items[0]
    assert it["composer_id"] == "c2" and it["turn_index"] == 0
    # _score/token overlap and tag boost paths exercised by search_items
    hits = ragmod.search_items(items, "api design", k=5)
    assert hits and hits[0]["composer_id"] == "c2"


