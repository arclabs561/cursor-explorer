"""Cursor agent backend implementation."""

import os
import sys
from typing import Optional
from agent_explorer.backends.base import AgentBackend


class CursorBackend(AgentBackend):
    """Backend for Cursor AI agent."""
    
    def get_db_path(self, env_override: Optional[str] = None) -> str:
        """Return the default Cursor SQLite DB path.
        
        - Respects `CURSOR_STATE_DB` if set
        - macOS: prefers globalStorage then workspaceStorage
        - Windows: `%APPDATA%/Cursor/User/...`
        - Linux: `~/.config/Cursor/User/...`
        """
        env_var = self.get_env_var_name()
        override = env_override or os.getenv(env_var)
        if override:
            return self.expand_path(override)
        
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
    
    def get_table_name(self) -> str:
        """Return Cursor's key-value table name."""
        return "cursorDiskKV"
    
    def get_agent_name(self) -> str:
        """Return agent identifier."""
        return "cursor"

