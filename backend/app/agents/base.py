from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas import AgentEnvelope, TripRequest


class BaseAgent(ABC):
    agent_id: str
    title: str

    @abstractmethod
    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        raise NotImplementedError

    def ok(
        self,
        result: dict[str, Any],
        *,
        status: str = "ok",
        warnings: list[str] | None = None,
        missing: list[str] | None = None,
        sources: list[str] | None = None,
        data_status: str = "ESTIMATED",
        errors: list[str] | None = None,
    ) -> AgentEnvelope:
        return AgentEnvelope(
            agent=self.agent_id,
            status=status,
            result=result,
            warnings=warnings or [],
            missing_information=missing or [],
            errors=errors or [],
            sources=sources or [],
            data_status=data_status,
        )
