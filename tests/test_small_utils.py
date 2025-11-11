import os
from pathlib import Path

from cursor_explorer import prompts as promptmod
from cursor_explorer import env as envmod
import llm_cache as cache


def test_prompts_load_and_render(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("Hello {{ name }}!", encoding="utf-8")
    template = promptmod.load_prompt(str(p))
    out = promptmod.render_prompt(template, {"name": "World"})
    assert out == "Hello World!"


def test_env_load_dotenv_if_present_noop():
    # Should not raise even if python-dotenv is not installed in env
    envmod.load_dotenv_if_present()


def test_llm_cache_roundtrip_and_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_PATH", str(tmp_path / "cache.sqlite"))
    cache.clear()
    key = "k1"
    cache.set(key, "{\"a\":1}", prompt_tokens=1, completion_tokens=2, total_tokens=3)
    assert cache.get(key) == "{\"a\":1}"
    meta = cache.get_meta(key)
    assert meta and meta["prompt_tokens"] == 1 and meta["total_tokens"] == 3
    assert cache.count() >= 1
    cache.clear()
    assert cache.count() == 0


