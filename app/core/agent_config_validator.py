"""Agent config validators based on agent role."""

from typing import Any

from app.schemas.agent_role import AgentRole


class AgentConfigValidator:
    """Validators for agent configs based on role."""

    @staticmethod
    def validate_orchestrator_config(config: dict[str, Any]) -> bool:
        """Validate orchestrator agent config.

        Required fields:
        - metadata.role = "orchestrator"
        - metadata.capabilities (list of strings)
        - metadata.cost_per_call (float)
        - model (string)
        - temperature (float)

        Optional fields:
        - metadata.max_parallel_agents (int)
        - metadata.approval_threshold_cost (float)
        - metadata.approval_threshold_tasks (int)

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is missing required fields
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")

        metadata = config["metadata"]

        if metadata.get("role") != AgentRole.ORCHESTRATOR.value:
            raise ValueError("Config role must be 'orchestrator'")

        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")

        if "model" not in config:
            raise ValueError("Missing 'model' in config")

        if "temperature" not in config:
            raise ValueError("Missing 'temperature' in config")

        return True

    @staticmethod
    def validate_code_agent_config(config: dict[str, Any]) -> bool:
        """Validate code agent config.

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is missing required fields
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")

        metadata = config["metadata"]

        if metadata.get("role") != AgentRole.CODE.value:
            raise ValueError("Config role must be 'code'")

        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")

        if "model" not in config:
            raise ValueError("Missing 'model' in config")

        return True

    @staticmethod
    def validate_architect_agent_config(config: dict[str, Any]) -> bool:
        """Validate architect agent config.

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is missing required fields
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")

        metadata = config["metadata"]

        if metadata.get("role") != AgentRole.ARCHITECT.value:
            raise ValueError("Config role must be 'architect'")

        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")

        if "model" not in config:
            raise ValueError("Missing 'model' in config")

        return True

    @staticmethod
    def validate_ask_agent_config(config: dict[str, Any]) -> bool:
        """Validate ask agent config.

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is missing required fields
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")

        metadata = config["metadata"]

        if metadata.get("role") != AgentRole.ASK.value:
            raise ValueError("Config role must be 'ask'")

        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")

        if "model" not in config:
            raise ValueError("Missing 'model' in config")

        return True

    @staticmethod
    def validate_debug_agent_config(config: dict[str, Any]) -> bool:
        """Validate debug agent config.

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is missing required fields
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")

        metadata = config["metadata"]

        if metadata.get("role") != AgentRole.DEBUG.value:
            raise ValueError("Config role must be 'debug'")

        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")

        if "model" not in config:
            raise ValueError("Missing 'model' in config")

        return True

    @staticmethod
    def validate_agent_config_by_role(config: dict[str, Any]) -> bool:
        """Validate agent config based on its role.

        Args:
            config: Agent configuration dictionary

        Returns:
            True if config is valid

        Raises:
            ValueError: If config is invalid for its role
        """
        role = config.get("metadata", {}).get("role")

        if role == AgentRole.ORCHESTRATOR.value:
            return AgentConfigValidator.validate_orchestrator_config(config)
        elif role == AgentRole.CODE.value:
            return AgentConfigValidator.validate_code_agent_config(config)
        elif role == AgentRole.ARCHITECT.value:
            return AgentConfigValidator.validate_architect_agent_config(config)
        elif role == AgentRole.ASK.value:
            return AgentConfigValidator.validate_ask_agent_config(config)
        elif role == AgentRole.DEBUG.value:
            return AgentConfigValidator.validate_debug_agent_config(config)
        elif role == AgentRole.CUSTOM.value:
            # Custom roles pass validation by default
            return True
        else:
            raise ValueError(f"Unknown agent role: {role}")
