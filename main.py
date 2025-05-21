# main.py
import logging
import os
import json
import asyncio  # Для asyncio.run
from datetime import datetime

from aiogram import Bot, Router, types, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hcode, hbold, hitalic
from aiogram.fsm.storage.memory import MemoryStorage  # Для FSM
from aiogram.fsm.context import FSMContext  # Для FSM
from aiogram.fsm.state import State, StatesGroup  # Для FSM

# Импорты из наших модулей
from inline_keyboards import get_action_keyboard, get_confirm_save_keyboard, NoteCallbackFactory, \
    get_note_actions_keyboard
from utills import hf_speech_to_text
from llm_processor import enhance_text_with_llm
import database_setup as db  # Импортируем наш модуль для работы с БД

# Загрузка переменных окружения (если используете .env)
from dotenv import load_dotenv

load_dotenv()
#TODO Убрать max_notes_mvp когда буду снимать лимит
MAX_NOTES_MVP = 5
# --- КОНФИГУРАЦИЯ ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ БОТА ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
DEEPSEEK_API_KEY_EXISTS = bool(os.environ.get("DEEPSEEK_API_KEY"))

if not TG_BOT_TOKEN:
    logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
    exit("Ошибка: TG_BOT_TOKEN не найден.")

if not DEEPSEEK_API_KEY_EXISTS:
    logger.warning("Переменная окружения DEEPSEEK_API_KEY не установлена! Функционал LLM будет недоступен.")

bot = Bot(token=TG_BOT_TOKEN)
router = Router()
# Используем MemoryStorage для FSM. Для продакшена лучше RedisStorage или другое.
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- СОСТОЯНИЯ FSM ---
class NoteCreationStates(StatesGroup):
    awaiting_confirmation = State()  # Ожидание подтверждения сохранения


# --- ОБРАБОТЧИКИ ---

async def get_or_create_user(tg_user: types.User):
    """Вспомогательная функция для добавления/обновления пользователя в БД."""
    user = await db.get_user_profile(tg_user.id)
    if not user:
        user = await db.add_or_update_user(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code
        )
        logger.info(f"Новый пользователь зарегистрирован: {tg_user.id}")
    else:  # Обновим данные, если они изменились (username, имя и т.д.)
        user = await db.add_or_update_user(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code
        )
    return user


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):  # Добавляем state на всякий случай
    """Обработчик команды /start."""
    await state.clear()  # Сбрасываем состояние, если оно было
    await get_or_create_user(message.from_user)  # Регистрируем/обновляем пользователя

    await message.answer(
        "🎤 Привет! Я VoiceNote AI, твой помощник для создания умных голосовых заметок.\n\n"
        "Просто отправь мне голосовое сообщение, и я:\n"
        "1. Распознаю речь.\n"
        "2. Улучшу текст и извлеку важные детали с помощью AI.\n"
        "3. Предложу сохранить заметку.\n\n"
        "Используй кнопки ниже для навигации или сразу отправляй голосовое!",
        reply_markup=get_action_keyboard()
    )


