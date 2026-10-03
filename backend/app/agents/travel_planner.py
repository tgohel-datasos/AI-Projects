from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.data.airports import nearest_airports
from app.schemas import AgentEnvelope, TripRequest
from app.tools.geo import geocode, haversine_km


class TravelPlannerAgent(BaseAgent):
    agent_id = "travel_planner"
    title = "Travel Planner Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        origin = await geocode(trip.origin)
        dest = await geocode(trip.destination)
        missing = []
        if not origin:
            missing.append("origin_geocode")
        if not dest:
            missing.append("destination_geocode")
        if missing:
            return self.ok(
                {"is_trip_possible": False, "feasibility_rationale": "Could not resolve places."},
                status="failed",
                missing=missing,
                errors=["Geocoding failed"],
                data_status="UNKNOWN",
            )

        distance = round(haversine_km(origin["lat"], origin["lon"], dest["lat"], dest["lon"]), 1)
        origin_air = nearest_airports(origin["lat"], origin["lon"], 3)
        dest_air = nearest_airports(dest["lat"], dest["lon"], 3)
        nearest_dest = dest_air[0]
        within = nearest_dest["distance_km"] <= trip.max_airport_distance_km

        possible = True
        reasons = [
            f"Resolved corridor {trip.origin} → {trip.destination} ({distance} km great-circle)."
        ]
        if trip.travel_mode.value == "car" and distance > 2500:
            possible = False
            reasons.append("Road trip distance is unusually long; treat as infeasible without overnight staging.")
        if trip.travel_mode.value == "flight" and not within:
            reasons.append(
                f"Nearest airport {nearest_dest['iata']} is {nearest_dest['distance_km']} km "
                f"(limit {trip.max_airport_distance_km} km). Trip remains possible with multimodal transfer."
            )

        days = []
        for i in range(trip.duration_days):
            days.append(
                {
                    "day": i + 1,
                    "theme": "Travel day" if i in (0, trip.duration_days - 1) else "Sightseeing / rest mix",
                }
            )

        return self.ok(
            {
                "is_trip_possible": possible,
                "feasibility": "YES" if possible else "NO",
                "feasibility_rationale": " ".join(reasons),
                "origin_geo": origin,
                "destination_geo": dest,
                "corridor_distance_km": distance,
                "origin_airports": origin_air,
                "destination_airports": dest_air,
                "itinerary_skeleton": days,
            },
            status="ok",
            sources=["nominatim", "airport_catalog"],
            data_status="VERIFIED_LIVE" if origin and dest else "UNKNOWN",
        )
