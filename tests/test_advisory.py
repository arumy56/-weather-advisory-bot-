"""
Unit tests for DWAS Advisory Engine
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from advisory import advise, forecast, geocode, MSG


def test_advise_heavy_rain_english():
    sample_daily = {
        "time": ["2026-11-11", "2026-11-12", "2026-11-13"],
        "precipitation_sum": [2.0, 25.4, 0.0],
        "temperature_2m_max": [24.0, 22.0, 26.5]
    }
    result = advise(sample_daily, lang="en", location_name="Kitale, Kenya")
    assert "Heavy Rain Alert" in result
    assert "2026-11-12" in result
    assert "Delay foliar spraying" in result
    assert "Kitale, Kenya" in result


def test_advise_heavy_rain_swahili():
    sample_daily = {
        "time": ["2026-11-11", "2026-11-12", "2026-11-13"],
        "precipitation_sum": [30.0, 5.0, 1.0],
        "temperature_2m_max": [23.0, 25.0, 27.0]
    }
    result = advise(sample_daily, lang="sw", location_name="Mbeya, Tanzania")
    assert "Tahadhari ya Mvua Kubwa" in result
    assert "2026-11-11" in result
    assert "Ahirisha kupiga dawa" in result
    assert "Mbeya, Tanzania" in result


def test_advise_dry_spell():
    sample_daily = {
        "time": ["2026-11-11", "2026-11-12", "2026-11-13"],
        "precipitation_sum": [0.0, 0.2, 0.1],
        "temperature_2m_max": [31.0, 32.5, 33.0]
    }
    res_en = advise(sample_daily, lang="en")
    assert "Dry Spell Warning" in res_en
    assert "Prioritize irrigation" in res_en

    res_sw = advise(sample_daily, lang="sw")
    assert "Tahadhari ya Ukame" in res_sw
    assert "matandazo" in res_sw


def test_advise_moderate_weather():
    sample_daily = {
        "time": ["2026-11-11", "2026-11-12", "2026-11-13"],
        "precipitation_sum": [4.0, 5.5, 3.0],
        "temperature_2m_max": [24.0, 25.0, 24.5]
    }
    res_en = advise(sample_daily, lang="en")
    assert "Favorable Moisture" in res_en

    res_sw = advise(sample_daily, lang="sw")
    assert "Hali Nzuri ya Unyevu" in res_sw


def test_advise_empty_daily():
    result = advise({}, lang="en")
    assert "temporarily unavailable" in result


@pytest.mark.asyncio
async def test_geocode_success():
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "results": [
            {
                "latitude": -1.286389,
                "longitude": 36.817223,
                "name": "Nairobi",
                "country": "Kenya"
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = fake_response

    res = await geocode("Nairobi", client=mock_client)
    assert res is not None
    lat, lon, name = res
    assert abs(lat - (-1.286)) < 0.01
    assert "Nairobi" in name
    assert "Kenya" in name


@pytest.mark.asyncio
async def test_geocode_not_found():
    fake_response = MagicMock()
    fake_response.json.return_value = {"results": []}
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = fake_response

    res = await geocode("NonExistentPlaceXYZ123", client=mock_client)
    assert res is None


@pytest.mark.asyncio
async def test_forecast_fetch():
    fake_daily = {
        "time": ["2026-11-11", "2026-11-12", "2026-11-13"],
        "precipitation_sum": [0.0, 10.0, 5.0],
        "temperature_2m_max": [25.0, 24.0, 26.0]
    }
    fake_response = MagicMock()
    fake_response.json.return_value = {"daily": fake_daily}
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = fake_response

    daily = await forecast(-1.28, 36.81, client=mock_client)
    assert daily == fake_daily
