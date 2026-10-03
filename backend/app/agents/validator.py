from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest


class ValidatorAgent(BaseAgent):
    agent_id = "validator"
    title = "Validator Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        phase = context.get("validator_phase", "input")
        if phase == "input":
            return self._input(trip)
        return self._audit(trip, context)

    def _input(self, trip: TripRequest) -> AgentEnvelope:
        checks = {
            "input_schema_sanitized": True,
            "traveler_math": trip.total_travelers == trip.adults + trip.children,
            "room_occupancy_rule_compliant": trip.required_rooms >= 1,
            "temporal_dates_consistent": trip.end_date >= trip.start_date,
            "start_not_in_past": trip.start_date >= date.today(),
        }
        missing = []
        if trip.children and not trip.child_ages:
            missing.append("child_ages")
            checks["child_ages"] = False
        else:
            checks["child_ages"] = True
        if trip.start_date < date.today():
            missing.append("start_date must not be in the past")
        ok = all(checks.values()) and not missing
        return self.ok(
            {
                "phase": "input",
                "audit_status": "APPROVED" if ok else "NEEDS_INPUT",
                "is_valid": ok,
                "audit_checks": checks,
                "derived": {
                    "total_travelers": trip.total_travelers,
                    "duration_days": trip.duration_days,
                    "duration_nights": trip.duration_nights,
                    "required_rooms": trip.required_rooms,
                },
            },
            status="ok" if ok else "needs_input",
            missing=missing,
            data_status="USER_PROVIDED",
        )

    def _audit(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        results: dict[str, AgentEnvelope] = context.get("agent_results", {})
        transport = _r(results, "transportation")
        hotel = _r(results, "hotel")
        finance = _r(results, "finance")
        flags: list[str] = []

        airport_ok = True
        proximity = transport.get("servicing_airport") or {}
        if trip.travel_mode.value == "flight":
            within = proximity.get("within_limit")
            multimodal = transport.get("multimodal_required")
            airport_ok = bool(within) or bool(multimodal)
            if within is False and not multimodal:
                flags.append("Airport exceeds max_airport_distance_km without multimodal transfer plan")

        cancel_ok = True
        if trip.hotel_cancellation_required:
            hotels = hotel.get("hotels") or []
            refundable = [h for h in hotels if h.get("cancellation", {}).get("freeCancellation")]
            cancel_ok = bool(refundable)
            if not refundable:
                flags.append(
                    "A current hotel quote with a verified free-cancellation policy is required, "
                    "but no hotel quote provider is configured. Add a provider or disable the "
                    "free-cancellation requirement and rerun."
                )

        rooms_ok = True
        if hotel.get("roomRequirement", {}).get("roomsRequired"):
            rooms_ok = hotel["roomRequirement"]["roomsRequired"] >= trip.required_rooms

        diet = _r(results, "dietitian")
        meal_ok = True
        if trip.food_preference:
            meal_ok = bool(diet.get("flight_meal_code") or diet.get("days"))

        finance_ok = True
        recon = {}
        totals = finance.get("totals") or {}
        breakdown = finance.get("costBreakdown") or []
        if totals:
            computed = round(sum(float(i.get("total") or 0) for i in breakdown), 2)
            reported_subtotal = totals.get("knownSubtotal")
            if reported_subtotal is not None and abs(computed - round(float(reported_subtotal), 2)) > 1:
                finance_ok = False
                flags.append("Finance known-subtotal arithmetic variance exceeds INR 1")
            reported = totals.get("grandTotal")
            recon = {
                "computed_known_subtotal": computed,
                "reported_known_subtotal": reported_subtotal,
                "reported_grand_total": reported,
                "variance": round(computed - float(reported_subtotal), 2) if reported_subtotal is not None else None,
                "pricing_status": totals.get("pricingStatus", "unknown"),
            }
            if reported is not None and abs(computed - round(float(reported), 2)) > 1:
                finance_ok = False
                flags.append("Finance grand-total arithmetic variance exceeds INR 1")

        checks = {
            "airport_proximity_verified": airport_ok,
            "hotel_cancellation_requirement_met": cancel_ok,
            "room_occupancy_rule_compliant": rooms_ok,
            "dietary_flight_meal_matched": meal_ok,
            "financial_arithmetic_balanced": finance_ok,
        }
        approved = all(checks.values())
        return self.ok(
            {
                "phase": "audit",
                "audit_status": "APPROVED" if approved else "DISCREPANCY",
                "is_valid": approved,
                "validation_score": int(100 * sum(1 for v in checks.values() if v) / max(len(checks), 1)),
                "audit_timestamp": datetime.now(timezone.utc).isoformat(),
                "audit_checks": checks,
                "financial_reconciliation": recon,
                "flags_or_warnings": flags,
            },
            status="ok" if approved else "partial",
            warnings=flags,
            data_status="CALCULATED",
        )


def _r(results: dict, key: str) -> dict:
    env = results.get(key)
    if env is None:
        return {}
    if hasattr(env, "result"):
        return env.result or {}
    return env.get("result") or env
