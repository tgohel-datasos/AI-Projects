from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentEnvelope, TripRequest
from app.tools.food import daterange
from app.tools.geo import fetch_climate_archive, fetch_forecast


class WeatherAgent(BaseAgent):
    agent_id = "weather"
    title = "Weather Agent"

    async def run(self, trip: TripRequest, context: dict[str, Any]) -> AgentEnvelope:
        planner = context.get("agent_results", {}).get("travel_planner")
        geo = {}
        if planner:
            geo = planner.result.get("destination_geo") or {}
        if not geo:
            return self.ok(
                {"forecast_status": "NOT_AVAILABLE"},
                status="partial",
                missing=["destination_geo"],
                data_status="UNKNOWN",
            )

        horizon = date.today() + timedelta(days=16)
        daily = []
        status = "FORECAST_AVAILABLE"
        source = "open-meteo-forecast"
        raw = None
        try:
            if trip.end_date <= horizon:
                raw = await fetch_forecast(geo["lat"], geo["lon"], trip.start_date.isoformat(), trip.end_date.isoformat())
            else:
                prior_start = trip.start_date.replace(year=trip.start_date.year - 1)
                prior_end = trip.end_date.replace(year=trip.end_date.year - 1)
                raw = await fetch_climate_archive(geo["lat"], geo["lon"], prior_start.isoformat(), prior_end.isoformat())
                status = "LIMITED_FORECAST"
                source = "open-meteo-archive-seasonal"
        except Exception as exc:  # noqa: BLE001
            return self.ok(
                {"forecast_status": "NOT_AVAILABLE", "error": str(exc)},
                status="degraded",
                warnings=["Weather API failed; no invented daily temperatures."],
                data_status="UNKNOWN",
            )

        days = raw.get("daily") or {}
        dates = days.get("time") or []
        tmax = days.get("temperature_2m_max") or []
        tmin = days.get("temperature_2m_min") or []
        rainp = days.get("precipitation_probability_max") or [None] * len(dates)
        rain = days.get("precipitation_sum") or []
        trip_days = list(daterange(trip.start_date, trip.end_date))
        for i, trip_day in enumerate(trip_days):
            daily.append(
                {
                    # Archive rows are from the previous year. Keep the itinerary's
                    # requested date as the primary date and expose the source date
                    # separately so seasonal context cannot be mistaken for a forecast.
                    "date": trip_day.isoformat(),
                    "reference_date": dates[i] if i < len(dates) else None,
                    "temp_max_c": tmax[i] if i < len(tmax) else None,
                    "temp_min_c": tmin[i] if i < len(tmin) else None,
                    "rain_prob_pct": rainp[i] if i < len(rainp) else None,
                    "precip_mm": rain[i] if i < len(rain) else None,
                }
            )

        if not daily:
            for d in daterange(trip.start_date, trip.end_date):
                daily.append({"date": d.isoformat(), "temp_max_c": None, "temp_min_c": None})
            status = "NOT_AVAILABLE"

        temps = [x["temp_max_c"] for x in daily if x.get("temp_max_c") is not None]
        tmins = [x["temp_min_c"] for x in daily if x.get("temp_min_c") is not None]
        rain_days = [x for x in daily if (x.get("precip_mm") or 0) > 1 or (x.get("rain_prob_pct") or 0) > 40]
        avg_max = round(sum(temps) / len(temps), 1) if temps else None
        avg_min = round(sum(tmins) / len(tmins), 1) if tmins else None

        policy = {
            "summary": (
                "Seasonal historical weather mapped to the requested trip dates; not an exact-date forecast."
                if status == "LIMITED_FORECAST"
                else "Live weather forecast for the requested trip dates."
            ),
            "pros": [],
            "cons": [],
        }
        if avg_max and avg_max <= 22:
            policy["pros"].append("Cooler daytime temperatures for walking.")
            policy["cons"].append("Evenings may require warm layers, especially for children.")
        if rain_days:
            policy["cons"].append("Rain or high precipitation probability on some days — pack rain protection.")
        if not temps:
            policy["cons"].append("Exact-date forecast not available.")

        return self.ok(
            {
                "forecast_status": status,
                "average_temperature_celsius": {"min": avg_min, "max": avg_max},
                "precipitation_risk": "Elevated" if rain_days else "Low/unknown",
                "daily_forecast": daily,
                "weather_policy": policy,
                "rain_gear_needed": bool(rain_days),
            },
            status="ok" if status != "NOT_AVAILABLE" else "degraded",
            sources=[source],
            data_status="VERIFIED_LIVE" if status == "FORECAST_AVAILABLE" else "SEASONAL",
            warnings=["Seasonal archive used because dates are beyond the live forecast horizon."]
            if status == "LIMITED_FORECAST"
            else [],
        )
