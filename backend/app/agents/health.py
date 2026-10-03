from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest


class HealthAgent(BaseAgent):
    agent_id = "health"
    title = "Health Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        weather = context.get("agent_results", {}).get("weather")
        forecast_status = "FORECAST_NOT_AVAILABLE"
        rain = False
        if weather:
            forecast_status = weather.result.get("forecast_status", forecast_status)
            rain = bool(weather.result.get("rain_gear_needed"))

        tour = context.get("agent_results", {}).get("tour_guide")
        activities = []
        if tour:
            for a in tour.result.get("guidedActivities") or []:
                activities.append(
                    {
                        "activity": a.get("name"),
                        "preparation": ["Hydration", "Comfortable footwear", "Rest breaks for children"],
                        "safety_considerations": ["Uneven terrain possible", "CONSULT_HEALTHCARE_PROFESSIONAL for individual fitness"],
                        "child_considerations": ["Shorter walking blocks"] if trip.children else [],
                        "data_status": "GENERAL_GUIDANCE",
                    }
                )

        missing = []
        if trip.children and not trip.child_ages:
            missing.append("Children ages (REQUIRES_USER_INPUT for age-specific kit items)")

        kit = [
            {"category": "Hygiene", "item": "Hand sanitizer", "purpose": "Hand hygiene", "priority": "RECOMMENDED", "notes": ""},
            {"category": "Wound care", "item": "Basic first-aid supplies", "purpose": "Minor cuts", "priority": "RECOMMENDED", "notes": ""},
            {"category": "Hydration", "item": "Oral rehydration supplies", "purpose": "Fluid replacement", "priority": "RECOMMENDED", "notes": "Not a treatment plan"},
            {"category": "Sun/rain", "item": "Sunscreen and rain protection", "purpose": "Weather exposure", "priority": "RECOMMENDED", "notes": ""},
            {"category": "Personal", "item": "Personally prescribed medicines", "purpose": "Continuity of care", "priority": "REQUIRED", "notes": "Do not share; no dosages provided"},
        ]
        if rain:
            kit.append({"category": "Weather", "item": "Waterproof layer", "purpose": "Stay dry", "priority": "RECOMMENDED", "notes": ""})

        return self.ok(
            {
                "agent_name": "HealthAgent",
                "input_validation": {"status": "ok" if not missing else "NEEDS_MORE_INFORMATION", "missing_information": missing, "assumptions": []},
                "health_summary": {
                    "overall_status": "GENERAL_GUIDANCE",
                    "travel_health_preparedness": "Standard domestic travel precautions; not a medical opinion.",
                    "notes": ["This agent is not a doctor and does not diagnose or prescribe."],
                },
                "health_flags": {
                    "allergies": "not_provided",
                    "sensitive_skin": "not_provided",
                    "children_traveling": trip.children > 0,
                },
                "traveler_considerations": {
                    "adults": {"traveler_count": trip.adults, "considerations": ["Hydration", "Movement on long transfers", "Sleep"]},
                    "children": {"traveler_count": trip.children, "considerations": ["Rest breaks", "Snacks", "Weather protection"]},
                },
                "travel_mode_health_preparation": {
                    "mode": trip.travel_mode.value,
                    "preparation": ["Hydration", "Stretch during long sits"],
                    "data_status": "GENERAL_GUIDANCE",
                },
                "destination_health_preparation": {
                    "destination": trip.destination,
                    "considerations": ["Outdoor exposure", "Food and water hygiene"],
                    "data_status": "GENERAL_GUIDANCE",
                },
                "weather_based_preparation": {
                    "forecast_status": forecast_status,
                    "recommended_preparation": ["Layers", "Rain protection"] if rain else ["Sun protection", "Hydration"],
                },
                "activity_based_preparation": activities,
                "medical_kit": kit,
                "food_and_hydration": {
                    "food_preference": trip.food_preference,
                    "general_guidance": ["Keep dietary consistency; dietitian owns menus"],
                    "food_safety": ["Prefer sealed water; avoid assuming street food safety"],
                },
                "insurance_coordination": {"items_to_verify": ["Medical emergency", "Hospitalization", "Assistance"], "coordination_required": True},
                "identified_risks": [
                    {
                        "risk": "Travel fatigue for a large group",
                        "severity": "MEDIUM",
                        "reason": f"{trip.total_travelers} travelers including {trip.children} children",
                        "prevention": ["Buffer time", "Rest days"],
                        "data_status": "GENERAL_GUIDANCE",
                    }
                ],
                "professional_consultation": {
                    "recommended_when": ["Existing conditions", "Medications", "Pregnancy", "Disability/mobility needs"],
                    "general_note": "For personalized medical advice, consult a qualified healthcare professional.",
                },
                "handoff_to_orchestrator": {
                    "critical_findings": [],
                    "user_decisions_required": missing,
                },
            },
            status="ok" if not missing else "needs_input",
            missing=missing,
            data_status="GENERAL_GUIDANCE",
            sources=["health_agent_rules"],
        )
