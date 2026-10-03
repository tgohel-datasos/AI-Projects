from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import daterange, is_jain, jain_ok, meal_code


ADULT_MEALS = [
    ("Breakfast", "Poha with peanuts and fruit (no onion/garlic)"),
    ("Lunch", "Steamed rice, dal, seasonal sabzi, curd, salad of cucumber/tomato if allowed"),
    ("Dinner", "Roti, mixed vegetable (non-root for Jain), khichdi option"),
]
CHILD_MEALS = [
    ("Breakfast", "Plain porridge or idli with ghee, banana"),
    ("Lunch", "Mild dal-rice, curd, fruit"),
    ("Dinner", "Khichdi, steamed vegetables, milk if tolerated"),
]


class DietitianAgent(BaseAgent):
    agent_id = "dietitian"
    title = "Dietitian Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        if trip.children and not trip.child_ages:
            return self.ok(
                {"status": "needs_input", "days": [], "confidence": 0.6, "rtcco": _rtcco(trip)},
                status="needs_input",
                missing=["child_ages"],
                data_status="UNKNOWN",
            )

        weather = context.get("agent_results", {}).get("weather")
        weather_old = True
        if weather and weather.result.get("forecast_status") in {"FORECAST_AVAILABLE", "LIMITED_FORECAST"}:
            weather_old = weather.result.get("forecast_status") != "FORECAST_AVAILABLE"

        days = []
        failed = []
        for d in daterange(trip.start_date, trip.end_date):
            adult = []
            child = []
            for slot, dish in ADULT_MEALS:
                if is_jain(trip.food_preference) and not jain_ok(dish):
                    failed.append(dish)
                    dish = "Plain steamed rice, moong dal, cucumber salad (Jain-safe replacement)"
                adult.append({"slot": slot, "dish": dish})
            for slot, dish in CHILD_MEALS:
                if is_jain(trip.food_preference) and not jain_ok(dish):
                    failed.append(dish)
                    dish = "Moong khichdi without onion/garlic, banana"
                child.append({"slot": slot, "dish": dish})
            days.append({"date": d.isoformat(), "adults": adult, "children": child})

        confidence = 1.0
        if trip.children and not trip.child_ages:
            confidence -= 0.40
        confidence -= 0.15  # allergies not confirmed
        if weather_old:
            confidence -= 0.20
        if failed:
            confidence -= 0.0  # replacements made
        confidence -= 0.10  # nutrition_estimate not clinical
        confidence = max(0.0, round(confidence, 2))
        status = "ok" if confidence >= 0.70 and len(days) == trip.duration_days else "degraded"

        return self.ok(
            {
                "status": status,
                "rtcco": _rtcco(trip),
                "flight_meal_code": meal_code(trip.food_preference),
                "days": days,
                "confidence": confidence,
                "confidence_reason": "Allergies unconfirmed; nutrition is estimated; weather may be seasonal.",
                "jain_rules": {
                    "applied": is_jain(trip.food_preference),
                    "note": "Vegetarian is not automatically Jain. No onion, garlic, eggs, meat, honey, or root vegetables.",
                },
            },
            status=status,
            data_status="ESTIMATED",
            warnings=["Not medical nutrition therapy. Confirm hotel/airline Jain meal availability."],
            sources=["dietitian_rules"],
        )


def _rtcco(trip: TripRequest) -> dict[str, Any]:
    return {
        "requirement": f"{trip.food_preference} meals for {trip.total_travelers} travelers",
        "target": "Day-wise adult/child meal outline",
        "context": f"{trip.origin} to {trip.destination}, {trip.start_date}–{trip.end_date}",
        "constraints": ["No booking", "No invented hotel menus"],
        "outcome": "JSON meal plan with confidence",
    }
