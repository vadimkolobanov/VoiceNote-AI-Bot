# main.py
import logging
import os
import json
import asyncio
from datetime import datetime  # Для работы с датами (например, для due_date)

from aiogram import Bot, Router, types, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hcode, hbold, hitalic
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения из .env

# Импорты из наших модулей
from inline_keyboards import (
    get_action_keyboard,
    get_confirm_save_keyboard,
    NoteCallbackFactory,
    get_note_actions_keyboard
)
from utills import recognize_speech_yandex, download_audio_content  # STT через aiohttp
from llm_processor import enhance_text_with_llm
import database_setup as db  # Модуль для работы с БД PostgreSQL

# --- Глобальные константы и конфигурация ---
MAX_NOTES_MVP = 5  # Лимит заметок для MVP

# --- КОНФИГУРАЦИЯ ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ БОТА И ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
DEEPSEEK_API_KEY_EXISTS = bool(os.environ.get("DEEPSEEK_API_KEY"))
YANDEX_STT_CONFIGURED = bool(
    os.environ.get("YANDEX_SPEECHKIT_API_KEY") and
    os.environ.get("YANDEX_SPEECHKIT_FOLDER_ID")
)

if not TG_BOT_TOKEN:
    logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
    exit("Критическая ошибка: TG_BOT_TOKEN не найден.")
if not DEEPSEEK_API_KEY_EXISTS:
    logger.warning("Переменная окружения DEEPSEEK_API_KEY не установлена! Функционал LLM будет недоступен.")
if not YANDEX_STT_CONFIGURED:
    logger.warning(
        "YANDEX_SPEECHKIT_API_KEY или YANDEX_SPEECHKIT_FOLDER_ID не установлены! Функционал Яндекс STT будет недоступен.")

bot = Bot(token=TG_BOT_TOKEN)
router = Router()
storage = MemoryStorage()  # Для FSM. В продакшене рассмотреть RedisStorage или PgStorage.
dp = Dispatcher(storage=storage)


# --- СОСТОЯНИЯ FSM ---
class NoteCreationStates(StatesGroup):
    awaiting_confirmation = State()  # Ожидание подтверждения сохранения заметки


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_or_create_user(tg_user: types.User):
    """
    Проверяет наличие пользователя в БД. Если нет - добавляет.
    Если есть - обновляет его данные (username, first_name и т.д.).
    Возвращает запись о пользователе из БД.
    """
    # add_or_update_user сама реализует логику UPSERT
    user_record = await db.add_or_update_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code
    )
    if not await db.get_user_profile(
            tg_user.id):  # Проверка на случай, если add_or_update_user не вернула запись при первой вставке (маловероятно)
        logger.info(f"Новый пользователь зарегистрирован: {tg_user.id}")
    return user_record


# --- ОБРАБОТЧИКИ КОМАНД ---
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await get_or_create_user(message.from_user)
    await message.answer(
        "🎤 Привет! Я **VoiceNote AI**, твой помощник для создания умных голосовых заметок.\n\n"
        "Просто отправь мне голосовое сообщение, и я:\n"
        "1. Распознаю речь (Yandex SpeechKit).\n"
        "2. Улучшу текст и извлеку важные детали с помощью AI (DeepSeek).\n"
        "3. Предложу сохранить заметку.\n\n"
        "Используй кнопки ниже для навигации или сразу отправляй голосовое!",
        reply_markup=get_action_keyboard(),
        parse_mode="MarkdownV2"  # или HTML, если используешь HTML теги
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    help_text = f"""
👋 Привет! Я **VoiceNote AI** – твой умный помощник для голосовых заметок.

Я использую технологию распознавания речи от Яндекса (Yandex SpeechKit) и продвинутый AI (DeepSeek) для анализа текста.

Вот что я умею:

🎤 **Создание заметок:**
   - Отправь мне голосовое сообщение.
   - Я распознаю твою речь, улучшу текст с помощью AI и извлеку важные детали (даты, задачи и т.д.).
   - Тебе будет предложено сохранить заметку.
   - В текущей MVP-версии действует лимит: **{MAX_NOTES_MVP} активных заметок** на пользователя.

📝 **Мои заметки:**
   - Нажми кнопку "📝 Мои заметки" в главном меню (появляется после /start).
   - Ты увидишь список своих последних {MAX_NOTES_MVP} заметок.
   - Каждую заметку можно **удалить**, нажав кнопку 🗑️ рядом с ней.

👤 **Профиль:**
   - Кнопка "👤 Профиль" в главном меню покажет твой Telegram ID, имя, дату регистрации, статус подписки (сейчас всегда "Бесплатная") и количество заметок.

🤖 **Основные команды:**
   - /start - Запустить бота или вернуться в главное меню.
   - /help - Показать это сообщение.

💡 **Советы:**
   - Говори четко и в относительно тихом месте для лучшего распознавания.
   - Если хочешь, чтобы AI извлек дату или задачу, старайся формулировать их явно в своем голосовом сообщении (например, "Завтра в 10 утра позвонить Ивану" или "Купить молоко после работы во вторник").

---
Если у тебя есть предложения по улучшению или ты нашел ошибку, пожалуйста, сообщи моему создателю! (Контакт: @useranybody - замени на свой)
"""
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)


