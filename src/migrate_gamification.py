# migrate_gamification.py
import asyncio
import logging
from tqdm import tqdm  # для красивого прогресс-бара, установите: pip install tqdm

from src.database import connection, user_repo, note_repo, birthday_repo
from src.services.gamification_service import XP_REWARDS, check_and_grant_achievements, AchievCode
from src.core.logging_setup import setup_logging

# Настраиваем логирование, чтобы видеть, что происходит
setup_logging()
logger = logging.getLogger(__name__)


async def calculate_initial_xp(user_id: int) -> int:
    """Подсчитывает стартовый опыт на основе прошлых действий."""
    total_xp = 0

    # 1. Опыт за заметки
    total_notes, voice_notes = await note_repo.count_total_and_voice_notes(user_id)
    text_notes = total_notes - voice_notes
    total_xp += text_notes * XP_REWARDS['create_note_text']
    total_xp += voice_notes * XP_REWARDS['create_note_voice']

    # 2. Опыт за выполненные заметки
    completed_notes = await note_repo.count_completed_notes(user_id)
    total_xp += completed_notes * XP_REWARDS['note_completed']

    # 3. Опыт за дни рождения
    birthdays_count = await birthday_repo.count_birthdays_for_user(user_id)
    total_xp += birthdays_count * XP_REWARDS['add_birthday_manual']

    # 4. Опыт за шаринг (если хоть раз делился)
    has_shared = await note_repo.did_user_share_note(user_id)
    if has_shared:
        total_xp += XP_REWARDS['note_shared']

    return total_xp


async def main():
    logger.info("--- Запуск миграции данных геймификации ---")

    # Инициализируем соединение с БД
    await connection.init_db()

    # Получаем ID всех пользователей
    pool = await connection.get_db_pool()
    async with pool.acquire() as conn:
        users_records = await conn.fetch("SELECT telegram_id FROM users")
        all_user_ids = [rec['telegram_id'] for rec in users_records]

    logger.info(f"Найдено {len(all_user_ids)} пользователей для обработки.")

    # Используем tqdm для визуализации прогресса
    for user_id in tqdm(all_user_ids, desc="Миграция пользователей"):
        try:
            # 1. Считаем и устанавливаем стартовый опыт
            initial_xp = await calculate_initial_xp(user_id)
            initial_level = user_repo.get_level_for_xp(initial_xp)

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET xp = $1, level = $2 WHERE telegram_id = $3",
                    initial_xp, initial_level, user_id
                )

            # 2. "Тихо" выдаем все уже заработанные ачивки
            # Мы передаем `bot=None`, т.к. в тихом режиме он не нужен для отправки сообщений
            await check_and_grant_achievements(bot=None, user_id=user_id, silent=True)

        except Exception as e:
            logger.error(f"Ошибка при обработке пользователя {user_id}: {e}", exc_info=True)

    # Закрываем соединение с БД
    await connection.close_db_pool()
    logger.info("--- Миграция данных геймификации успешно завершена ---")


if __name__ == "__main__":
    asyncio.run(main())