@router.message(F.voice)
async def handle_voice(message: types.Message, state: FSMContext):
    """Обработчик голосовых сообщений."""
    await get_or_create_user(message.from_user)  # Убедимся, что пользователь есть в БД

    voice = message.voice
    file_id = voice.file_id

    status_message = await message.reply("✔️ Запись получена. Начинаю распознавание речи...")

    try:
        file_info = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
    except Exception as e:
        logger.exception("Ошибка получения информации о файле из Telegram")
        await status_message.edit_text(f"❌ Ошибка при получении файла от Telegram: {e}")
        return
    voice_message_datetime = message.date
    raw_text = await hf_speech_to_text(file_url)
    if not raw_text:
        await status_message.edit_text(
            "❌ Не удалось распознать речь. Попробуйте записать четче."
        )
        return

    await status_message.edit_text(
        f"🗣️ Распознано (STT):\n{hcode(raw_text)}\n\n"
        "✨ Улучшаю текст и извлекаю детали с помощью LLM..."
    )

    llm_analysis_result = None
    corrected_text_for_response = raw_text  # По умолчанию, если LLM не сработает

    if DEEPSEEK_API_KEY_EXISTS:
        llm_result_dict = await enhance_text_with_llm(raw_text)
        if "error" in llm_result_dict:
            logger.error(f"LLM processing error: {llm_result_dict['error']}")
            llm_info_for_user = f"⚠️ {hbold('Ошибка при обработке LLM:')} {hcode(llm_result_dict['error'])}"
            # В этом случае llm_analysis_result остается None
        else:
            llm_analysis_result = llm_result_dict  # Сохраняем весь результат для БД
            corrected_text_for_response = llm_result_dict.get("corrected_text", raw_text)
            llm_info_for_user = f"{hbold('✨ Улучшенный текст (LLM):')}\n{hcode(corrected_text_for_response)}"

            details_parts = []
            if llm_result_dict.get("task_description"):
                details_parts.append(f"📝 {hbold('Задача:')} {hitalic(llm_result_dict['task_description'])}")
            # ... (остальные детали, как в предыдущей версии)
            dates_times_str_list = []
            for dt_entry in llm_result_dict.get("dates_times", []):
                mention = dt_entry.get('original_mention', 'N/A')
                start_dt = dt_entry.get('absolute_datetime_start', 'N/A')
                dates_times_str_list.append(f"- {hitalic(mention)} -> {hcode(start_dt)}")
            if dates_times_str_list:
                details_parts.append(f"🗓️ {hbold('Даты/Время:')}\n" + "\n".join(dates_times_str_list))

            if llm_result_dict.get("people_mentioned"):
                details_parts.append(f"👥 {hbold('Люди:')} {hitalic(', '.join(llm_result_dict['people_mentioned']))}")
            if llm_result_dict.get("locations_mentioned"):
                details_parts.append(
                    f"📍 {hbold('Места:')} {hitalic(', '.join(llm_result_dict['locations_mentioned']))}")
            if llm_result_dict.get("implied_intent"):
                details_parts.append(f"💡 {hbold('Намерения:')} {hcode(', '.join(llm_result_dict['implied_intent']))}")

            if details_parts:
                llm_info_for_user += f"\n\n{hbold('🔍 Извлеченные детали:')}\n" + "\n\n".join(details_parts)
    else:
        llm_info_for_user = f"{hitalic('LLM обработка пропущена: DEEPSEEK_API_KEY не настроен.')}"

    # Сохраняем данные в FSM для подтверждения
    await state.set_state(NoteCreationStates.awaiting_confirmation)
    await state.update_data(
        original_stt_text=raw_text,
        corrected_text=corrected_text_for_response,  # Текст, который будет сохранен
        llm_analysis_json=llm_analysis_result,  # Полный JSON от LLM или None
        original_audio_telegram_file_id=file_id,
        voice_message_date=voice_message_datetime
        # Можно добавить и другие данные, если нужно, например, due_date из llm_analysis_result
    )

    response_message_text = (
        f"{hbold('🎙️ Исходный текст (STT):')}\n{hcode(raw_text)}\n\n"
        f"{llm_info_for_user}\n\n"
        f"{hbold('📊 Параметры аудио:')}\n"
        f"Длительность: {voice.duration} сек, Размер: {voice.file_size // 1024} КБ\n\n"
        "💾 Сохранить эту заметку?"
    )

    try:
        await status_message.edit_text(
            response_message_text,
            reply_markup=get_confirm_save_keyboard(),  # Клавиатура "Сохранить/Отмена"
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение, отправляю новое: {e}")
        await message.answer(
            response_message_text,
            reply_markup=get_confirm_save_keyboard(),
            parse_mode="HTML"
        )


@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "confirm_save_note")
async def confirm_save_note_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения сохранения заметки."""


    user_data = await state.get_data()
    voice_message_date = user_data.get("voice_message_date")
    telegram_id = callback_query.from_user.id

    original_stt_text = user_data.get("original_stt_text")
    corrected_text = user_data.get("corrected_text")
    llm_analysis_json = user_data.get("llm_analysis_json")  # Это уже dict или None
    audio_file_id = user_data.get("original_audio_telegram_file_id")

    # Извлечение due_date из llm_analysis_json, если оно есть
    due_date_obj = None
    if llm_analysis_json and "dates_times" in llm_analysis_json and llm_analysis_json["dates_times"]:
        # Берем первую дату/время как due_date, можно усложнить логику выбора
        first_date_time_entry = llm_analysis_json["dates_times"][0]
        if "absolute_datetime_start" in first_date_time_entry:
            try:
                # Преобразуем строку ISO 8601 в datetime объект
                due_date_str = first_date_time_entry["absolute_datetime_start"]
                # Убираем 'Z' если есть, asyncpg может не понять его для timestamptz без явного указания
                if due_date_str.endswith('Z'):
                    due_date_str = due_date_str[:-1] + "+00:00"
                due_date_obj = datetime.fromisoformat(due_date_str)
            except ValueError as e:
                logger.warning(
                    f"Не удалось распарсить due_date '{first_date_time_entry['absolute_datetime_start']}': {e}")

    current_notes = await db.get_notes_by_user(telegram_id, limit=MAX_NOTES_MVP + 1, archived=False)
    if len(current_notes) >= MAX_NOTES_MVP:
        await callback_query.message.edit_text(
            f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок.\n"
            "Проект находится в тестовом режиме\n"
            "Чтобы добавить новую, пожалуйста, удалите одну из существующих."
            ,
            reply_markup=None
        )
        await callback_query.answer("Лимит заметок достигнут", show_alert=True)
        await state.clear()
        # Отправляем главное меню
        await callback_query.message.answer(
            "Чем еще могу помочь?",
            reply_markup=get_action_keyboard()
        )
        return  # Прерываем сохранение
    note_id = await db.create_note(
        telegram_id=telegram_id,
        original_stt_text=original_stt_text,
        corrected_text=corrected_text,
        llm_analysis_json=llm_analysis_json,  # Передаем dict, db.create_note его сериализует
        original_audio_telegram_file_id=audio_file_id,
        due_date=due_date_obj,  # Передаем datetime объект или None
        note_taken_at = voice_message_date
        # category, tags, location_info - можно будет добавить позже из llm_analysis_json
    )

    if note_id:
        await callback_query.message.edit_text(
            f"✅ Заметка #{note_id} успешно сохранена!\n\n{hcode(corrected_text)}",
            parse_mode="HTML",
            reply_markup=None  # Убираем клавиатуру подтверждения
        )
    else:
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при сохранении заметки в базу данных.",
            reply_markup=None
        )
    await callback_query.answer()
    await state.clear()
    # Отправляем главное меню новым сообщением
    await callback_query.message.answer(
        "Чем еще могу помочь?",
        reply_markup=get_action_keyboard()
    )

    await callback_query.answer()  # Отвечаем на callback
    await state.clear()  # Очищаем состояние FSM


@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "cancel_save_note")
async def cancel_save_note_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик отмены сохранения заметки."""
    await callback_query.message.edit_text(
        "🚫 Сохранение отменено.",
        reply_markup=None
    )
    await callback_query.answer()
    await state.clear()


