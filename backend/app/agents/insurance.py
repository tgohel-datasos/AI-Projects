from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest


class InsuranceAgent(BaseAgent):
    agent_id = "insurance"
    title = "Travel Insurance Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        return self.ok(
            {
                "status": "NO_PROVIDER_QUOTES",
                "trip": {
                    "destination": trip.destination,
                    "start_date": trip.start_date.isoformat(),
                    "end_date": trip.end_date.isoformat(),
                    "duration_days": trip.duration_days,
                },
                "insurance_options": [],
                "selected": None,
                "warnings": [
                    "No insurer quote provider is configured; do not treat catalog rates or invented coverage as available policies.",
                    "Confirm eligibility, exclusions, coverage limits, and cancellation cover directly with a licensed insurer.",
                ],
                "sources": [],
            },
            status="no_data",
            warnings=["Insurance availability and premium are unavailable without an insurer quote."],
            missing=["insurance_provider_quote"],
            data_status="UNKNOWN",
            sources=[],
        )
