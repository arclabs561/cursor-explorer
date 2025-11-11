"""Agent backend implementations."""

from agent_explorer.backends.base import AgentBackend
from agent_explorer.backends.cursor import CursorBackend

__all__ = ["AgentBackend", "CursorBackend"]

# Registry of available backends
BACKENDS = {
    "cursor": CursorBackend,
}

def get_backend(agent_type: str = None) -> AgentBackend:
    """Get backend instance for agent type.
    
    Args:
        agent_type: Agent identifier (e.g., 'cursor', 'cline'). 
                   Defaults to 'cursor' for backward compatibility.
    
    Returns:
        AgentBackend instance
    """
    import os
    agent_type = agent_type or os.getenv("AGENT_TYPE", "cursor")
    
    if agent_type not in BACKENDS:
        raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(BACKENDS.keys())}")
    
    return BACKENDS[agent_type]()

