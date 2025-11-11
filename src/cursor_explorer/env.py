from __future__ import annotations


def load_dotenv_if_present() -> None:
	try:
		from dotenv import load_dotenv, find_dotenv  # type: ignore
		import os
		# Project/local .env (auto-discovered)
		path = find_dotenv(usecwd=True)
		load_dotenv(path, override=False)
		# User-level env files (optional)
		home_env_1 = os.path.expanduser("~/.cursor-explorer.env")
		home_env_2 = os.path.expanduser("~/.cursor_explorer.env")
		load_dotenv(home_env_1, override=False)
		load_dotenv(home_env_2, override=False)
	except Exception:
		# Optional dependency; ignore if missing
		return
