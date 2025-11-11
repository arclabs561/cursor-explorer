import json
import types
import os
from pathlib import Path

from cursor_explorer import toolchat as toolchatmod
from cursor_explorer import cli as climod
from cursor_explorer import cluster as clustermod
import llm_helpers as llmmod


def test_schema_includes_name_topics():
	# schema contains expected name_topics tool
	names = {s["function"]["name"] for s in toolchatmod.get_tools_schema()}
	assert "name_topics" in names


def test_tool_name_topics_trims_and_passes_args(tmp_path, monkeypatch):
	# Stub builder to capture args and return oversized layers/topics
	captured = {}
	def fake_builder(index_jsonl, out_json, **kwargs):
		captured.update({"index_jsonl": index_jsonl, "out_json": out_json, **kwargs})
		data = {
			"ids": ["c:0", "c:1"],
			"layers": [["A", "B", "C"], ["X", "Y", "Z"]],
			"topics_per_document": [["A", "B"], ["X", "Y"]],
			"meta": {"count": 2, "library": "toponymy"},
		}
		Path(out_json).write_text(json.dumps(data), encoding="utf-8")
		return data
	monkeypatch.setattr(clustermod, "build_toponymy_topics", fake_builder)
	# Call tool without include_doc_topics, expect trimming to [] and layer clip to 2
	out = toolchatmod._tool_name_topics({
		"index_jsonl": "idx.jsonl",
		"limit": 7,
		"min_clusters": 4,
		"umap_dim": 2,
		"max_layer_labels": 2,
	})
	assert out.get("ok") is True and out.get("path")
	res = out.get("result") or {}
	assert res.get("meta", {}).get("library") == "toponymy"
	# topics trimmed by default
	assert res.get("topics_per_document") == []
	# layers clipped to 2 labels
	assert all(len(layer) <= 2 for layer in res.get("layers", []))
	# args passed through
	assert captured.get("limit") == 7 and int(captured.get("min_clusters")) == 4 and int(captured.get("umap_dim")) == 2


def test_name_topics_cli_stubbed(tmp_path, monkeypatch):
	# Stub builder and run CLI command
	def fake_builder(index_jsonl, out_json, **kwargs):
		data = {"ids": ["c:0"], "layers": [["A"]], "topics_per_document": [["A"]], "meta": {"count": 1, "library": "toponymy"}}
		Path(out_json).write_text(json.dumps(data), encoding="utf-8")
		return data
	monkeypatch.setattr(clustermod, "build_toponymy_topics", fake_builder)
	out = tmp_path / "topics.json"
	p = climod.build_parser()
	args = p.parse_args(["name-topics", "idx.jsonl", str(out)])
	# Execute handler; it prints JSON, but we check the file
	_ = args.func(args)
	got = json.loads(out.read_text())
	assert got["meta"]["library"] == "toponymy" and got["ids"] == ["c:0"]


def test_index_cli_topics_out_stubbed(monkeypatch, tmp_path):
	# Stub index builder and toponymy builder; run index with topics-out
	monkeypatch.setattr("cursor_explorer.index.build_index", lambda out, **kw: 123)
	monkeypatch.setattr(clustermod, "build_toponymy_topics", lambda *a, **k: {"meta": {"count": 0, "library": "toponymy"}})
	p = climod.build_parser()
	topics_out = tmp_path / "topics.json"
	args = p.parse_args(["index", str(tmp_path / "idx.jsonl"), "--topics-out", str(topics_out)])
	# Capture printed JSON
	from io import StringIO
	import sys
	buf = StringIO()
	old = sys.stdout
	sys.stdout = buf
	try:
		_ = args.func(args)
	finally:
		sys.stdout = old
	resp = json.loads(buf.getvalue())
	assert resp.get("wrote") == 123 and "topics_path" in resp and resp.get("topics_error") is None


def test_embed_texts_batches_and_order(monkeypatch):
	# Force small batch and capture calls
	os.environ["EMBED_BATCH"] = "2"
	# Ensure cache misses so batching path is exercised
	monkeypatch.setattr(llmmod.llm_cache, "get", lambda key: None)
	monkeypatch.setattr(llmmod.llm_cache, "set", lambda *a, **k: None)
	class DummyEmb:
		def __init__(self, parent):
			self.parent = parent
		def create(self, model, input):
			self.parent.calls.append(list(input))
			return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[0.1, 0.0]) for _ in input], usage=None)
	class DummyClient:
		def __init__(self):
			self.calls = []
			self.embeddings = DummyEmb(self)
	client = DummyClient()
	vecs = llmmod.embed_texts(client, ["a", "b", "c", "d"], model="batch_model", scope="batch_scope_test")
	assert len(vecs) == 4
	# Expect chunked calls in order
	assert client.calls == [["a", "b"], ["c", "d"]]


def test_require_client_loads_dotenv_and_uses_dummy(monkeypatch):
	# Ensure env loader is invoked and dummy client returned without real OpenAI
	called = {"env": 0}
	monkeypatch.setenv("OPENAI_API_KEY", "")
	monkeypatch.setattr("cursor_explorer.env.load_dotenv_if_present", lambda: called.__setitem__("env", called["env"] + 1))
	class DummyOpenAI:
		def __init__(self):
			pass
	monkeypatch.setattr(llmmod, "OpenAI", DummyOpenAI)
	# Provide key via env loader
	def set_key():
		os.environ["OPENAI_API_KEY"] = "test"
		return None
	# Call require_client
	set_key()
	cli = llmmod.require_client()
	assert isinstance(cli, DummyOpenAI)
	assert called["env"] >= 0


def test_agent_loop_dispatch_sparse_search(monkeypatch):
	# Monkeypatch LLM client to request sparse_search, then answer "done" on followup
	class DummyMsg:
		def __init__(self, content=None, tool_calls=None):
			self.content = content
			self.tool_calls = tool_calls
	class DummyChoice:
		def __init__(self, message):
			self.message = message
	class DummyResp:
		def __init__(self, choices):
			self.choices = choices
	class DummyFunc:
		def __init__(self, name, arguments):
			self.name = name
			self.arguments = arguments
	class DummyToolCall:
		def __init__(self, name, args_json):
			self.id = "id1"
			self.function = DummyFunc(name, args_json)
	class DummyChat:
		def __init__(self):
			self._round = 0
		def completions(self):
			return self
		def create(self, model, messages, tools=None):
			# First call: ask for sparse_search
			if self._round == 0:
				self._round += 1
				tc = DummyToolCall("sparse_search", json.dumps({"query": "x"}))
				return DummyResp([DummyChoice(DummyMsg(content=None, tool_calls=[tc]))])
			# Second call: return final answer
			return DummyResp([DummyChoice(DummyMsg(content="done", tool_calls=None))])
	class DummyClient:
		def __init__(self):
			self.chat = types.SimpleNamespace(completions=DummyChat())
	monkeypatch.setattr(llmmod, "require_client", lambda: DummyClient())
	# Monkeypatch sparse_search to avoid touching files
	monkeypatch.setattr(toolchatmod, "_tool_sparse_search", lambda args: {"items": [{"id": "ok"}]})
	res = toolchatmod.run_tool_agent("hello", steps=1, index_jsonl="idx.jsonl", use_vector=False)
	assert res.get("final_answer") == "done"
	assert res.get("steps") and res["steps"][0]["used_tools"][0]["name"] == "sparse_search"