# --- ОБРАБОТЧИКИ ДЛЯ ПРОСМОТРА И УДАЛЕНИЯ ЗАМЕТОК ---

@router.callback_query(F.data == "my_notes")
async def my_notes_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Мои заметки'."""
    await state.clear()  # На всякий случай очистим состояние
    telegram_id = callback_query.from_user.id

    # Для MVP покажем первые N заметок без сложной пагинации
    # В будущем можно добавить кнопки "Вперед/Назад" и передавать offset в callback_data
    notes = await db.get_notes_by_user(telegram_id, limit=5, offset=0, archived=False)

    if not notes:
        await callback_query.message.answer("У вас пока нет сохраненных заметок.")
        await callback_query.answer()
        return

    response_text = f"{hbold('📝 Ваши последние заметки:')}\n\n"

    # Удаляем предыдущее сообщение с кнопками, если это был ответ на callback с Inline клавиатурой
    # или редактируем, если это было сообщение бота.
    # Для простоты MVP, если это callback, просто отправим новое сообщение.
    # Если это было сообщение бота, то его можно отредактировать.
    # Но так как это callback от кнопки "Мои заметки", лучше отправить новое сообщение.
    try:
        # Если предыдущее сообщение имело inline клавиатуру, оно будет отредактировано без нее
        # или удалено, если edit_text не сработает (например, если это не сообщение бота).
        # Для MVP проще отправить новое сообщение, чтобы избежать сложностей с редактированием.
        # await callback_query.message.delete() # Можно удалить предыдущее, если оно было с кнопками
        pass  # Пока не будем удалять, чтобы не усложнять.
    except Exception as e:
        logger.warning(f"Could not delete previous message for my_notes: {e}")

    await callback_query.answer("Загружаю заметки...")  # Ответ на callback, чтобы кнопка перестала "грузиться"

    # Отправляем каждую заметку отдельным сообщением с кнопкой "Удалить"
    # Это проще для MVP, чем формировать одно большое сообщение со сложной разметкой
    await callback_query.message.answer(response_text, parse_mode="HTML")  # Заголовок

    for note in notes:
        note_text_preview = note['corrected_text']
        if len(note_text_preview) > 150:  # Ограничим длину превью
            note_text_preview = note_text_preview[:150] + "..."

        note_date = note['created_at'].strftime("%d.%m.%Y %H:%M")

        message_per_note = (
            f"📌 {hbold(f'Заметка #{note['note_id']}')} от {note_date}\n"
            f"{hcode(note_text_preview)}\n"
        )
        if note.get('due_date'):
            message_per_note += f"💡 {hitalic('Срок до:')} {hcode(note['due_date'].strftime('%d.%m.%Y %H:%M'))}\n"

        await callback_query.message.answer(
            message_per_note,
            parse_mode="HTML",
            reply_markup=get_note_actions_keyboard(note['note_id'])
        )
    # TODO Комментарий
    # Если бы мы хотели отправить все в одном сообщении:
    # for i, note in enumerate(notes, 1):
    #     note_text_preview = note['corrected_text']
    #     if len(note_text_preview) > 100: # Ограничим длину превью
    #         note_text_preview = note_text_preview[:100] + "..."

    #     note_date = note['created_at'].strftime("%d.%m.%Y %H:%M")
    #     response_text += (
    #         f"{hbold(f'{i}. Заметка #{note['note_id']}')} ({note_date})\n"
    #         f"{hcode(note_text_preview)}\n"
    #         # Сюда нужно добавить кнопки для каждой заметки, что усложняет, если в одном сообщении
    #         # Поэтому для MVP каждая заметка - отдельное сообщение.
    #         f"--------------------\n"
    #     )
    # await callback_query.message.edit_text(response_text, parse_mode="HTML")