# --- ОБРАБОТЧИК ГОЛОСОВЫХ СООБЩЕНИЙ ---
@router.message(F.voice)
async def handle_voice(message: types.Message, state: FSMContext):
    """Обработчик голосовых сообщений."""
    await get_or_create_user(message.from_user)
    voice = message.voice

    MIN_VOICE_DURATION_SEC = 1
    if voice.duration < MIN_VOICE_DURATION_SEC:
        logger.info(f"User {message.from_user.id} sent too short voice: {voice.duration}s")
        await message.reply(
            f"🎤 Ваше голосовое сообщение слишком короткое ({voice.duration} сек.).\n"
            f"Пожалуйста, запишите сообщение длительностью не менее {MIN_VOICE_DURATION_SEC} сек."
        )
        return

    file_id = voice.file_id
    voice_message_datetime = message.date  # Время отправки сообщения пользователем (в UTC)

    status_msg = await message.reply("✔️ Запись получена. Скачиваю и начинаю распознавание...")

    try:
        file_info = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
    except Exception as e:
        logger.exception(f"Error getting file info from Telegram for user {message.from_user.id}")
        await status_msg.edit_text(f"❌ Ошибка при получении файла от Telegram: {e}")
        return

    audio_bytes = await download_audio_content(file_url)
    if not audio_bytes:
        await status_msg.edit_text("❌ Не удалось скачать аудиофайл для обработки.")
        return

    if not YANDEX_STT_CONFIGURED:
        await status_msg.edit_text(
            "❌ Сервис распознавания речи временно недоступен. Пожалуйста, попробуйте позже или свяжитесь с поддержкой.")
        logger.error("Yandex STT not configured, but voice message received.")
        return

    raw_text_stt = await recognize_speech_yandex(audio_bytes)

    MIN_STT_TEXT_CHARS = 5
    MIN_STT_TEXT_WORDS = 1
    if not raw_text_stt or not raw_text_stt.strip():
        logger.info(f"Yandex STT for user {message.from_user.id} returned empty text.")
        await status_msg.edit_text(
            "❌ К сожалению, не удалось распознать речь в вашем сообщении.\n"
            "Попробуйте записать его четче или в более тихом месте."
        )
        return

    if len(raw_text_stt.strip()) < MIN_STT_TEXT_CHARS or len(raw_text_stt.strip().split()) < MIN_STT_TEXT_WORDS:
        logger.info(f"Yandex STT for user {message.from_user.id} returned too short text: '{raw_text_stt}'")
        await status_msg.edit_text(
            f"❌ Распознанный текст слишком короткий.\nРаспознано: {hcode(raw_text_stt)}\nПожалуйста, попробуйте еще раз."
        )
        return

    await status_msg.edit_text(
        f"🗣️ Распознано (Yandex STT):\n{hcode(raw_text_stt)}\n\n"
        "✨ Улучшаю текст и извлекаю детали с помощью LLM..."
    )

    llm_analysis_result_json = None  # Для сохранения в БД
    corrected_text_for_response = raw_text_stt  # Текст для отображения и сохранения, если LLM не сработает
    llm_info_for_user_display = f"{hitalic('LLM обработка пропущена (DEEPSEEK_API_KEY не настроен или LLM не используется).')}"

    if DEEPSEEK_API_KEY_EXISTS:
        llm_result_dict = await enhance_text_with_llm(raw_text_stt)
        if "error" in llm_result_dict:
            logger.error(f"LLM processing error for user {message.from_user.id}: {llm_result_dict['error']}")
            llm_info_for_user_display = f"⚠️ {hbold('Ошибка при обработке LLM:')} {hcode(llm_result_dict['error'])}"
        else:
            llm_analysis_result_json = llm_result_dict  # Сохраняем весь результат для БД
            corrected_text_for_response = llm_result_dict.get("corrected_text", raw_text_stt)

            details_parts = [f"{hbold('✨ Улучшенный текст (LLM):')}\n{hcode(corrected_text_for_response)}"]
            if llm_result_dict.get("task_description"):
                details_parts.append(f"📝 {hbold('Задача:')} {hitalic(llm_result_dict['task_description'])}")

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

            if len(details_parts) > 1:  # Если есть что-то кроме улучшенного текста
                llm_info_for_user_display = f"\n\n{hbold('🔍 Результаты AI анализа:')}\n" + "\n\n".join(details_parts)
            else:  # Только улучшенный текст
                llm_info_for_user_display = details_parts[0]

    await state.set_state(NoteCreationStates.awaiting_confirmation)
    await state.update_data(
        original_stt_text=raw_text_stt,
        corrected_text_for_save=corrected_text_for_response,  # Текст, который пойдет в БД
        llm_analysis_json=llm_analysis_result_json,
        original_audio_telegram_file_id=file_id,
        voice_message_date=voice_message_datetime
    )

    response_to_user = (
        f"{hbold('🎙️ Исходный текст (Yandex STT):')}\n{hcode(raw_text_stt)}\n\n"
        f"{llm_info_for_user_display}\n\n"
        f"{hbold('📊 Параметры аудио:')}\n"
        f"Длительность: {voice.duration} сек, Размер: {voice.file_size // 1024} КБ\n\n"
        "💾 Сохранить эту заметку?"
    )

    try:
        await status_msg.edit_text(
            response_to_user,
            reply_markup=get_confirm_save_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:  # Например, если сообщение слишком длинное для редактирования
        logger.warning(f"Could not edit status message, sending new one: {e}")
        await message.answer(
            response_to_user,
            reply_markup=get_confirm_save_keyboard(),
            parse_mode="HTML"
        )


# --- ОБРАБОТЧИКИ CALLBACK'ОВ ДЛЯ СОЗДАНИЯ ЗАМЕТКИ ---
@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "confirm_save_note")
async def confirm_save_note_handler(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    telegram_id = callback_query.from_user.id

    current_notes_list = await db.get_notes_by_user(telegram_id, limit=MAX_NOTES_MVP + 1, archived=False)
    if len(current_notes_list) >= MAX_NOTES_MVP:
        await callback_query.message.edit_text(
            f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок для MVP.\n"
            "Чтобы добавить новую, пожалуйста, удалите одну из существующих.",
            reply_markup=None
        )
        await callback_query.answer("Лимит заметок достигнут", show_alert=True)
        await state.clear()
        await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_action_keyboard())
        return

    original_stt_text = user_data.get("original_stt_text")
    corrected_text_to_save = user_data.get("corrected_text_for_save")
    llm_analysis_data = user_data.get("llm_analysis_json")  # dict или None
    audio_file_id = user_data.get("original_audio_telegram_file_id")
    note_creation_time = user_data.get("voice_message_date")  # Это datetime объект

    due_date_obj = None
    if llm_analysis_data and "dates_times" in llm_analysis_data and llm_analysis_data["dates_times"]:
        first_date_entry = llm_analysis_data["dates_times"][0]
        if "absolute_datetime_start" in first_date_entry:
            try:
                due_date_str = first_date_entry["absolute_datetime_start"]
                if due_date_str.endswith('Z'):  # Преобразование Z в +00:00 для fromisoformat
                    due_date_str = due_date_str[:-1] + "+00:00"
                due_date_obj = datetime.fromisoformat(due_date_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse due_date '{first_date_entry['absolute_datetime_start']}': {e}")

    note_id = await db.create_note(
        telegram_id=telegram_id,
        original_stt_text=original_stt_text,
        corrected_text=corrected_text_to_save,
        llm_analysis_json=llm_analysis_data,
        original_audio_telegram_file_id=audio_file_id,
        note_taken_at=note_creation_time,
        due_date=due_date_obj
    )

    if note_id:
        await callback_query.message.edit_text(
            f"✅ Заметка #{note_id} успешно сохранена!\n\n{hcode(corrected_text_to_save)}",
            parse_mode="HTML",
            reply_markup=None
        )
    else:
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при сохранении заметки в базу данных.",
            reply_markup=None
        )

    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_action_keyboard())


