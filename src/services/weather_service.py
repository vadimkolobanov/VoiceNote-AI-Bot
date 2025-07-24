# src/services/weather_service.py
import logging
import aiohttp
from src.core.config import APP_USER_AGENT

logger = logging.getLogger(__name__)

GEOCODER_API_URL = "https://nominatim.openstreetmap.org/search"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
PRIORITY_COUNTRY_CODES = "ru,by,ua,kz,kg,uz,md,am,ge,az"

def _get_weather_icon(weather_code: int) -> str:
    """
    Возвращает иконку погоды по коду WMO (World Meteorological Organization).
    """
    if weather_code == 0: return "☀️"
    if weather_code == 1: return "🌤️"
    if weather_code == 2: return "🌥️"
    if weather_code == 3: return "☁️"
    if weather_code in [45, 48]: return "🌫️"
    if weather_code in [51, 53, 55, 56, 57]: return "💧"
    if weather_code in [61, 63, 65, 66, 67]: return "🌧️"
    if weather_code in [71, 73, 75, 77]: return "❄️"
    if weather_code in [80, 81, 82]: return "🌦️"
    if weather_code in [85, 86]: return "🌨️"
    if weather_code in [95, 96, 99]: return "⛈️"
    return ""


async def _get_coords_for_city(city: str) -> tuple[float, float, str] | None:
    """
    Получает координаты (широта, долгота) и найденное имя города через Nominatim,
    приоритизируя русскоязычные страны.
    """
    params = {
        "q": city,
        "format": "json",
        "accept-language": "ru",
        "limit": 1,
        "countrycodes": PRIORITY_COUNTRY_CODES
    }
    headers = {"User-Agent": APP_USER_AGENT}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GEOCODER_API_URL, params=params, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка API Nominatim: {resp.status}, {await resp.text()}")
                    return None
                data = await resp.json()
                if not data:
                    logger.warning(f"Город '{city}' не найден Nominatim в приоритетных странах.")
                    # Попробуем найти по всему миру, если не нашли в СНГ
                    del params['countrycodes']
                    async with session.get(GEOCODER_API_URL, params=params, headers=headers) as fallback_resp:
                        data = await fallback_resp.json()
                        if not data:
                            logger.warning(f"Город '{city}' не найден Nominatim глобально.")
                            return None

                result = data[0]
                lat, lon = float(result["lat"]), float(result["lon"])
                found_name = result.get("display_name", city).split(',')[0]
                return lat, lon, found_name
    except Exception as e:
        logger.error(f"Не удалось получить координаты для '{city}': {e}", exc_info=True)
        return None


async def get_weather_for_city(city: str) -> str | None:
    """
    Получает и форматирует прогноз погоды для города через Open-Meteo.
    Возвращает готовую для отправки строку или None в случае ошибки.
    """
    coords_data = await _get_coords_for_city(city)
    if not coords_data:
        return f"Не удалось найти город «{city}». Пожалуйста, проверьте название."

    lat, lon, found_name = coords_data

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min",
        "current_weather": "true",
        "timezone": "auto"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEATHER_API_URL, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка API Open-Meteo: {resp.status}, {await resp.text()}")
                    return "Сервис погоды временно недоступен."

                data = await resp.json()
                current = data.get("current_weather")
                daily = data.get("daily")

                if not current or not daily:
                    return "Не удалось получить полный прогноз погоды."

                temp_now = int(current.get('temperature'))
                weather_code_now = current.get('weathercode')
                icon_now = _get_weather_icon(weather_code_now)

                temp_min = int(daily.get('temperature_2m_min', [0])[0])
                temp_max = int(daily.get('temperature_2m_max', [0])[0])
                weather_code_day = daily.get('weathercode', [0])[0]
                icon_day = _get_weather_icon(weather_code_day)

                return (
                    f"в г. {found_name}: сейчас {temp_now}°{icon_now}, "
                    f"днём от {temp_min}° до {temp_max}°{icon_day}"
                )

    except Exception as e:
        logger.error(f"Не удалось получить погоду для '{city}': {e}", exc_info=True)
        return "Произошла ошибка при получении прогноза погоды."