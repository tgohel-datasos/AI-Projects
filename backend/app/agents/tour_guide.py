from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.data.sightseeing import SIGHTSEEING
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import is_jain
from app.tools.geo import search_pois


class TourGuideAgent(BaseAgent):
    agent_id = "tour_guide"
    title = "Tour Guide Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        key = trip.destination.strip().lower().split(",")[0]
        catalog = SIGHTSEEING.get(key, [])
        warnings = []
        if not catalog:
            try:
                pois = await search_pois(f"tourist attraction {trip.destination}", limit=6)
                catalog = [
                    {"name": p["name"], "family_friendly": True, "outdoor": True, "guide_useful": True, "source": "nominatim"}
                    for p in pois
                ]
            except Exception as exc:  # noqa: BLE001
                warnings.append(str(exc))
                catalog = []

        weather = context.get("agent_results", {}).get("weather")
        rain = False
        if weather:
            rain = bool(weather.result.get("rain_gear_needed"))

        activities = []
        for a in catalog:
            note = "Prefer indoor slots if rain risk is elevated." if rain and a.get("outdoor") else ""
            activities.append(
                {
                    "name": a["name"],
                    "familyFriendly": a.get("family_friendly"),
                    "guideRequired": "Yes" if a.get("guide_useful") else "Optional",
                    "reason": "Cultural / nature interpretation for a large group.",
                    "source": a.get("source", "LLM_RECOMMENDATION"),
                    "weatherNote": note,
                    "entryFee": None,
                    "guideFee": None,
                    "total": None,
                    "currency": trip.currency,
                }
            )

        verified_guides: list[dict[str, Any]] = []
        missing = [
            "Guide names/prices not verified (no authorized tour-guide API configured)",
            "Child ages required for some activity bookings" if trip.children and not trip.child_ages else None,
        ]
        missing = [m for m in missing if m]

        score = 45
        if catalog:
            score += 15
        if verified_guides:
            score += 30
        if rain:
            score -= 5
        score = max(0, min(100, score))
        level = _level(score)

        group = {
            "requiredTravelers": trip.total_travelers,
            "guideCapacity": None,
            "canAccommodate": None,
            "multipleGuidesRequired": True if trip.total_travelers > 10 else None,
        }

        estimated_guide = {
            "guideName": None,
            "provider": None,
            "languages": ["English", "Hindi"],
            "groupCapacity": None,
            "price": None,
            "currency": trip.currency,
            "transportation": "Not Specified",
            "entryTickets": "Not Specified",
            "jainFoodSupport": "REQUIRES_CONFIRMATION" if is_jain(trip.food_preference) else "NOT_REQUESTED",
            "cancellationPolicy": "Cancellation policy not available.",
            "source": "UNAVAILABLE",
            "confidence": {"score": 0, "level": "Unavailable", "reason": "No guide inventory or quote provider is configured."},
        }

        return self.ok(
            {
                "destination": trip.destination,
                "travelDates": {"startDate": trip.start_date.isoformat(), "endDate": trip.end_date.isoformat()},
                "travelers": {"adults": trip.adults, "children": trip.children, "total": trip.total_travelers},
                "tourGuideRequired": "Optional",
                "guidedActivities": activities,
                "tourGuides": verified_guides,
                "estimatedGuidePackage": estimated_guide,
                "groupValidation": group,
                "jainFoodSupport": [{"status": estimated_guide["jainFoodSupport"]}],
                "cancellationPolicy": [{"available": False, "details": "Cancellation policy not available."}],
                "missingInformation": missing,
                "confidence": {
                    "score": score,
                    "level": level,
                    "reason": "Activities are catalog/OSM suggestions; guide inventory is not API-verified.",
                    "verifiedFactors": [],
                    "missingFactors": ["guide availability", "price", "capacity", "cancellation"],
                },
                "finance_line": {
                    "name": "Estimated licensed guide (unverified)",
                    "participants": trip.total_travelers,
                    "entryFee": 0,
                    "guideFee": None,
                    "tax": 0,
                    "total": None,
                    "currency": trip.currency,
                    "type": "unavailable",
                },
            },
            status="partial",
            warnings=warnings
            + ["Guide availability, capacity, and price are unavailable without a provider quote."],
            missing=missing,
            sources=["sightseeing_catalog", "nominatim"],
            data_status="UNVERIFIED",
        )


def _level(score: int) -> str:
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 60:
        return "Medium"
    if score >= 40:
        return "Low"
    return "Very Low"