@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "cancel_save_note")
async def cancel_save_note_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("🚫 Сохранение отменено.", reply_markup=None)
    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_action_keyboard())


# --- ОБРАБОТЧИКИ ДЛЯ ПРОСМОТРА И УДАЛЕНИЯ ЗАМЕТОК ---
@router.callback_query(F.data == "my_notes")
async def my_notes_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    telegram_id = callback_query.from_user.id
    notes = await db.get_notes_by_user(telegram_id, limit=MAX_NOTES_MVP, offset=0, archived=False)

    await callback_query.answer("Загружаю заметки...")

    if not notes:
        await callback_query.message.answer("У вас пока нет сохраненных заметок.", reply_markup=get_action_keyboard())
        return

    await callback_query.message.answer(f"{hbold('📝 Ваши последние заметки:')}", parse_mode="HTML")

    for note_record in notes:
        text_preview = note_record['corrected_text']
        if len(text_preview) > 150:
            text_preview = text_preview[:150] + "..."

        # Используем note_taken_at или created_at для даты заметки
        # Отображаем в UTC, т.к. пока не реализована поддержка таймзон пользователя
        date_to_show_utc = note_record.get('note_taken_at') or note_record['created_at']
        date_str = date_to_show_utc.strftime("%d.%m.%Y %H:%M UTC")

        note_message = f"📌 {hbold(f'Заметка #{note_record['note_id']}')} от {date_str}\n{hcode(text_preview)}\n"

        if note_record.get('due_date'):
            due_date_utc = note_record['due_date']
            due_date_str_display = due_date_utc.strftime("%d.%m.%Y %H:%M UTC")
            note_message += f"💡 {hitalic('Срок до:')} {hcode(due_date_str_display)}\n"

        await callback_query.message.answer(
            note_message,
            parse_mode="HTML",
            reply_markup=get_note_actions_keyboard(note_record['note_id'])
        )
    # После вывода всех заметок, можно снова показать главное меню
    # await callback_query.message.answer("Выберите действие:", reply_markup=get_action_keyboard())


