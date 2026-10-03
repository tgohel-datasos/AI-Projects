from datetime import date

from app.agents.finance import FinanceAgent
from app.agents.validator import ValidatorAgent
from app.schemas import TripRequest


def _trip(**kwargs):
    data = dict(
        origin="Ahmedabad",
        destination="Munnar",
        adults=12,
        children=2,
        child_ages=[6, 9],
        start_date=date(2026, 11, 8),
        end_date=date(2026, 11, 15),
        budget_min=300000,
        budget_max=500000,
    )
    data.update(kwargs)
    return TripRequest(**data)


async def test_rooms_and_duration():
    t = _trip()
    assert t.total_travelers == 14
    assert t.duration_nights == 7
    assert t.duration_days == 8
    assert t.required_rooms == 7


async def test_trip_derived_values_change_with_request():
    t = _trip(
        origin="Ahmedabad",
        destination="Udaipur",
        adults=3,
        children=1,
        child_ages=[7],
        start_date=date(2026, 10, 4),
        end_date=date(2026, 10, 7),
    )
    assert t.total_travelers == 4
    assert t.duration_nights == 3
    assert t.duration_days == 4
    assert t.required_rooms == 2


async def test_validator_child_ages():
    t = _trip()
    env = await ValidatorAgent().run(t, {"validator_phase": "input"})
    assert env.status == "ok"


async def test_audit_explains_required_unverified_cancellation():
    from app.schemas import AgentEnvelope

    t = _trip()
    results = {
        "transportation": AgentEnvelope(
            agent="transportation", status="ok", result={"servicing_airport": {"within_limit": True}}
        ),
        "hotel": AgentEnvelope(
            agent="hotel", status="partial", result={"hotels": [{"cancellation": {"freeCancellation": None}}]}
        ),
        "dietitian": AgentEnvelope(agent="dietitian", status="ok", result={"days": [{"meals": []}]}),
        "finance": AgentEnvelope(
            agent="finance", status="partial", result={"totals": {"knownSubtotal": 0}, "costBreakdown": []}
        ),
    }

    env = await ValidatorAgent().run(t, {"validator_phase": "audit", "agent_results": results})

    assert env.result["is_valid"] is False
    assert env.result["audit_checks"]["hotel_cancellation_requirement_met"] is False
    assert "no hotel quote provider is configured" in env.result["flags_or_warnings"][0]


async def test_audit_allows_unknown_cancellation_when_not_required():
    from app.schemas import AgentEnvelope

    t = _trip(hotel_cancellation_required=False)
    results = {
        "transportation": AgentEnvelope(
            agent="transportation", status="ok", result={"servicing_airport": {"within_limit": True}}
        ),
        "hotel": AgentEnvelope(
            agent="hotel", status="partial", result={"hotels": [{"cancellation": {"freeCancellation": None}}]}
        ),
        "dietitian": AgentEnvelope(agent="dietitian", status="ok", result={"days": [{"meals": []}]}),
        "finance": AgentEnvelope(
            agent="finance", status="partial", result={"totals": {"knownSubtotal": 0}, "costBreakdown": []}
        ),
    }

    env = await ValidatorAgent().run(t, {"validator_phase": "audit", "agent_results": results})

    assert env.result["is_valid"] is True
    assert env.result["audit_checks"]["hotel_cancellation_requirement_met"] is True


async def test_finance_no_invented_discount():
    from app.schemas import AgentEnvelope

    t = _trip()
    hotel = AgentEnvelope(
        agent="hotel",
        status="ok",
        result={
            "selected": {
                "name": "Test",
                "pricing": {"totalCost": 100000, "taxes": 0},
                "cancellation": {"status": "UNVERIFIED"},
            }
        },
    )
    env = await FinanceAgent().run(t, {"agent_results": {"hotel": hotel}})
    assert env.result["totals"]["discountApplied"] == 0
    assert env.result["offers"] == []
    assert env.result["offerStatus"] == "NOT_CONFIGURED"


async def test_finance_keeps_unquoted_prices_unknown():
    env = await FinanceAgent().run(_trip(), {"agent_results": {}})
    totals = env.result["totals"]
    assert totals["grandTotal"] is None
    assert totals["pricingStatus"] == "incomplete"
    assert totals["missingQuotes"] == ["hotel", "insurance", "transportation"]


async def test_seasonal_weather_uses_trip_dates_and_preserves_reference_dates(monkeypatch):
    from datetime import timedelta

    from app.agents import weather as weather_module
    from app.agents.weather import WeatherAgent
    from app.schemas import AgentEnvelope

    start = date.today() + timedelta(days=40)
    trip = _trip(start_date=start, end_date=start + timedelta(days=1))

    async def seasonal_archive(*args, **kwargs):
        return {
            "daily": {
                "time": [(start - timedelta(days=365) + timedelta(days=i)).isoformat() for i in range(2)],
                "temperature_2m_max": [21, 22],
                "temperature_2m_min": [14, 15],
                "precipitation_sum": [2, 0],
            }
        }

    monkeypatch.setattr(weather_module, "fetch_climate_archive", seasonal_archive)
    env = await WeatherAgent().run(
        trip,
        {
            "agent_results": {
                "travel_planner": AgentEnvelope(
                    agent="travel_planner",
                    status="ok",
                    result={"destination_geo": {"lat": 10, "lon": 77}},
                )
            }
        },
    )

    daily = env.result["daily_forecast"]
    assert [day["date"] for day in daily] == [start.isoformat(), (start + timedelta(days=1)).isoformat()]
    assert daily[0]["reference_date"] == (start - timedelta(days=365)).isoformat()
    assert "not an exact-date forecast" in env.result["weather_policy"]["summary"]
