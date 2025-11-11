import json
import os

from cursor_explorer import trace as tracemod


def test_trace_writes_jsonl(tmp_path):
	path = tmp_path / "out.jsonl"
	os.environ["LLM_LOG_PATH"] = str(path)
	tracemod.set_context({"app": "test", "env": "ci"})
	tracemod.log_llm_event(
		endpoint="chat.completions",
		model="gpt-5.0-mini",
		request_meta={"temperature": 0.0},
		response_meta={"total_tokens": 10},
		pair={"composer_id": "c1", "turn_index": 1},
		input_text="hello",
		output_text="world",
	)
	assert path.exists()
	lines = path.read_text(encoding="utf-8").strip().splitlines()
	assert len(lines) >= 1
	obj = json.loads(lines[-1])
	assert obj["endpoint"] == "chat.completions"
	assert obj["model"] == "gpt-5.0-mini"
	assert obj["context"]["app"] == "test"

