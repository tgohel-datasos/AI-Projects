from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import is_jain
from app.tools.geo import search_pois


class HotelAgent(BaseAgent):
    agent_id = "hotel"
    title = "Hotel Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        warnings = [
            "No hotel booking/quote provider is configured. OpenStreetMap results are location candidates only; category, availability, price, Jain food, and cancellation terms are unverified."
        ]
        pois: list[dict[str, Any]] = []
        try:
            pois = await search_pois(f"hotel {trip.destination}", limit=8)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Hotel POI search failed: {exc}")

        nights = trip.duration_nights
        rooms = trip.required_rooms
        hotels = []
        for i, p in enumerate(pois[:6] or [{"name": f"{trip.hotel_category} stay near {trip.destination}", "lat": None, "lon": None}]):
            hotels.append(
                {
                    "hotelId": f"osm-{i}",
                    "name": p.get("name"),
                    "category": trip.hotel_category,
                    "category_verification": "UNVERIFIED",
                    "rating": {"value": None, "status": "UNKNOWN"},
                    "availability": {"available": None, "status": "UNKNOWN"},
                    "room": {"type": "Standard occupancy", "rooms": rooms, "occupancy": trip.room_occupancy},
                    "pricing": {
                        "pricePerNight": None,
                        "nights": nights,
                        "roomCost": None,
                        "taxes": None,
                        "fees": None,
                        "totalCost": None,
                        "currency": trip.currency,
                        "status": "UNAVAILABLE",
                        "reason": "A hotel quote provider is required for a current rate.",
                    },
                    "breakfast": {"included": None},
                    "amenities": [],
                    "jain_food": {
                        "status": "REQUIRES_CONFIRMATION" if is_jain(trip.food_preference) else "NOT_REQUESTED",
                        "note": "Vegetarian is not automatically Jain.",
                    },
                    "cancellation": {
                        "available": None,
                        "freeCancellation": None,
                        "deadline": None,
                        "cancellationFee": None,
                        "refund": "UNKNOWN",
                        "status": "UNVERIFIED",
                    },
                    "location": {
                        "address": p.get("full_name"),
                        "lat": p.get("lat"),
                        "lon": p.get("lon"),
                    },
                    "constraints": {
                        "categorySatisfied": None,
                        "budgetSatisfied": None,
                        "occupancySatisfied": True,
                        "cancellationSatisfied": None,
                        "amenitiesSatisfied": False,
                    },
                    "source": p.get("source", "estimate"),
                }
            )

        hotel_budget = trip.budget_max
        est = hotels[0]["pricing"]["totalCost"] if hotels else None
        status = "PARTIAL" if hotels else "NO_DATA"
        return self.ok(
            {
                "status": status,
                "searchCriteria": {
                    "destination": trip.destination,
                    "checkIn": trip.start_date.isoformat(),
                    "checkOut": trip.end_date.isoformat(),
                    "nights": nights,
                    "adults": trip.adults,
                    "children": trip.child_ages,
                },
                "roomRequirement": {
                    "roomsRequired": rooms,
                    "reason": f"ceil({trip.total_travelers}/{trip.room_occupancy})",
                },
                "hotels": hotels,
                "budgetAnalysis": {
                    "hotelBudget": hotel_budget,
                    "estimatedHotelCost": est,
                    "withinBudget": None if est is None or hotel_budget is None else est <= hotel_budget,
                },
                "selected": hotels[0] if hotels else None,
            },
            status="partial" if hotels else "no_data",
            warnings=warnings,
            sources=["nominatim"],
            data_status="ESTIMATED",
        )
