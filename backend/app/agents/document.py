from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest


class DocumentAgent(BaseAgent):
    agent_id = "document"
    title = "Document Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        docs = [
            {
                "document": "Government photo ID (Aadhaar / Passport / Voter ID / Driving licence)",
                "applies_to": "All adult travelers",
                "purpose": "Airline/railway security and hotel check-in",
                "class": "MANDATORY",
                "data_status": "GENERAL_GUIDANCE",
            },
            {
                "document": "Child photo ID / birth certificate / school ID",
                "applies_to": "Children",
                "purpose": "Age verification on flights and hotels",
                "class": "MANDATORY" if trip.children else "IF_APPLICABLE",
                "data_status": "GENERAL_GUIDANCE",
            },
            {
                "document": "Confirmed tickets and hotel voucher (once booked)",
                "applies_to": "All travelers",
                "purpose": "Boarding and check-in",
                "class": "MANDATORY",
                "data_status": "GENERAL_GUIDANCE",
            },
            {
                "document": "Travel insurance policy copy",
                "applies_to": "All travelers",
                "purpose": "Medical/trip disruption claims",
                "class": "RECOMMENDED",
                "data_status": "GENERAL_GUIDANCE",
            },
            {
                "document": "Payment card used for booking + ID",
                "applies_to": "Lead guest",
                "purpose": "Hotel guarantee / no-show policy",
                "class": "RECOMMENDED",
                "data_status": "GENERAL_GUIDANCE",
            },
        ]
        international = False
        o = trip.origin.lower()
        d = trip.destination.lower()
        india_hints = ["india", "ahmedabad", "munnar", "udaipur", "goa", "delhi", "mumbai", "kochi", "kerala", "rajasthan"]
        if not any(h in d for h in india_hints) and "," in trip.destination:
            international = True
        if international:
            docs.append(
                {
                    "document": "Passport with validity + visa if required",
                    "applies_to": "All travelers",
                    "purpose": "Border control — confirm with official sources",
                    "class": "MANDATORY",
                    "data_status": "REQUIRES_VERIFICATION",
                }
            )
        return self.ok(
            {
                "mandatory_documents": [x for x in docs if x["class"] == "MANDATORY"],
                "recommended": [x for x in docs if x["class"] == "RECOMMENDED"],
                "if_applicable": [x for x in docs if x["class"] == "IF_APPLICABLE"],
                "all": docs,
                "missing_or_unclear": [
                    "Traveler nationality (needed for visa rules)",
                    "Whether trip is treated as domestic India",
                ],
                "recommended_next_steps": [
                    "Do not invent visa outcomes. Check official bureau sites before international travel.",
                    "Keep digital and paper copies separate from originals.",
                ],
            },
            data_status="GENERAL_GUIDANCE",
            sources=["document_agent_rules"],
            warnings=["Document rules are general; not legal advice."],
        )
