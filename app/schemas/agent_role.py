"""Agent role enumeration."""

from enum import Enum


class AgentRole(str, Enum):
    """Agent role in the system.

    Each agent in the system has a specific role that determines:
    - What it can do (capabilities)
    - How it's selected for tasks (routing)
    - How it's configured (config schema)

    Attributes:
        ARCHITECT: Creates plans and analyzes requirements
        ORCHESTRATOR: Routes messages and coordinates task execution
        CODE: Writes and modifies code
        ASK: Answers questions and explains concepts
        DEBUG: Investigates errors and adds logging
        CUSTOM: Custom agent with user-defined role
    """

    ARCHITECT = "architect"
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    ASK = "ask"
    DEBUG = "debug"
    CUSTOM = "custom"
