from __future__ import annotations

from typing import Any

from app.schemas import AgentEnvelope, TripRequest

DEFAULT_AGENTS = [
    "validator",
    "travel_planner",
    "weather",
    "transportation",
    "hotel",
    "tour_guide",
    "health",
    "dietitian",
    "document",
    "insurance",
    "fashion_designer",
    "finance",
]

# Sequential groups; agents inside a group may run in parallel.
PIPELINE: list[tuple[str, list[str], str]] = [
    ("stage0_input", ["validator"], "sequential"),
    ("stage1_feasibility", ["travel_planner"], "sequential"),
    ("stage1b_weather", ["weather"], "sequential"),
    ("stage2_logistics", ["transportation", "hotel", "tour_guide"], "parallel"),
    ("stage3_advisory", ["health", "dietitian", "document", "insurance"], "parallel"),
    ("stage3b_style", ["fashion_designer"], "sequential"),
    ("stage4_finance", ["finance"], "sequential"),
    ("stage5_audit", ["validator"], "sequential"),
]


def select_agents(trip: TripRequest) -> list[str]:
    chosen = list(DEFAULT_AGENTS)
    if trip.include_agents:
        allow = set(trip.include_agents) | {"validator", "travel_planner"}
        chosen = [a for a in chosen if a in allow]
    if trip.exclude_agents:
        deny = set(trip.exclude_agents) - {"validator", "travel_planner"}
        chosen = [a for a in chosen if a not in deny]
    return chosen


def pipeline_for(selected: list[str]) -> list[tuple[str, list[str], str]]:
    out = []
    used_validator_audit = False
    for stage, agents, mode in PIPELINE:
        subset = [a for a in agents if a in selected]
        if stage == "stage5_audit":
            if "validator" in selected:
                subset = ["validator"]
                used_validator_audit = True
            else:
                subset = []
        if stage == "stage0_input":
            subset = ["validator"] if "validator" in selected else []
        if subset:
            out.append((stage, subset, mode))
    return out


def combine_plan(trip: TripRequest, results: dict[str, AgentEnvelope]) -> dict[str, Any]:
    planner = results.get("travel_planner")
    weather = results.get("weather")
    transport = results.get("transportation")
    hotel = results.get("hotel")
    tour = results.get("tour_guide")
    finance = results.get("finance")
    validator = None
    # last validator is audit if present twice — stored as validator_audit in runner
    audit = results.get("validator_audit") or results.get("validator")
    feasible = True
    rationale = ""
    if planner:
        feasible = bool(planner.result.get("is_trip_possible", True))
        rationale = planner.result.get("feasibility_rationale", "")

    return {
        "trip_status": {
            "is_possible": feasible,
            "feasibility_note": rationale,
        },
        "validation_summary": (audit.result if audit else {}),
        "route_overview": trip.public_dict(),
        "weather_and_climate": weather.result if weather else {},
        "transport_details": transport.result if transport else {},
        "hotel_details": hotel.result if hotel else {},
        "sightseeing_and_guide": tour.result if tour else {},
        "lifestyle_and_safety_advisories": {
            "recommended_wardrobe": (results.get("fashion_designer").result if results.get("fashion_designer") else {}),
            "mandatory_documents": (results.get("document").result if results.get("document") else {}),
            "health_and_wellness": (results.get("health").result if results.get("health") else {}),
            "meals": (results.get("dietitian").result if results.get("dietitian") else {}),
        },
        "insurance_details": results.get("insurance").result if results.get("insurance") else {},
        "costing_and_discounts": finance.result if finance else {},
        "agent_statuses": {k: v.status for k, v in results.items()},
    }
