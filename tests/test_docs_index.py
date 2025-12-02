import json
from pathlib import Path

from cursor_explorer import docs as docmod


def test_index_markdown_dir_basic(tmp_path):
	root = tmp_path / "vault"
	root.mkdir()
	(root / "a.md").write_text("# Title A\nHello world\n", encoding="utf-8")
	(root / "b.markdown").write_text("Second\nBody text\n", encoding="utf-8")
	(root / ".hidden.md").write_text("Hidden\nShould ignore by default\n", encoding="utf-8")

	out = tmp_path / "out.jsonl"
	wrote = docmod.index_markdown_dir(str(root), str(out))
	assert wrote == 2

	lines = out.read_text(encoding="utf-8").strip().splitlines()
	assert len(lines) == 2
	objs = [json.loads(l) for l in lines]
	# verify required fields and shapes
	for o in objs:
		assert o.get("composer_id", "").startswith("doc_")
		assert o.get("turn_index") == 0
		assert isinstance(o.get("user_head"), str) and isinstance(o.get("assistant_head"), str)
		ann = o.get("annotations") or {}
		assert ann.get("kind") == "doc" and isinstance(ann.get("path"), str)
		assert isinstance(o.get("assistant"), str)


def test_create_markdown_note(tmp_path):
	vault = tmp_path / "vault"
	vault.mkdir()
	path = docmod.create_markdown_note(
		root_dir=str(vault),
		title="My Test Note",
		body="Hello\n",
		subdir="inbox",
		tags=["test", "notes"],
		aliases=["Alias1"],
		date_prefix=False,
	)
	text = Path(path).read_text(encoding="utf-8")
	assert text.startswith("---\n") and "title: My Test Note" in text
	assert "Hello\n" in text