@router.callback_query(NoteCallbackFactory.filter(F.action == "delete"))
async def delete_note_handler(callback_query: CallbackQuery, callback_data: NoteCallbackFactory, state: FSMContext):
    """Обработчик удаления заметки."""
    await state.clear()  # На всякий случай
    note_id_to_delete = callback_data.note_id
    telegram_id = callback_query.from_user.id

    if note_id_to_delete is None:
        await callback_query.answer("Ошибка: ID заметки не найден.", show_alert=True)
        return

    # Проверим, существует ли заметка и принадлежит ли она пользователю (хотя delete_note это тоже делает)
    note = await db.get_note_by_id(note_id_to_delete, telegram_id)
    if not note:
        await callback_query.answer("Заметка не найдена или у вас нет прав на ее удаление.", show_alert=True)
        # Можно удалить сообщение с уже неактуальной кнопкой
        try:
            await callback_query.message.delete()
        except Exception:
            pass  # Если не получилось удалить, не страшно
        return

    deleted = await db.delete_note(note_id_to_delete, telegram_id)

    if deleted:
        await callback_query.answer("🗑️ Заметка удалена!")
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение после удаления заметки: {e}")
            await callback_query.message.edit_text(f"🗑️ Заметка #{note_id_to_delete} удалена.", reply_markup=None)
        # Отправляем главное меню новым сообщением
        await callback_query.message.answer(
            "Заметка удалена. Чем еще могу помочь?",  # Можно добавить это сообщение перед главным меню
            reply_markup=get_action_keyboard()
        )
    else:
        await callback_query.answer("❌ Не удалось удалить заметку. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "user_profile")
async def user_profile_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Профиль'."""
    await state.clear()  # На всякий случай очистим состояние
    telegram_id = callback_query.from_user.id

    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        # Этого не должно произойти, если get_or_create_user работает корректно
        await callback_query.answer("Профиль не найден. Попробуйте /start", show_alert=True)
        return
    # TODO Комментарий
    # Получаем количество активных заметок пользователя
    # get_notes_by_user возвращает список, нам нужно его количество.
    # Мы могли бы создать отдельную db функцию count_user_notes для эффективности,
    # но для MVP подойдет и так.
    user_notes = await db.get_notes_by_user(telegram_id, limit=MAX_NOTES_MVP + 1,
                                            archived=False)  # MAX_NOTES_MVP определен в db или main
    notes_count = len(user_notes)

    # Формируем информацию о профиле
    profile_info_parts = [
        f"{hbold('👤 Ваш профиль:')}",
        f"Telegram ID: {hcode(user_profile['telegram_id'])}"
    ]
    if user_profile.get('username'):
        profile_info_parts.append(f"Username: @{hitalic(user_profile['username'])}")
    if user_profile.get('first_name'):
        profile_info_parts.append(f"Имя: {hitalic(user_profile['first_name'])}")

    profile_info_parts.append(f"Зарегистрирован: {user_profile['created_at'].strftime('%d.%m.%Y %H:%M')}")

    # Информация о подписке (пока заглушка)
    subscription_status_text = "Бесплатная (MVP)"  # По умолчанию
    if user_profile.get('subscription_status') == 'active_paid':  # Пример для будущего
        subscription_status_text = f"Активная платная до {user_profile['subscription_expires_at'].strftime('%d.%m.%Y') if user_profile.get('subscription_expires_at') else 'N/A'}"
    elif user_profile.get('subscription_status') == 'free':
        subscription_status_text = "Бесплатная"

    profile_info_parts.append(f"Статус подписки: {hitalic(subscription_status_text)}")

    # Информация о заметках
    profile_info_parts.append(f"Сохраненных заметок: {hbold(notes_count)} из {MAX_NOTES_MVP} (MVP лимит)")
    # TODO Комментарий
    # Пользовательские данные, если есть (для MVP можно не выводить подробно)
    # custom_data = user_profile.get('custom_profile_data')
    # if custom_data:
    #     profile_info_parts.append(f"\n{hbold('Дополнительные данные:')}")
    #     for key, value in custom_data.items():
    #         profile_info_parts.append(f"- {key.capitalize()}: {hitalic(str(value))}")

    response_text = "\n".join(profile_info_parts)

    # Отвечаем на callback
    await callback_query.answer()

    # Отправляем сообщение с профилем и основной клавиатурой
    # Можно отредактировать предыдущее сообщение, если оно от этого бота
    # или отправить новое. Для простоты MVP - новое.
    try:
        # Попытка удалить предыдущее сообщение, если оно было с кнопками
        # await callback_query.message.delete()
        pass
    except Exception as e:
        logger.warning(f"Could not delete previous message for user_profile: {e}")

    await callback_query.message.answer(
        response_text,
        parse_mode="HTML",
        reply_markup=get_action_keyboard()  # Возвращаем к главному меню
    )
# --- LIFECYCLE HANDLERS ---
async def on_startup(dispatcher: Dispatcher):
    """Выполняется при запуске бота."""
    logger.info("Инициализация базы данных...")
    await db.setup_database_on_startup()  # Инициализация БД
    logger.info("Бот запущен и готов к работе!")


async def on_shutdown(dispatcher: Dispatcher):
    """Выполняется при остановке бота."""
    logger.info("Остановка бота...")
    await db.shutdown_database_on_shutdown()  # Закрытие соединений с БД
    logger.info("Бот остановлен.")


async def main():
    """Основная функция для запуска бота."""
    dp.include_router(router)

    # Регистрация lifecycle handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Запуск polling...")
    # Запуск long polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Принудительная остановка бота.")
    except Exception as e:
        logger.critical(f"Критическая ошибка во время выполнения: {e}", exc_info=True)