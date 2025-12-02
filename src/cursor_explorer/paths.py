import os
import sys

# Backward compatibility: Import from agent_explorer if available, otherwise use legacy
try:
    from agent_explorer.backends import get_backend
    _USE_AGENT_BACKEND = True
except ImportError:
    _USE_AGENT_BACKEND = False


def default_db_path(agent_type: str = None) -> str:
    """Return the default agent SQLite DB path.
    
    Supports multiple agents via backend system. Defaults to Cursor for backward compatibility.

    - Respects `CURSOR_STATE_DB` (or agent-specific env var) if set
    - macOS: prefers globalStorage then workspaceStorage
    - Windows: `%APPDATA%/Agent/User/...`
    - Linux: `~/.config/Agent/User/...`
    
    Args:
        agent_type: Agent identifier (e.g., 'cursor', 'cline'). 
                   Defaults to 'cursor' for backward compatibility.
    """
    if _USE_AGENT_BACKEND:
        try:
            backend = get_backend(agent_type)
            return backend.get_db_path()
        except (ValueError, ImportError):
            # Fall back to legacy Cursor implementation
            pass

    # Legacy Cursor-specific implementation (backward compatibility)
    env_override = os.getenv("CURSOR_STATE_DB")
    if env_override:
        return os.path.expanduser(os.path.expandvars(env_override))

    if sys.platform == "darwin":
        # macOS defaults
        darwin_global = os.path.expanduser(
            "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
        )
        darwin_workspace = os.path.expanduser(
            "~/Library/Application Support/Cursor/User/workspaceStorage/state.vscdb"
        )
        if os.path.exists(darwin_global):
            return darwin_global
        if os.path.exists(darwin_workspace):
            return darwin_workspace
        return darwin_global
    if os.name == "nt" or sys.platform.startswith("win"):
        # Windows defaults
        appdata = os.environ.get("APPDATA", "")
        win_global = os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")
        win_workspace = os.path.join(appdata, "Cursor", "User", "workspaceStorage", "state.vscdb")
        if os.path.exists(win_global):
            return win_global
        if os.path.exists(win_workspace):
            return win_workspace
        return win_global
    # Linux / other Unix
    lin_global = os.path.expanduser("~/.config/Cursor/User/globalStorage/state.vscdb")
    lin_workspace = os.path.expanduser("~/.config/Cursor/User/workspaceStorage/state.vscdb")
    if os.path.exists(lin_global):
        return lin_global
    if os.path.exists(lin_workspace):
        return lin_workspace
    return lin_global


def expand_abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))
