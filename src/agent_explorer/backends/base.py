"""Base class for agent backends."""

import os
from abc import ABC, abstractmethod
from typing import Optional


class AgentBackend(ABC):
    """Abstract base class for AI agent backends.
    
    Each backend provides agent-specific configuration:
    - Database path detection
    - Table names
    - Agent identifier
    """
    
    @abstractmethod
    def get_db_path(self, env_override: Optional[str] = None) -> str:
        """Return path to agent's state database.
        
        Args:
            env_override: Optional environment variable override path
        
        Returns:
            Absolute path to SQLite database file
        """
        pass
    
    @abstractmethod
    def get_table_name(self) -> str:
        """Return name of key-value storage table.
        
        Returns:
            Table name (e.g., 'cursorDiskKV', 'clineDiskKV')
        """
        pass
    
    @abstractmethod
    def get_agent_name(self) -> str:
        """Return agent identifier.
        
        Returns:
            Agent name (e.g., 'cursor', 'cline')
        """
        pass
    
    def get_env_var_name(self) -> str:
        """Return environment variable name for database path override.
        
        Returns:
            Env var name (e.g., 'CURSOR_STATE_DB', 'CLINE_STATE_DB')
        """
        return f"{self.get_agent_name().upper()}_STATE_DB"
    
    def expand_path(self, path: str) -> str:
        """Expand user and environment variables in path.
        
        Args:
            path: Path string that may contain ~ or $VAR
        
        Returns:
            Expanded absolute path
        """
        return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))

