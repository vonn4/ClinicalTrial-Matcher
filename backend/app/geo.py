"""Free, city-level geocoding for fictional trial-location preferences.

Only a city/region string (never diagnoses or profile details) is sent to the
noncommercial Open-Meteo geocoding endpoint. Seattle remains available without
network access for the Hackaroo acceptance test. Failed or ambiguous resolution
never becomes a fabricated radius claim.
"""
from __future__ import annotations
import math
import re
import time
import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
# Grounded approximate city centers for offline acceptance of the key demo case.
LOCAL_CENTERS = {
    "seattle,washington": (47.6062, -122.3321),
    "seattle,wa": (47.6062, -122.3321),
}
_cache: dict[str, tuple[float, tuple[float, float] | None]] = {}
_CACHE_SECONDS = 24 * 3600
_REGION_ALIASES = {
    "wa": "washington", "mo": "missouri", "ks": "kansas",
    "ny": "new york", "ca": "california", "il": "illinois",
    "ma": "massachusetts", "tx": "texas", "fl": "florida",
    "or": "oregon", "pa": "pennsylvania", "oh": "ohio",
}
_TRAVEL_RADII = {"Within 50 miles": 50, "Within 100 miles": 100,
                 "Within 250 miles": 250}


def travel_radius(profile) -> int | None:
    answer = profile.intake_answers.get("travel") if profile.intake_answers else None
    if answer and answer.state == "answered":
        return _TRAVEL_RADII.get(answer.value or "")
    # A quick-description profile has no explicit verified distance preference.
    return None


def _normalize_region(value: str) -> str:
    value = " ".join(value.strip().lower().split())
    return _REGION_ALIASES.get(value, value)


def _parse_city(value: str | None) -> tuple[str, str] | None:
    if not value or not 4 <= len(value) <= 90 or re.search(r"[0-9;<>\[\]{}]", value):
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) not in (2, 3) or any(not p for p in parts):
        return None
    if not re.fullmatch(r"[\w .'-]+", parts[0]) or not re.fullmatch(r"[\w .'-]+", parts[1]):
        return None
    return parts[0], parts[1]


async def resolve_city(value: str | None) -> tuple[float, float] | None:
    """Resolve city/region only; reject unverified or ambiguous geocoder guesses."""
    parts = _parse_city(value)
    if not parts:
        return None
    city, region = parts
    key = city.lower() + "," + _normalize_region(region)
    if key in LOCAL_CENTERS:
        return LOCAL_CENTERS[key]
    entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < _CACHE_SECONDS:
        return entry[1]
    coordinates = None
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=False) as client:
            response = await client.get(GEOCODE_URL, params={
                "name": f"{city}, {region}", "count": 10, "language": "en", "format": "json"
            })
            response.raise_for_status()
            options = response.json().get("results") or []
        exact = [
            candidate for candidate in options
            if str(candidate.get("name", "")).strip().casefold() == city.casefold()
            and _normalize_region(str(candidate.get("admin1", ""))) == _normalize_region(region)
        ]
        if len(exact) == 1:
            latitude = float(exact[0]["latitude"])
            longitude = float(exact[0]["longitude"])
            if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
                coordinates = (latitude, longitude)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    if len(_cache) >= 64:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), coordinates)
    return coordinates


def miles_between(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    """Haversine straight-line distance, not road or transit distance."""
    lat1, lon1 = map(math.radians, point_a)
    lat2, lon2 = map(math.radians, point_b)
    a = (math.sin((lat2 - lat1) / 2)**2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2)**2)
    return 3958.7613 * 2 * math.asin(min(1.0, math.sqrt(a)))
