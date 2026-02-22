"""Orchestrator router for intelligent agent routing based on capabilities."""

import json
from uuid import UUID
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_helpers import get_agents_by_role
from app.schemas.agent_role import AgentRole
from app.schemas.event import StreamEvent, StreamEventType
from app.models.user_agent import UserAgent


class OrchestratorRouter:
    """Routes messages to the best agent based on capability matching."""

    # Keywords mapping for capability extraction
    CAPABILITY_KEYWORDS = {
        "debug": [
            "отладь", "баг", "ошибка", "debug", "error", "fix", "исправь",
            "почему не работает", "что не так", "trace", "stack",
        ],
        "implement_feature": [
            "напиши", "создай", "реализуй", "implement", "write", "code",
            "функция", "метод", "class", "модуль", "generate",
        ],
        "explain": [
            "объясни", "что такое", "как работает", "explain", "describe",
            "расскажи", "понимаю", "help me understand", "tell me",
        ],
        "design": [
            "дизайн", "архитектура", "план", "design", "architecture",
            "structure", "как лучше", "предложи решение",
        ],
        "test": [
            "тест", "test", "unit test", "integration test", "проверь",
            "валидируй", "validate",
        ],
    }

    async def route_message(
        self,
        db: AsyncSession,
        user_id: UUID,
        project_id: UUID,
        user_message: str,
    ) -> dict:
        """Route message to best agent based on capabilities.

        Analyzes the user message to determine required capabilities,
        fetches all available agents, and selects the one with the best
        capability match.

        Args:
            db: Database session
            user_id: User ID
            project_id: Project ID
            user_message: User's message text

        Returns:
            Dictionary with routing decision:
                {
                    "selected_agent_id": UUID,
                    "agent_name": str,
                    "routing_score": float (0.0-1.0),
                    "required_capabilities": list[str],
                    "matched_capabilities": list[str],
                    "confidence": "high" | "medium" | "low"
                }

        Example:
            decision = await router.route_message(
                db, user_id, project_id, "Отладь баг в auth.py"
            )
            if decision["confidence"] == "high":
                # Route to selected agent
        """
        # Extract required capabilities from message
        required_capabilities = self._extract_required_capabilities(user_message)

        # Fetch all ready agents for the project
        agents = []
        for role in AgentRole:
            role_agents = await get_agents_by_role(
                db, project_id, role, status="ready", user_id=user_id
            )
            agents.extend(role_agents)

        if not agents:
            raise ValueError(
                f"No ready agents found for project {project_id}"
            )

        # Calculate routing scores
        best_agent: Optional[UserAgent] = None
        best_score: float = 0.0
        best_matched: list[str] = []

        for agent in agents:
            agent_capabilities = (
                agent.config.get("metadata", {}).get("capabilities", [])
            )

            # Calculate overlap score
            score, matched = self._calculate_routing_score(
                required_capabilities, agent_capabilities
            )

            if score > best_score:
                best_score = score
                best_agent = agent
                best_matched = matched

        if not best_agent:
            raise ValueError("No suitable agent found for message")

        # Determine confidence level
        confidence = self._determine_confidence(
            best_score, len(required_capabilities)
        )

        return {
            "selected_agent_id": best_agent.id,
            "agent_name": best_agent.name,
            "agent_role": best_agent.config.get("metadata", {}).get("role"),
            "routing_score": round(best_score, 3),
            "required_capabilities": required_capabilities,
            "matched_capabilities": best_matched,
            "confidence": confidence,
        }

    def _extract_required_capabilities(self, message: str) -> list[str]:
        """Extract required capabilities from user message.

        Uses simple heuristics based on keyword matching to determine
        what capabilities are needed for the message.

        Args:
            message: User message text

        Returns:
            List of required capability names
        """
        message_lower = message.lower()
        found_capabilities = set()

        for capability, keywords in self.CAPABILITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    found_capabilities.add(capability)
                    break

        # If no specific capabilities found, default to general ones
        if not found_capabilities:
            found_capabilities.add("explain")

        return sorted(list(found_capabilities))

    @staticmethod
    def _calculate_routing_score(
        required: list[str], available: list[str]
    ) -> tuple[float, list[str]]:
        """Calculate overlap score between required and available capabilities.

        Args:
            required: List of required capabilities
            available: List of agent's available capabilities

        Returns:
            Tuple of (score, matched_capabilities)
        """
        if not required:
            return 1.0, []

        matched = [cap for cap in required if cap in available]

        if not matched:
            score = 0.3
        else:
            score = len(matched) / len(required)

        return score, matched

    @staticmethod
    def _determine_confidence(
        score: float, required_count: int
    ) -> str:
        """Determine confidence level based on score.

        Args:
            score: Routing score (0.0-1.0)
            required_count: Number of required capabilities

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        else:
            return "low"

    @staticmethod
    def format_routing_decision(decision: dict) -> str:
        """Format routing decision for logging/display.

        Args:
            decision: Routing decision dictionary

        Returns:
            Formatted string representation
        """
        return json.dumps(decision, indent=2, default=str)

    @staticmethod
    def create_agent_switched_event(
        session_id: UUID,
        selected_agent_id: UUID,
        agent_name: str,
        agent_role: str,
        routing_score: float,
        required_capabilities: list[str],
        matched_capabilities: list[str],
        confidence: str,
    ) -> StreamEvent:
        """Create a SSE event for agent switching/selection.

        This event is sent to notify the client that the orchestrator
        has selected a different agent for message processing.

        Args:
            session_id: Chat session ID
            selected_agent_id: ID of selected agent
            agent_name: Name of selected agent
            agent_role: Role of selected agent
            routing_score: Routing confidence score (0.0-1.0)
            required_capabilities: Capabilities required for the message
            matched_capabilities: Capabilities matched in selected agent
            confidence: Confidence level (high/medium/low)

        Returns:
            StreamEvent ready to be broadcast

        Example:
            event = OrchestratorRouter.create_agent_switched_event(
                session_id=session_id,
                selected_agent_id=agent.id,
                agent_name="Architect",
                agent_role="architect",
                routing_score=0.95,
                required_capabilities=["design", "plan"],
                matched_capabilities=["design"],
                confidence="high"
            )
        """
        return StreamEvent(
            event_type=StreamEventType.AGENT_SWITCHED,
            session_id=session_id,
            payload={
                "selected_agent_id": str(selected_agent_id),
                "agent_name": agent_name,
                "agent_role": agent_role,
                "routing_score": round(routing_score, 3),
                "confidence": confidence,
                "required_capabilities": required_capabilities,
                "matched_capabilities": matched_capabilities,
                "match_percentage": round((len(matched_capabilities) / len(required_capabilities) * 100) if required_capabilities else 0, 1),
            }
        )