@router.callback_query(NoteCallbackFactory.filter(F.action == "delete"))
async def delete_note_handler(callback_query: CallbackQuery, callback_data: NoteCallbackFactory, state: FSMContext):
    await state.clear()
    note_id = callback_data.note_id
    telegram_id = callback_query.from_user.id

    if note_id is None:
        await callback_query.answer("Ошибка: ID заметки не найден.", show_alert=True)
        return

    note_exists = await db.get_note_by_id(note_id, telegram_id)
    if not note_exists:
        await callback_query.answer("Заметка не найдена или удалена.", show_alert=True)
        try:
            await callback_query.message.delete()
        except:
            pass
        return

    deleted_successfully = await db.delete_note(note_id, telegram_id)
    if deleted_successfully:
        await callback_query.answer("🗑️ Заметка удалена!")
        try:
            await callback_query.message.delete()
        except Exception:
            await callback_query.message.edit_text(f"🗑️ Заметка #{note_id} удалена.", reply_markup=None)
        await callback_query.message.answer("Заметка удалена. Чем еще могу помочь?", reply_markup=get_action_keyboard())
    else:
        await callback_query.answer("❌ Не удалось удалить заметку.", show_alert=True)


# --- ОБРАБОТЧИК ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ ---
@router.callback_query(F.data == "user_profile")
async def user_profile_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    telegram_id = callback_query.from_user.id
    user = await db.get_user_profile(telegram_id)

    if not user:
        await callback_query.answer("Профиль не найден. Попробуйте /start", show_alert=True)
        return

    user_notes_list = await db.get_notes_by_user(telegram_id, limit=MAX_NOTES_MVP + 1, archived=False)
    notes_count_actual = len(user_notes_list)

    profile_parts = [f"{hbold('👤 Ваш профиль:')}", f"Telegram ID: {hcode(user['telegram_id'])}"]
    if user.get('username'): profile_parts.append(f"Username: @{hitalic(user['username'])}")
    if user.get('first_name'): profile_parts.append(f"Имя: {hitalic(user['first_name'])}")
    profile_parts.append(f"Зарегистрирован: {user['created_at'].strftime('%d.%m.%Y %H:%M UTC')}")

    sub_status = "Бесплатная (MVP)"  # Заглушка
    profile_parts.append(f"Статус подписки: {hitalic(sub_status)}")
    profile_parts.append(f"Сохраненных заметок: {hbold(notes_count_actual)} из {MAX_NOTES_MVP} (MVP лимит)")

    response_text = "\n".join(profile_parts)
    await callback_query.answer()
    await callback_query.message.answer(response_text, parse_mode="HTML", reply_markup=get_action_keyboard())


# --- LIFECYCLE HANDLERS ---
async def on_startup(dispatcher: Dispatcher):
    logger.info("Инициализация базы данных...")
    await db.setup_database_on_startup()
    logger.info("Бот запущен и готов к работе!")


async def on_shutdown(dispatcher: Dispatcher):
    logger.info("Остановка бота...")
    await db.shutdown_database_on_shutdown()
    logger.info("Бот остановлен.")


async def main_bot_loop():
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    logger.info("Запуск polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main_bot_loop())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Принудительная остановка бота.")
    except Exception as e:
        logger.critical(f"Критическая ошибка во время выполнения: {e}", exc_info=True)