from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest


class FinanceAgent(BaseAgent):
    agent_id = "finance"
    title = "Finance Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        results = context.get("agent_results", {})
        lines: list[dict[str, Any]] = []
        warnings: list[str] = []
        assumptions: list[str] = []
        sources_state = {}
        missing_quotes: list[str] = []

        transport = results.get("transportation")
        sources_state["travel"] = "received" if transport else "missing"
        if transport:
            sel = transport.result.get("selected_option") or {}
            if sel.get("total"):
                lines.append(_line("Flights", sel.get("mode", "Transport"), sel["total"], sel.get("tax_per_passenger", 0) * trip.total_travelers, 0.5, "transportation", "estimate"))
            else:
                warnings.append("Transport quote unavailable")
                if "transportation" not in trip.exclude_agents:
                    missing_quotes.append("transportation")
            transfer = transport.result.get("airport_transfer") or {}
            if transfer.get("total"):
                lines.append(_line("Local transportation", transfer.get("description", "Transfer"), transfer["total"], 0, 0.5, "transportation", "estimate"))
            elif trip.travel_mode.value == "flight" and "transportation" not in trip.exclude_agents:
                warnings.append("Airport transfer quote unavailable")
        else:
            warnings.append("Missing transportation data")
            if "transportation" not in trip.exclude_agents:
                missing_quotes.append("transportation")

        hotel = results.get("hotel")
        sources_state["hotel"] = "received" if hotel else "missing"
        selected_hotel = None
        if hotel:
            selected_hotel = hotel.result.get("selected")
            if selected_hotel:
                p = selected_hotel.get("pricing") or {}
                if p.get("totalCost") is not None:
                    lines.append(_line("Hotel", selected_hotel.get("name", "Stay"), p["totalCost"], p.get("taxes") or 0, 0.5, "hotel", "estimate"))
                else:
                    warnings.append("Hotel quote unavailable")
                    if "hotel" not in trip.exclude_agents:
                        missing_quotes.append("hotel")
            else:
                warnings.append("Hotel cost unavailable")
                if "hotel" not in trip.exclude_agents:
                    missing_quotes.append("hotel")
        else:
            warnings.append("Missing hotel data")
            if "hotel" not in trip.exclude_agents:
                missing_quotes.append("hotel")

        tour = results.get("tour_guide")
        sources_state["tourGuide"] = "received" if tour else "missing"
        if tour:
            fl = tour.result.get("finance_line") or {}
            if fl.get("total"):
                lines.append(_line("Tour/activities", fl.get("name", "Guide"), fl["total"], fl.get("tax") or 0, 0.4, "tour_guide", "estimate"))
            else:
                warnings.append("Tour/guide quote unavailable; optional costs are excluded")

        ins = results.get("insurance")
        sources_state["insurance"] = "received" if ins else "missing"
        if ins:
            sel = ins.result.get("selected") or {}
            prem = (sel.get("premium") or {}).get("amount")
            if prem is not None:
                lines.append(_line("Insurance", sel.get("plan_name", "Policy"), prem, 0, 0.4, "insurance", "estimate"))
            elif "insurance" not in trip.exclude_agents:
                warnings.append("Insurance quote unavailable")
                missing_quotes.append("insurance")
        elif "insurance" not in trip.exclude_agents:
            warnings.append("Insurance quote unavailable")
            missing_quotes.append("insurance")

        fashion = results.get("fashion_designer")
        if fashion:
            ce = fashion.result.get("cost_estimate") or {}
            if ce.get("grand_total"):
                lines.append(_line("Other approved trip expenses", "Clothing/gear estimates", ce["grand_total"], 0, 0.4, "fashion", "estimate"))
                assumptions.append("Clothing costs are optional estimates, not bookings.")

        sources_state["weather"] = "received" if results.get("weather") else "missing"

        base = sum(float(x["baseAmount"]) for x in lines)
        taxes = sum(float(x["tax"] or 0) for x in lines)
        discount = 0.0
        known_subtotal = round(base + taxes - discount, 2) if lines else None
        grand = known_subtotal if not missing_quotes and known_subtotal is not None else None
        per = round(grand / trip.total_travelers, 2) if grand is not None and trip.total_travelers else None

        budget_status = "unknown"
        saving = []
        if trip.budget_max is not None and grand is not None:
            if grand <= trip.budget_max:
                budget_status = "near_limit" if trip.budget_max - grand < 0.08 * trip.budget_max else "within"
            else:
                budget_status = "over"
                saving.append(
                    {
                        "suggestion": "Consider a lower hotel category if the user agrees",
                        "estimatedSaving": None,
                        "tradeoff": "Changes stay quality; does not silently alter the request",
                        "source": "finance_rule",
                    }
                )

        offers: list[dict[str, Any]] = []
        if trip.payment_method.value == "Credit Card":
            warnings.append("CARD_DETAILS_REQUIRED — no bank/card given, so no discount applied.")

        cancel_items = []
        if selected_hotel:
            quoted_amount = (selected_hotel.get("pricing") or {}).get("totalCost")
            amt = float(quoted_amount) if quoted_amount is not None else None
            pol = selected_hotel.get("cancellation") or {}
            refundability = "unconfirmed" if pol.get("status") == "UNVERIFIED" else "confirmed"
            cancel_items.append(
                {
                    "item": selected_hotel.get("name"),
                    "bookingAmount": amt,
                    "refundability": refundability,
                    "freeCancelTill": pol.get("deadline"),
                    "refundPercent": None,
                    "potentialLoss": amt,
                    "chargeAfter": "UNKNOWN",
                    "source": "hotel",
                }
            )

        weighted_num = sum(float(x["total"]) * float(x["confidence"]) for x in lines) if lines else 0
        weighted_den = sum(float(x["total"]) for x in lines) or 1
        overall = round(weighted_num / weighted_den, 2)
        decision = "present" if overall >= 0.85 else "present_with_warnings" if overall >= 0.70 else "needs_user_check"

        status = "ok"
        if "Missing hotel data" in warnings or "Missing transportation data" in warnings:
            status = "partial"
        if missing_quotes:
            status = "partial"

        return self.ok(
            {
                "agent": "finance",
                "version": "4",
                "status": status,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "currency": trip.currency,
                "tripSummary": {
                    "adults": trip.adults,
                    "children": trip.children,
                    "totalTravelers": trip.total_travelers,
                    "days": trip.duration_days,
                    "nights": trip.duration_nights,
                    "rooms": trip.required_rooms,
                },
                "costBreakdown": lines,
                "totals": {
                    "baseCost": round(base, 2) if lines else None,
                    "taxes": round(taxes, 2) if lines else None,
                    "discountApplied": discount,
                    "grandTotal": grand,
                    "knownSubtotal": known_subtotal,
                    "pricingStatus": "complete" if grand is not None else "incomplete",
                    "missingQuotes": sorted(set(missing_quotes)),
                    "perTraveler": per,
                    "perAdult": None,
                    "perChild": None,
                    "perRoom": round(grand / trip.required_rooms, 2) if grand is not None and trip.required_rooms else None,
                },
                "budgetCheck": {
                    "budgetMin": trip.budget_min,
                    "budgetMax": trip.budget_max,
                    "currency": trip.currency,
                    "status": budget_status,
                    "difference": round(trip.budget_max - grand, 2) if trip.budget_max is not None and grand is not None else None,
                    "savingOptions": saving,
                },
                "offers": offers,
                "offerStatus": "NOT_CONFIGURED",
                "paymentPlan": {
                    "method": trip.payment_method.value,
                    "payOnline": [{"item": x["category"], "amount": x["total"], "whenToPay": "Not provided"} for x in lines],
                    "payInCash": [],
                    "emiOptions": [],
                    "bookingSequence": ["Flight", "Hotel", "Vehicle", "Tour"],
                },
                "cancellation": {
                    "required": trip.hotel_cancellation_required,
                    "items": cancel_items,
                    "totalFinancialExposure": sum(i["bookingAmount"] for i in cancel_items) if cancel_items and all(i["bookingAmount"] is not None for i in cancel_items) else None,
                    "financialRisk": "Hotel refundability unconfirmed" if cancel_items else "",
                },
                "financialRisks": [
                    {"risk": w, "impact": "Totals may change at booking", "severity": "high" if "unconfirmed" in w.lower() or "unavailable" in w.lower() else "medium", "action": "Verify before booking"}
                    for w in warnings[:8]
                ],
                "confidence": {
                    "overall": overall,
                    "bySection": {"flights": 0.5, "hotels": 0.5, "transport": 0.5, "tours": 0.4, "insurance": 0.4, "offers": 0.0, "cancellation": 0.4},
                    "decision": decision,
                },
                "warnings": warnings,
                "assumptions": assumptions,
                "errors": [],
                "agentSources": sources_state,
                "trace": {"iterations": 1, "toolCalls": 0},
                "verifyBeforeBooking": True,
            },
            status=status,
            warnings=warnings,
            data_status="ESTIMATED",
            sources=["upstream_agents", "calculator"],
        )


def _line(category: str, description: str, total: float, tax: float, conf: float, source: str, typ: str) -> dict[str, Any]:
    tax = float(tax or 0)
    total = float(total or 0)
    base = max(total - tax, 0)
    return {
        "category": category,
        "description": description,
        "unitPrice": None,
        "quantity": None,
        "baseAmount": base,
        "tax": tax,
        "discount": 0,
        "total": total,
        "type": typ,
        "source": source,
        "fetchedAt": None,
        "confidence": conf,
    }
