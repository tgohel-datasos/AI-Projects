from __future__ import annotations

import math
from typing import Any

import httpx

from app.config import settings

NOMINATIM = "https://nominatim.openstreetmap.org"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def geocode(place: str) -> dict[str, Any] | None:
    headers = {"User-Agent": settings.nominatim_user_agent}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        r = await client.get(
            f"{NOMINATIM}/search",
            params={"q": place, "format": "json", "limit": 1},
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        item = data[0]
        return {
            "name": item.get("display_name", place),
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "source": "nominatim",
        }


async def search_pois(query: str, limit: int = 8) -> list[dict[str, Any]]:
    headers = {"User-Agent": settings.nominatim_user_agent}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        r = await client.get(
            f"{NOMINATIM}/search",
            params={"q": query, "format": "json", "limit": limit},
        )
        r.raise_for_status()
        out = []
        for item in r.json():
            out.append(
                {
                    "name": item.get("display_name", query).split(",")[0],
                    "full_name": item.get("display_name"),
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "type": item.get("type"),
                    "source": "nominatim",
                }
            )
        return out


async def fetch_forecast(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code",
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(OPEN_METEO, params=params)
        r.raise_for_status()
        return r.json()


async def fetch_climate_archive(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    # Use a prior-year window as seasonal baseline when live forecast horizon is exceeded.
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(OPEN_METEO_ARCHIVE, params=params)
        r.raise_for_status()
        return r.json()
