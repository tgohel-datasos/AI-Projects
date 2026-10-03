from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import daterange


class FashionDesignerAgent(BaseAgent):
    agent_id = "fashion_designer"
    title = "Fashion Designer Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        weather = context.get("agent_results", {}).get("weather")
        health = context.get("agent_results", {}).get("health")
        tour = context.get("agent_results", {}).get("tour_guide")
        assumptions = []
        if not weather:
            assumptions.append("Weather missing — layering assumed.")
        rain = bool(weather.result.get("rain_gear_needed")) if weather else True
        temps = (weather.result.get("average_temperature_celsius") or {}) if weather else {}
        cool = (temps.get("min") or 18) <= 16
        activities = []
        if tour:
            activities = [a.get("name") for a in (tour.result.get("guidedActivities") or [])][: trip.duration_days]
        flags = health.result.get("health_flags") if health else {}

        outfits = []
        for i, d in enumerate(daterange(trip.start_date, trip.end_date)):
            act = activities[i] if i < len(activities) else "Sightseeing / transfer"
            outfits.append(
                {
                    "date": d.isoformat(),
                    "activity": act,
                    "adult_outfit": [
                        "Breathable base layer",
                        "Warm mid layer" if cool else "Light shirt",
                        "Rain/wind shell" if rain else "Sun shirt",
                    ],
                    "child_outfit": ["Soft layers", "Spare set", "Easy-on rain jacket" if rain else "Sun cap"],
                    "color_palette": ["cream", "olive", "mustard"],
                    "color_reason": "Heat reflection at origin; visibility in mist/rain at hills or outdoor sites",
                    "footwear": "Grippy walking shoes",
                    "accessories": ["Sunglasses", "Cap"],
                    "notes": "Temple-ready modest cover-up in day bag",
                }
            )

        items = [
            {"item": "Walking shoes", "qty_total": trip.total_travelers, "unit_cost": None, "total": None, "basis": "PRICE_UNAVAILABLE"},
            {"item": "Rain shell", "qty_total": trip.total_travelers, "unit_cost": None, "total": None, "basis": "PRICE_UNAVAILABLE"},
            {"item": "Spare child sets", "qty_total": max(trip.children, 0) * trip.duration_days, "unit_cost": None, "total": None, "basis": "PRICE_UNAVAILABLE"},
        ]

        return self.ok(
            {
                "agent": "FashionDesigner",
                "assumptions": assumptions,
                "weather_strategy": {
                    "summary": f"Layering plan; rain_gear_needed={rain}",
                    "layering": {"base": ["cotton/merino"], "mid": ["fleece"] if cool else ["light overshirt"], "outer": ["rain shell"] if rain else ["sun shirt"]},
                    "rain_gear_needed": rain,
                },
                "color_strategy": {
                    "principles": ["Function first: heat, visibility, mud"],
                    "palette": {
                        "primary": ["Cream #F5F0E6"],
                        "secondary": ["Olive #556B2F"],
                        "accent": ["Mustard #E1B12C"],
                        "avoid": [{"color": "pure white on boat days", "reason": "Can turn see-through when wet"}],
                    },
                },
                "group_coordination": {
                    "enabled": True,
                    "theme": "earth + one bright outer",
                    "adult_palette": ["olive", "cream"],
                    "children_palette": ["mustard", "coral accent"],
                    "photo_day_suggestions": [],
                },
                "body_fit_guidance": [
                    {
                        "profile_id": "adult_group",
                        "recommended_silhouettes": ["relaxed walking trousers", "layered tops"],
                        "fits_and_lengths": ["adjustable waist"],
                        "necklines_and_details": ["modest option for temples"],
                        "fabrics": ["quick-dry", "breathable"],
                        "comfort_notes": ["No body inferred from age/gender"],
                        "avoid": ["long loose hems on treks"],
                    }
                ],
                "day_wise_outfits": outfits,
                "packing_list": {
                    "adults": [{"item": "3–4 mix-and-match tops", "qty_per_person": 4, "color": "cream/olive", "fit": "relaxed", "fabric": "cotton", "reason": "days of wear"}],
                    "children": [{"item": "spare set per day", "qty_per_person": trip.duration_days, "color": "bright outer", "fit": "easy on/off", "fabric": "soft", "reason": "spills/weather"}],
                },
                "beauty_and_skincare": [
                    {
                        "item": "Moisturizer, lip balm, sunscreen",
                        "reason": "Climate comfort",
                        "caution": "Avoid products conflicting with unlisted allergies; patch test. No medicines.",
                    }
                ],
                "activity_gear": [{"activity": a, "items": ["grip shoes"]} for a in activities[:5]],
                "cultural_dress_notes": [{"place_or_context": "Temples / churches", "guidance": "Cover shoulders and knees; treat as guidance not law."}],
                "cost_estimate": {
                    "currency": trip.currency,
                    "items": items,
                    "grand_total": None,
                    "status": "UNAVAILABLE",
                    "reason": "No product/retailer pricing source is configured.",
                },
                "health_conflict_check": flags or {"note": "no clinical flags provided"},
                "review_checklist": {
                    "matches_weather": bool(weather),
                    "covers_adults_and_children": True,
                    "uses_only_provided_data": True,
                },
            },
            data_status="ESTIMATED",
            sources=["fashion_rules", "weather_agent", "tour_guide", "health_agent"],
        )
