import json
from typing import Tuple, Union


ValueType = Union[bytes, str]


def to_text(value: ValueType) -> str:
	if isinstance(value, bytes):
		try:
			return value.decode("utf-8")
		except Exception:
			return value.decode("utf-8", errors="ignore")
	if isinstance(value, str):
		return value
	return str(value)


def pretty_json_or_text(value: ValueType) -> Tuple[str, bool]:
	"""Return a pretty string; second return indicates if JSON parse succeeded."""
	text = to_text(value)
	try:
		obj = json.loads(text)
		return json.dumps(obj, ensure_ascii=False, indent=2), True
	except Exception:
		return text, False


def preview(text: str, max_len: int = 2000) -> str:
	return text if len(text) <= max_len else text[:max_len] + "\n... [truncated]"
