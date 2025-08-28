# src/services/tz_utils.py
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# Список распространенных часовых поясов для удобства пользователя в клавиатурах.
# Названия ключей - то, что видит пользователь. Значения - IANA Time Zone Database names.
COMMON_TIMEZONES = {
    "Калининград (UTC+2)": "Europe/Kaliningrad",
    "Москва (UTC+3)": "Europe/Moscow",
    "Самара (UTC+4)": "Europe/Samara",
    "Екатеринбург (UTC+5)": "Asia/Yekaterinburg",
    "Омск (UTC+6)": "Asia/Omsk",
    "Красноярск (UTC+7)": "Asia/Krasnoyarsk",
    "Иркутск (UTC+8)": "Asia/Irkutsk",
    "Якутск (UTC+9)": "Asia/Yakutsk",
    "Владивосток (UTC+10)": "Asia/Vladivostok",
    "Магадан (UTC+11)": "Asia/Magadan",
    "Камчатка (UTC+12)": "Asia/Kamchatka",
}

# Множество всех доступных часовых поясов для валидации ручного ввода.
ALL_PYTZ_TIMEZONES = pytz.all_timezones_set


def format_datetime_for_user(
        dt_obj: datetime | None,
        user_tz_str: str | None,
        default_tz: str = 'UTC'
) -> str | None:
    """
    Конвертирует datetime объект (предположительно в UTC) в строку,
    отформатрованную для часового пояса пользователя.

    :param dt_obj: Объект datetime для форматирования. Должен быть aware (с tzinfo).
    :param user_tz_str: Строка с названием часового пояса пользователя (например, 'Europe/Moscow').
    :param default_tz: Часовой пояс по умолчанию, если у пользователя он не задан.
    :return: Отформатированная строка или None, если dt_obj is None.
    """
    if not dt_obj:
        return None

    # Если у пользователя не задан часовой пояс, используем пояс по умолчанию
    target_tz_str = user_tz_str or default_tz

    try:
        # Получаем объект часового пояса
        target_tz = pytz.timezone(target_tz_str)
    except pytz.UnknownTimeZoneError:
        # Если в профиле пользователя некорректная таймзона, откатываемся к UTC
        logger.warning(
            f"Неизвестный часовой пояс '{target_tz_str}' в профиле. "
            f"Используется UTC по умолчанию."
        )
        target_tz = pytz.timezone('UTC')

    # Убедимся, что исходный datetime имеет информацию о часовом поясе (aware)
    # Если он naive (без tzinfo), предполагаем, что это UTC, как и хранится в нашей БД.
    if dt_obj.tzinfo is None:
        dt_obj = pytz.utc.localize(dt_obj)

    # Конвертируем время в целевой часовой пояс
    local_dt = dt_obj.astimezone(target_tz)

    # Форматируем в удобный для пользователя вид
    # %Z показывает аббревиатуру часового пояса (например, MSK)
    return local_dt.strftime('%d.%m.%Y %H:%M (%Z)')

from datetime import datetime

def get_day_of_week_str(dt: datetime) -> str:
    """Возвращает название дня недели на русском."""
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return days[dt.weekday()]
# Пример использования (для самопроверки и отладки)
if __name__ == '__main__':
    # Время в UTC, как оно было бы извлечено из БД
    utc_now = datetime.now(pytz.utc)
    print(f"Текущее время в UTC: {utc_now}")

    # Пользователь из Москвы
    user_timezone_moscow = 'Europe/Moscow'
    formatted_time_moscow = format_datetime_for_user(utc_now, user_timezone_moscow)
    print(f"Время для пользователя из Москвы: {formatted_time_moscow}")

    # Пользователь из Владивостока
    user_timezone_vlad = 'Asia/Vladivostok'
    formatted_time_vlad = format_datetime_for_user(utc_now, user_timezone_vlad)
    print(f"Время для пользователя из Владивостока: {formatted_time_vlad}")

    # Пользователь, у которого не задан часовой пояс (или задан неверно)
    formatted_time_default = format_datetime_for_user(utc_now, None)
    print(f"Время для пользователя без таймзоны: {formatted_time_default}")

    formatted_time_invalid = format_datetime_for_user(utc_now, 'Invalid/Timezone')
    print(f"Время для пользователя с неверной таймзоной: {formatted_time_invalid}")