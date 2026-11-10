"""
DWAS - Digital Weather Advisory Service Core Engine
Provides geocoding, 3-day weather forecasting via Open-Meteo,
and agricultural decision support advisories in English and Kiswahili.
"""

from typing import Any, Dict, Optional, Tuple
import httpx

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

MSG: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": (
            "🌾 *Welcome to the Farm Weather Advisory Service (DWAS)*\n\n"
            "Send your town or village name, or share your GPS location to get a 3-day agricultural forecast.\n\n"
            "• Use /sw for Kiswahili\n"
            "• Use /en for English\n"
            "• Use /help for instructions"
        ),
        "notfound": "⚠️ Could not locate '{query}'. Please check spelling or try a nearby major town.",
        "api_error": "⚠️ Weather service is temporarily unavailable. Please try again shortly.",
        "forecast_header": "📍 *Weather Advisory for {location}* (Next 3 Days)\n",
        "day_row": "• *{date}*: 🌡️ Max {temp}°C | 🌧️ Rain: {rain} mm\n",
        "advisory_header": "\n🚜 *Agronomic Recommendation:*",
        "rain_heavy": "🚨 *Heavy Rain Alert* ({dates}): Soil saturation risk. Delay foliar spraying, pesticides, and synthetic fertilizer application to prevent chemical runoff and nutrient leaching. Ensure field drainage channels are clear.",
        "rain_moderate": "🌱 *Favorable Moisture*: Normal rainfall expected ({total_rain} mm total). Ideal conditions for land preparation, weeding, and transplanting hardy crops.",
        "dry_spell": "☀️ *Dry Spell Warning*: Very low rainfall (< {total_rain} mm total over 3 days). Prioritize irrigation, apply organic mulch to retain soil moisture, and avoid transplanting tender seedlings."
    },
    "sw": {
        "welcome": (
            "🌾 *Karibu kwenye Huduma ya Ushauri wa Hali ya Hewa Kilimo (DWAS)*\n\n"
            "Tuma jina la mji/kijiji chako au shiriki eneo lako la GPS kupata utabiri na ushauri wa kilimo wa siku 3.\n\n"
            "• Tumia /en kwa Kiingereza\n"
            "• Tumia /sw kwa Kiswahili\n"
            "• Tumia /help kupata maelekezo"
        ),
        "notfound": "⚠️ Sijapata eneo '{query}'. Tafadhali angalia herufi au jaribu mji wa karibu.",
        "api_error": "⚠️ Huduma ya hali ya hewa haipatikani kwa sasa. Tafadhali jaribu tena baadae kidogo.",
        "forecast_header": "📍 *Ushauri wa Hali ya Hewa: {location}* (Siku 3 Zijazo)\n",
        "day_row": "• *{date}*: 🌡️ Joto {temp}°C | 🌧️ Mvua: {rain} mm\n",
        "advisory_header": "\n🚜 *Ushauri wa Kilimo:*",
        "rain_heavy": "🚨 *Tahadhari ya Mvua Kubwa* ({dates}): Hatari ya mafuriko shambani. Ahirisha kupiga dawa na kuweka mbolea ili kuzuia kusombwa na maji. Hakikisha mitaro ya kupitisha maji ipo wazi.",
        "rain_moderate": "🌱 *Hali Nzuri ya Unyevu*: Mvua ya wastani inatarajiwa (jumla ya mm {total_rain}). Inafaa kwa kupalilia, kutayarisha shamba, na kupanda.",
        "dry_spell": "☀️ *Tahadhari ya Ukame*: Mvua kidogo sana (chini ya mm {total_rain} kwa siku 3). Zingatia umwagiliaji, weka matandazo (mulching) kuhifadhi unyevu udongoni, na epuka kupandikiza miche michanga."
    }
}


async def geocode(query: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Tuple[float, float, str]]:
    """
    Geocode a town or location name using Open-Meteo Geocoding API.
    Returns (latitude, longitude, display_name) or None if not found.
    """
    params = {"name": query.strip(), "count": 1, "language": "en", "format": "json"}
    
    async def _fetch(c: httpx.AsyncClient):
        resp = await c.get(OPEN_METEO_GEOCODING_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        if not results:
            return None
        item = results[0]
        country = item.get("country", "")
        name = item.get("name", query)
        display_name = f"{name}, {country}" if country else name
        return (float(item["latitude"]), float(item["longitude"]), display_name)

    try:
        if client:
            return await _fetch(client)
        async with httpx.AsyncClient() as c:
            return await _fetch(c)
    except Exception:
        return None


async def forecast(lat: float, lon: float, client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    """
    Fetch 3-day daily precipitation and max temperature forecast from Open-Meteo.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": 3,
        "daily": ["precipitation_sum", "temperature_2m_max"],
        "timezone": "auto"
    }
    
    async def _fetch(c: httpx.AsyncClient):
        resp = await c.get(OPEN_METEO_FORECAST_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("daily", {})

    if client:
        return await _fetch(client)
    async with httpx.AsyncClient() as c:
        return await _fetch(c)


def advise(daily: Dict[str, Any], lang: str = "en", location_name: Optional[str] = None) -> str:
    """
    Synthesize daily weather forecast into actionable agronomic advisory text.
    """
    lang = lang if lang in MSG else "en"
    m = MSG[lang]

    dates = daily.get("time", [])
    rains = [float(r) if r is not None else 0.0 for r in daily.get("precipitation_sum", [])]
    temps = [float(t) if t is not None else 0.0 for t in daily.get("temperature_2m_max", [])]

    if not dates or not rains:
        return m["api_error"]

    loc_str = location_name or ("Your Coordinates" if lang == "en" else "Eneo Lako")
    lines = [m["forecast_header"].format(location=loc_str)]

    for d, t, r in zip(dates, temps, rains):
        lines.append(m["day_row"].format(date=d, temp=f"{t:.1f}", rain=f"{r:.1f}"))

    lines.append(m["advisory_header"])

    # Agronomic Decision Rules
    heavy_dates = [d for d, r in zip(dates, rains) if r >= 20.0]
    total_rain = sum(rains)

    if heavy_dates:
        lines.append(m["rain_heavy"].format(dates=", ".join(heavy_dates)))
    elif total_rain < 2.0:
        lines.append(m["dry_spell"].format(total_rain=f"{total_rain:.1f}"))
    else:
        lines.append(m["rain_moderate"].format(total_rain=f"{total_rain:.1f}"))

    return "\n".join(lines)
