from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.data.airports import nearest_airports
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import meal_code


class TransportationAgent(BaseAgent):
    agent_id = "transportation"
    title = "Transportation Provider Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        planner = context.get("agent_results", {}).get("travel_planner")
        origin = planner.result.get("origin_geo") if planner else None
        dest = planner.result.get("destination_geo") if planner else None
        if not origin or not dest:
            return self.ok({}, status="failed", missing=["origin_geo", "destination_geo"])

        origin_air = nearest_airports(origin["lat"], origin["lon"], 1)[0]
        dest_air = nearest_airports(dest["lat"], dest["lon"], 3)
        nearest = dest_air[0]
        within = nearest["distance_km"] <= trip.max_airport_distance_km
        warnings = [
            "No authorized transport inventory/quote provider is configured. This is a route suggestion, not a confirmed schedule, fare, or booking."
        ]

        options: list[dict[str, Any]] = []
        if trip.travel_mode.value in {"flight", "multi"}:
            pax = trip.total_travelers
            options.append(
                {
                    "mode": "FLIGHT",
                    "provider": "catalog_estimate",
                    "data_status": "ESTIMATED",
                    "airline": "Indicative domestic carrier",
                    "flight_number": None,
                    "origin_airport": origin_air["iata"],
                    "destination_airport": nearest["iata"],
                    "departure_date": trip.start_date.isoformat(),
                    "return_date": trip.end_date.isoformat(),
                    "duration": None,
                    "meals_booking_available": None,
                    "recommended_meal_code": meal_code(trip.food_preference),
                    "base_fare_per_passenger": None,
                    "tax_per_passenger": None,
                    "total": None,
                    "pricing_status": "UNAVAILABLE",
                    "currency": trip.currency,
                    "cancellation": {"available": None, "details": "Fare rules require provider confirmation"},
                }
            )

        if trip.travel_mode.value in {"train", "multi", "flight"}:
            options.append(
                {
                    "mode": "TRAIN",
                    "provider": "catalog_estimate",
                    "data_status": "ESTIMATED",
                    "origin_city": trip.origin,
                    "destination_city": trip.destination,
                    "route_summary": f"{trip.origin} → {trip.destination}; city-level route only, stations and connections are not verified.",
                    "notes": "Train number, boarding/alighting stations, timetable, class availability, and fare are not available without an authorized Indian Railways data provider.",
                    "fare_status": "UNAVAILABLE",
                    "schedule_status": "UNAVAILABLE",
                    "official_search_url": "https://www.irctc.co.in/nget/train-search",
                    "total": None,
                    "currency": trip.currency,
                }
            )

        if trip.travel_mode.value == "car":
            hours = round((planner.result.get("corridor_distance_km") or 0) / 50, 1)
            options.append(
                {
                    "mode": "CAR",
                    "provider": "self_drive_or_hire_estimate",
                    "data_status": "ESTIMATED",
                    "distance_km": planner.result.get("corridor_distance_km"),
                    "duration_hours_estimate": hours,
                    "total": None,
                }
            )

        transfer_km = nearest["distance_km"]
        multimodal = trip.travel_mode.value == "flight" and not within

        result = {
            "transport_mode": trip.travel_mode.value,
            "transport_available": None,
            "inventory_status": "UNVERIFIED",
            "api_status": "NO_FREE_PUBLIC_API_CONFIRMED",
            "provider_summary": {
                "make_my_trip": {"api_status": "NOT_CONFIGURED"},
                "goibibo": {"api_status": "NOT_CONFIGURED"},
            },
            "proximity_clause_applied": trip.travel_mode.value == "flight",
            "servicing_airport": {
                "name": nearest["name"],
                "iata": nearest["iata"],
                "distance_to_destination_km": nearest["distance_km"],
                "within_limit": within,
                "limit_km": trip.max_airport_distance_km,
            },
            "alternate_airports": dest_air,
            "multimodal_required": multimodal,
            "airport_transfer": {
                "description": f"Road transfer {nearest['iata']} → {trip.destination}",
                "distance_km": transfer_km,
                "total": None,
                "currency": trip.currency,
                "data_status": "UNAVAILABLE",
                "reason": "A local transfer quote provider is required for current pricing.",
            },
            "options": options,
            "selected_option": options[0] if options else {},
            "vehicle_rental": {
                "needed_for_local": True,
                "capacity_hint": trip.total_travelers,
                "data_status": "UNVERIFIED",
            },
        }
        if multimodal:
            warnings.append(
                f"No airport within {trip.max_airport_distance_km} km of {trip.destination}. "
                f"Nearest is {nearest['iata']} at {nearest['distance_km']} km."
            )
        return self.ok(result, status="partial", warnings=warnings, sources=["airport_catalog"], data_status="ESTIMATED")
