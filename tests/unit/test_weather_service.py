import pytest

from src.services.weather_service import _get_weather_icon


@pytest.mark.parametrize(
    "weather_code, expected_icon",
    [
        # Clear / partly cloudy
        (0, "\u2600\ufe0f"),      # ☀️  Clear sky
        (1, "\U0001f324\ufe0f"),  # 🌤️  Mainly clear
        (2, "\U0001f325\ufe0f"),  # 🌥️  Partly cloudy
        (3, "\u2601\ufe0f"),      # ☁️  Overcast
        # Fog
        (45, "\U0001f32b\ufe0f"), # 🌫️  Fog
        (48, "\U0001f32b\ufe0f"), # 🌫️  Depositing rime fog
        # Drizzle
        (51, "\U0001f4a7"),       # 💧  Light drizzle
        # Rain
        (61, "\U0001f327\ufe0f"), # 🌧️  Slight rain
        # Snow
        (71, "\u2744\ufe0f"),     # ❄️  Slight snow fall
        # Rain showers
        (80, "\U0001f326\ufe0f"), # 🌦️  Slight rain showers
        # Snow showers
        (85, "\U0001f328\ufe0f"), # 🌨️  Slight snow showers
        # Thunderstorm
        (95, "\u26c8\ufe0f"),     # ⛈️  Thunderstorm
    ],
    ids=[
        "clear_sky_0",
        "mainly_clear_1",
        "partly_cloudy_2",
        "overcast_3",
        "fog_45",
        "rime_fog_48",
        "drizzle_51",
        "rain_61",
        "snow_71",
        "rain_showers_80",
        "snow_showers_85",
        "thunderstorm_95",
    ],
)
def test_get_weather_icon_known_codes(weather_code, expected_icon):
    assert _get_weather_icon(weather_code) == expected_icon


@pytest.mark.parametrize(
    "weather_code",
    [-1, 100, 999],
    ids=["negative_code", "unassigned_100", "large_unknown_999"],
)
def test_get_weather_icon_unknown_codes_return_fallback(weather_code):
    assert _get_weather_icon(weather_code) == "\U0001f321\ufe0f"  # 🌡️
