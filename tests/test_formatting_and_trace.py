from cursor_explorer import formatting as fmt
from cursor_explorer import trace as tracemod


def test_pretty_and_preview_and_to_text():
    text, is_json = fmt.pretty_json_or_text(b'{"a":1}')
    assert is_json and '"a"' in text
    t2, is_json2 = fmt.pretty_json_or_text(b'invalid')
    assert not is_json2 and t2 == 'invalid'
    assert fmt.preview('x' * 5, max_len=10) == 'xxxxx'
    assert fmt.preview('x' * 15, max_len=10).endswith('... [truncated]')
    assert fmt.to_text(b'hi') == 'hi'


def test_trace_flags_and_counters(tmp_path, monkeypatch):
    path = tmp_path / 'trace.jsonl'
    monkeypatch.setenv('LLM_LOG_PATH', str(path))
    # disable output preview but keep input
    monkeypatch.setenv('LLM_LOG_INPUT', '1')
    monkeypatch.setenv('LLM_LOG_OUTPUT', '0')
    tracemod.set_context({'x': 'y'})
    tracemod.log_llm_event(
        endpoint='chat.completions',
        model='m',
        request_meta={},
        response_meta={'total_tokens': 3, 'prompt_tokens': 1, 'completion_tokens': 2},
        input_text='input',
        output_text='output',
    )
    assert path.exists()
    # counters updated
    summary = tracemod.get_run_summary()
    assert summary['events'] >= 1 and summary['tokens']['total'] >= 3
    # generic event increments too
    tracemod.log_event('custom', {'a': 1})
    assert tracemod.get_run_summary()['events'] >= 2


