#!/usr/bin/env python3
"""
Генератор PDF-документа Технического Задания для VoiceNote AI.
Использует reportlab для создания профессионального документа.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Font Setup ---
# Try to register a font that supports Cyrillic
FONT_REGISTERED = False
FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
FONT_NAME_ITALIC = "Helvetica-Oblique"

# Try common Cyrillic-supporting fonts on Windows
font_paths = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf", "Arial"),
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/timesi.ttf", "TimesNewRoman"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/calibrii.ttf", "Calibri"),
]

for regular, bold, italic, name in font_paths:
    if os.path.exists(regular) and os.path.exists(bold):
        try:
            pdfmetrics.registerFont(TTFont(name, regular))
            pdfmetrics.registerFont(TTFont(f"{name}-Bold", bold))
            if os.path.exists(italic):
                pdfmetrics.registerFont(TTFont(f"{name}-Italic", italic))
            FONT_NAME = name
            FONT_NAME_BOLD = f"{name}-Bold"
            FONT_NAME_ITALIC = f"{name}-Italic" if os.path.exists(italic) else name
            FONT_REGISTERED = True
            print(f"Using font: {name}")
            break
        except Exception as e:
            print(f"Failed to register {name}: {e}")

if not FONT_REGISTERED:
    print("WARNING: No Cyrillic font found. PDF may not render Russian text correctly.")

# --- Colors ---
PRIMARY = HexColor("#1a237e")      # Deep indigo
SECONDARY = HexColor("#283593")    # Indigo
ACCENT = HexColor("#3949ab")       # Lighter indigo
TABLE_HEADER_BG = HexColor("#e8eaf6")  # Very light indigo
TABLE_ALT_BG = HexColor("#f5f5f5")     # Light grey
LIGHT_LINE = HexColor("#c5cae9")       # Indigo line
GREEN_CHECK = HexColor("#2e7d32")
RED_HIGH = HexColor("#c62828")
ORANGE_MED = HexColor("#e65100")
BLUE_LOW = HexColor("#1565c0")

# --- Output Path ---
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "TECHNICAL_REQUIREMENTS.pdf")


def create_styles():
    """Create all paragraph styles."""
    styles = getSampleStyleSheet()

    # Title page styles
    styles.add(ParagraphStyle(
        name='DocTitle',
        fontName=FONT_NAME_BOLD,
        fontSize=28,
        leading=34,
        alignment=TA_CENTER,
        textColor=PRIMARY,
        spaceAfter=6*mm,
    ))
    styles.add(ParagraphStyle(
        name='DocSubtitle',
        fontName=FONT_NAME,
        fontSize=16,
        leading=22,
        alignment=TA_CENTER,
        textColor=SECONDARY,
        spaceAfter=4*mm,
    ))
    styles.add(ParagraphStyle(
        name='DocMeta',
        fontName=FONT_NAME,
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=grey,
        spaceAfter=2*mm,
    ))

    # Section headers
    styles.add(ParagraphStyle(
        name='H1',
        fontName=FONT_NAME_BOLD,
        fontSize=18,
        leading=24,
        textColor=PRIMARY,
        spaceBefore=12*mm,
        spaceAfter=4*mm,
        borderWidth=0,
        borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        name='H2',
        fontName=FONT_NAME_BOLD,
        fontSize=14,
        leading=20,
        textColor=SECONDARY,
        spaceBefore=8*mm,
        spaceAfter=3*mm,
    ))
    styles.add(ParagraphStyle(
        name='H3',
        fontName=FONT_NAME_BOLD,
        fontSize=12,
        leading=16,
        textColor=ACCENT,
        spaceBefore=5*mm,
        spaceAfter=2*mm,
    ))

    # Body text
    styles.add(ParagraphStyle(
        name='Body',
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=2*mm,
    ))
    styles.add(ParagraphStyle(
        name='BodyBold',
        fontName=FONT_NAME_BOLD,
        fontSize=10,
        leading=14,
        spaceAfter=2*mm,
    ))
    styles.add(ParagraphStyle(
        name='BulletCustom',
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        leftIndent=8*mm,
        bulletIndent=3*mm,
        spaceAfter=1*mm,
    ))
    styles.add(ParagraphStyle(
        name='CodeBlock',
        fontName='Courier',
        fontSize=9,
        leading=12,
        leftIndent=5*mm,
        spaceAfter=2*mm,
        backColor=HexColor("#f5f5f5"),
    ))

    # Table cell styles
    styles.add(ParagraphStyle(
        name='TableCell',
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName=FONT_NAME_BOLD,
        fontSize=9,
        leading=12,
        textColor=PRIMARY,
    ))
    styles.add(ParagraphStyle(
        name='TableCellSmall',
        fontName=FONT_NAME,
        fontSize=8,
        leading=10,
    ))

    # TOC
    styles.add(ParagraphStyle(
        name='TOCEntry',
        fontName=FONT_NAME,
        fontSize=11,
        leading=18,
        leftIndent=5*mm,
        spaceAfter=1*mm,
    ))

    return styles


def make_table(headers, rows, col_widths=None, style_override=None):
    """Create a styled table."""
    s = create_styles()

    header_cells = [Paragraph(h, s['TableHeader']) for h in headers]
    data = [header_cells]

    for row in rows:
        data.append([Paragraph(str(cell), s['TableCell']) for cell in row])

    if col_widths is None:
        col_widths = [170*mm / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)

    base_style = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_LINE),
        ('LINEBELOW', (0, 0), (-1, 0), 1, PRIMARY),
    ]

    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            base_style.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT_BG))

    if style_override:
        base_style.extend(style_override)

    t.setStyle(TableStyle(base_style))
    return t


def priority_text(p):
    if p == "Высокий":
        return f'<font color="#c62828">{p}</font>'
    elif p == "Средний":
        return f'<font color="#e65100">{p}</font>'
    else:
        return f'<font color="#1565c0">{p}</font>'


def build_document():
    """Build the complete PDF document."""
    s = create_styles()
    story = []

    # =============================================
    # TITLE PAGE
    # =============================================
    story.append(Spacer(1, 50*mm))
    story.append(Paragraph("ТЕХНИЧЕСКОЕ ЗАДАНИЕ", s['DocTitle']))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('на разработку мобильного приложения<br/>"VoiceNote AI"', s['DocSubtitle']))
    story.append(Spacer(1, 15*mm))
    story.append(HRFlowable(width="60%", thickness=1, color=LIGHT_LINE, spaceAfter=10*mm))
    story.append(Paragraph("Версия: 1.0", s['DocMeta']))
    story.append(Paragraph("Дата: 17.04.2026", s['DocMeta']))
    story.append(Paragraph("Статус: Утверждено", s['DocMeta']))
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("Для внутреннего использования<br/>Команда разработки VoiceNote AI", s['DocMeta']))
    story.append(PageBreak())

    # =============================================
    # TABLE OF CONTENTS
    # =============================================
    story.append(Paragraph("СОДЕРЖАНИЕ", s['H1']))
    story.append(Spacer(1, 3*mm))

    toc_items = [
        "1. Общие сведения",
        "2. Назначение и цели",
        "3. Требования к функциональности",
        "4. Архитектура системы",
        "5. Описание экранов и UX-потоков",
        "6. API-контракты",
        "7. Схема базы данных",
        "8. Интеграции с внешними сервисами",
        "9. Требования к безопасности",
        "10. Нефункциональные требования",
        "11. План реализации",
        "12. Глоссарий",
    ]
    for item in toc_items:
        story.append(Paragraph(item, s['TOCEntry']))

    story.append(PageBreak())

    # =============================================
    # 1. ОБЩИЕ СВЕДЕНИЯ
    # =============================================
    story.append(Paragraph("1. ОБЩИЕ СВЕДЕНИЯ", s['H1']))

    story.append(Paragraph("1.1 Наименование проекта", s['H2']))
    story.append(Paragraph('Мобильное приложение "VoiceNote AI" для платформ iOS и Android.', s['Body']))

    story.append(Paragraph("1.2 Основание для разработки", s['H2']))
    story.append(Paragraph(
        "Расширение существующего Telegram-бота VoiceNote AI Bot (Python/FastAPI/Aiogram) "
        "до полноценного мобильного приложения с монетизацией.", s['Body']))

    story.append(Paragraph("1.3 Текущее состояние", s['H2']))
    story.append(Paragraph("Существует работающий Telegram-бот с REST API (FastAPI), включающий:", s['Body']))

    current_features = [
        "Авторизация через Telegram OAuth и одноразовые коды",
        "CRUD заметок с AI-классификацией интентов (DeepSeek LLM)",
        "Распознавание голосовых сообщений (Yandex SpeechKit)",
        "Трекер привычек с LLM-парсингом",
        "Напоминания и повторяющиеся задачи (APScheduler)",
        "Списки покупок с шарингом",
        "Дни рождения",
        "Система геймификации (XP, уровни, 18 достижений)",
        "Утренний дайджест с погодой",
        "Push-уведомления (Firebase FCM)",
        "Профиль с настройками (часовой пояс, город, дайджест)",
    ]
    for f in current_features:
        story.append(Paragraph(f"- {f}", s['BulletCustom']))

    story.append(Paragraph("1.4 Технологический стек", s['H2']))

    story.append(Paragraph("<b>Бэкенд (существующий, расширяемый):</b>", s['Body']))
    backend_items = [
        "Python 3.12+, FastAPI, Uvicorn",
        "PostgreSQL (asyncpg), Redis",
        "APScheduler, Aiogram 3.x",
        "DeepSeek API (LLM), Yandex SpeechKit (STT)",
        "Firebase FCM (push-уведомления)",
    ]
    for item in backend_items:
        story.append(Paragraph(f"- {item}", s['BulletCustom']))

    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("<b>Мобильное приложение (новое):</b>", s['Body']))

    mobile_stack = make_table(
        ["Компонент", "Технология", "Назначение"],
        [
            ["Фреймворк", "Flutter (Dart)", "Кроссплатформенная разработка"],
            ["State management", "Riverpod + кодогенерация", "Управление состоянием"],
            ["HTTP-клиент", "Dio", "API-вызовы, interceptors для JWT"],
            ["Навигация", "go_router", "Декларативный роутинг с guards"],
            ["Хранение токенов", "flutter_secure_storage", "Keychain (iOS) / Keystore (Android)"],
            ["Аудио", "record", "Запись голоса M4A/AAC"],
            ["Push", "firebase_messaging", "FCM + локальные уведомления"],
            ["WebView", "webview_flutter", "Оплата через ЮКасса"],
            ["Кэш", "Hive", "Локальное кэширование данных"],
            ["Модели", "freezed + json_serializable", "Иммутабельность + кодогенерация"],
        ],
        col_widths=[35*mm, 50*mm, 85*mm]
    )
    story.append(mobile_stack)

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("<b>Платежи:</b> ЮКасса (карты, SBP, YandexPay)", s['Body']))
    story.append(Paragraph("<b>Векторная БД:</b> pgvector (расширение PostgreSQL)", s['Body']))

    story.append(PageBreak())

    # =============================================
    # 2. НАЗНАЧЕНИЕ И ЦЕЛИ
    # =============================================
    story.append(Paragraph("2. НАЗНАЧЕНИЕ И ЦЕЛИ", s['H1']))

    story.append(Paragraph("2.1 Назначение", s['H2']))
    story.append(Paragraph(
        "Мобильное приложение для управления заметками, задачами и привычками "
        "с помощью голосового ввода и AI.", s['Body']))

    purposes = [
        "Создание заметок голосом и текстом",
        "Автоматическая классификация контента (заметка / напоминание / список покупок)",
        "Отслеживание привычек с визуальной статистикой",
        "Напоминания и утренний дайджест с погодой",
        "Персональный AI-агент с векторной памятью (премиум)",
    ]
    for p in purposes:
        story.append(Paragraph(f"- {p}", s['BulletCustom']))

    story.append(Paragraph("2.2 Цели проекта", s['H2']))
    goals = [
        "Создать кроссплатформенное мобильное приложение (iOS + Android)",
        "Интегрировать систему платежей ЮКасса",
        "Реализовать премиум-фичу: персональный AI-агент с векторной памятью",
        "Опубликовать приложение в Google Play и App Store",
    ]
    for i, g in enumerate(goals, 1):
        story.append(Paragraph(f"{i}. {g}", s['BulletCustom']))

    story.append(Paragraph("2.3 Целевая аудитория", s['H2']))
    audience = [
        "Русскоязычные пользователи 18-45 лет",
        "Люди, активно использующие голосовой ввод",
        "Пользователи, стремящиеся к продуктивности и трекингу привычек",
    ]
    for a in audience:
        story.append(Paragraph(f"- {a}", s['BulletCustom']))

    story.append(Paragraph("2.4 Модель монетизации", s['H2']))
    story.append(Paragraph("<b>Бесплатный тариф:</b> Все базовые функции (заметки, привычки, "
                           "напоминания, дни рождения, покупки, достижения).", s['Body']))
    story.append(Paragraph("<b>Premium (подписка):</b> Персональный AI-агент с векторной памятью.", s['Body']))

    pricing = make_table(
        ["Тариф", "Цена", "Экономия"],
        [
            ["Месяц", "299 руб.", "-"],
            ["Год", "2 390 руб.", "~33%"],
        ],
        col_widths=[50*mm, 60*mm, 60*mm]
    )
    story.append(pricing)

    story.append(PageBreak())

    # =============================================
    # 3. ТРЕБОВАНИЯ К ФУНКЦИОНАЛЬНОСТИ
    # =============================================
    story.append(Paragraph("3. ТРЕБОВАНИЯ К ФУНКЦИОНАЛЬНОСТИ", s['H1']))

    # 3.1 AUTH
    story.append(Paragraph("3.1 Модуль авторизации (FR-AUTH)", s['H2']))
    auth_reqs = [
        ["FR-AUTH-01", "Авторизация по одноразовому коду из Telegram-бота", "Высокий"],
        ["FR-AUTH-02", "Авторизация через Telegram Login Widget (WebView)", "Высокий"],
        ["FR-AUTH-03", "JWT access token (15 мин) + refresh token (30 дней)", "Высокий"],
        ["FR-AUTH-04", "Автообновление access token через Dio interceptor", "Высокий"],
        ["FR-AUTH-05", "Безопасное хранение токенов (flutter_secure_storage)", "Высокий"],
        ["FR-AUTH-06", "Логаут с отзывом refresh token", "Высокий"],
        ["FR-AUTH-07", "Автопереход на логин при истечении refresh token", "Средний"],
    ]
    for r in auth_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], auth_reqs, [22*mm, 120*mm, 28*mm]))

    # 3.2 NOTES
    story.append(Paragraph("3.2 Модуль заметок (FR-NOTES)", s['H2']))
    notes_reqs = [
        ["FR-NOTES-01", "Создание текстовой заметки с AI-классификацией", "Высокий"],
        ["FR-NOTES-02", "Создание заметки голосовым вводом (запись -> STT -> AI)", "Высокий"],
        ["FR-NOTES-03", "Список заметок с пагинацией и pull-to-refresh", "Высокий"],
        ["FR-NOTES-04", "Три сегмента: Активные / Архив / Покупки", "Высокий"],
        ["FR-NOTES-05", "Детальный просмотр (текст, категория, дата, повтор)", "Высокий"],
        ["FR-NOTES-06", "Редактирование текста заметки", "Высокий"],
        ["FR-NOTES-07", "Отметка заметки как выполненной", "Высокий"],
        ["FR-NOTES-08", "Архивирование / разархивирование", "Средний"],
        ["FR-NOTES-09", "Удаление заметки", "Средний"],
        ["FR-NOTES-10", "AI-семантический поиск по заметкам", "Средний"],
        ["FR-NOTES-11", "Свайп-жесты (архив, удаление)", "Средний"],
        ["FR-NOTES-12", "Цветная метка категории", "Низкий"],
        ["FR-NOTES-13", "Шаринг заметки по ссылке", "Низкий"],
    ]
    for r in notes_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], notes_reqs, [24*mm, 118*mm, 28*mm]))

    # 3.3 VOICE
    story.append(Paragraph("3.3 Модуль голосового ввода (FR-VOICE)", s['H2']))
    voice_reqs = [
        ["FR-VOICE-01", "Запись аудио через микрофон (пакет record)", "Высокий"],
        ["FR-VOICE-02", "Визуальная индикация записи (пульсирующий круг)", "Высокий"],
        ["FR-VOICE-03", "Загрузка аудио на сервер (POST /api/v1/voice/recognize)", "Высокий"],
        ["FR-VOICE-04", "Конвертация M4A -> OGG Opus через ffmpeg на сервере", "Высокий"],
        ["FR-VOICE-05", "Распознавание речи через Yandex SpeechKit", "Высокий"],
        ["FR-VOICE-06", "Лимит для бесплатных: 15 распознаваний / день", "Средний"],
        ["FR-VOICE-07", "Отображение прогресса распознавания", "Средний"],
    ]
    for r in voice_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], voice_reqs, [24*mm, 118*mm, 28*mm]))

    # 3.4 HABITS
    story.append(Paragraph("3.4 Модуль привычек (FR-HABITS)", s['H2']))
    habits_reqs = [
        ["FR-HABITS-01", "Список активных привычек с текущим streak", "Высокий"],
        ["FR-HABITS-02", "Создание через описание естественным языком (LLM)", "Высокий"],
        ["FR-HABITS-03", "Отметка: выполнено / пропущено", "Высокий"],
        ["FR-HABITS-04", "Еженедельная визуальная статистика (сетка Пн-Вс)", "Средний"],
        ["FR-HABITS-05", "Удаление привычки", "Средний"],
        ["FR-HABITS-06", "Иконки для типов привычек", "Низкий"],
    ]
    for r in habits_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], habits_reqs, [24*mm, 118*mm, 28*mm]))

    story.append(PageBreak())

    # 3.5 AI
    story.append(Paragraph("3.5 Модуль AI-агента (FR-AI) -- PREMIUM", s['H2']))
    ai_reqs = [
        ["FR-AI-01", "Чат-интерфейс с AI-агентом (пузыри сообщений)", "Высокий"],
        ["FR-AI-02", "Отправка текстовых запросов агенту", "Высокий"],
        ["FR-AI-03", "Ответы с контекстом из заметок (RAG)", "Высокий"],
        ["FR-AI-04", "Векторный поиск pgvector (cosine similarity)", "Высокий"],
        ["FR-AI-05", "Автосоздание embeddings при создании заметки", "Высокий"],
        ["FR-AI-06", "Хранение истории диалогов", "Средний"],
        ["FR-AI-07", "Извлечение и хранение фактов о пользователе", "Средний"],
        ["FR-AI-08", "Управление памятью: просмотр, удаление, сброс", "Средний"],
        ["FR-AI-09", "Paywall при попытке доступа без подписки", "Высокий"],
        ["FR-AI-10", 'Индикатор "печатает..." при ожидании ответа', "Низкий"],
    ]
    for r in ai_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], ai_reqs, [22*mm, 120*mm, 28*mm]))

    # 3.6 PAY
    story.append(Paragraph("3.6 Модуль платежей (FR-PAY)", s['H2']))
    pay_reqs = [
        ["FR-PAY-01", "Экран Paywall с описанием премиум-функций и ценами", "Высокий"],
        ["FR-PAY-02", "Создание платежа через ЮКасса API (серверная сторона)", "Высокий"],
        ["FR-PAY-03", "Оплата через WebView (redirect на ЮКасса)", "Высокий"],
        ["FR-PAY-04", "Webhook: payment.succeeded, refund.succeeded", "Высокий"],
        ["FR-PAY-05", "Автоактивация подписки при успешной оплате", "Высокий"],
        ["FR-PAY-06", "Статус подписки в профиле (план, дата окончания)", "Высокий"],
        ["FR-PAY-07", "Отмена автопродления подписки", "Средний"],
        ["FR-PAY-08", "Deep link возврат (voicenote://payment/success)", "Средний"],
        ["FR-PAY-09", "Ежедневная проверка истёкших подписок (scheduler)", "Высокий"],
        ["FR-PAY-10", "Уведомление за 3 дня до окончания подписки", "Низкий"],
    ]
    for r in pay_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], pay_reqs, [22*mm, 120*mm, 28*mm]))

    # 3.7 PROFILE
    story.append(Paragraph("3.7 Модуль профиля (FR-PROFILE)", s['H2']))
    profile_reqs = [
        ["FR-PROFILE-01", "Просмотр профиля (имя, аватар, уровень, XP)", "Высокий"],
        ["FR-PROFILE-02", "Настройка часового пояса", "Высокий"],
        ["FR-PROFILE-03", "Настройка города (для погоды)", "Средний"],
        ["FR-PROFILE-04", "Настройка утреннего дайджеста (вкл/выкл, время)", "Средний"],
        ["FR-PROFILE-05", "Настройка времени напоминаний по умолчанию", "Средний"],
        ["FR-PROFILE-06", "Просмотр достижений (заработанные / заблокированные)", "Средний"],
        ["FR-PROFILE-07", "Просмотр статуса подписки", "Высокий"],
    ]
    for r in profile_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], profile_reqs, [26*mm, 116*mm, 28*mm]))

    # 3.8 SHOP + 3.9 BIRTH + 3.10 PUSH
    story.append(Paragraph("3.8 Модуль списков покупок (FR-SHOP)", s['H2']))
    shop_reqs = [
        ["FR-SHOP-01", "Просмотр активного списка покупок", "Высокий"],
        ["FR-SHOP-02", "Отметка товаров (чекбокс)", "Высокий"],
        ["FR-SHOP-03", "Добавление товара в список", "Средний"],
        ["FR-SHOP-04", "Архивирование списка", "Средний"],
    ]
    for r in shop_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], shop_reqs, [24*mm, 118*mm, 28*mm]))

    story.append(Paragraph("3.9 Модуль дней рождения (FR-BIRTH)", s['H2']))
    birth_reqs = [
        ["FR-BIRTH-01", "Просмотр списка дней рождения (пагинация)", "Средний"],
        ["FR-BIRTH-02", "Добавление дня рождения (имя + дата)", "Средний"],
        ["FR-BIRTH-03", "Удаление записи", "Средний"],
    ]
    for r in birth_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], birth_reqs, [24*mm, 118*mm, 28*mm]))

    story.append(Paragraph("3.10 Push-уведомления (FR-PUSH)", s['H2']))
    push_reqs = [
        ["FR-PUSH-01", "Регистрация FCM-токена при запуске", "Высокий"],
        ["FR-PUSH-02", "Push при срабатывании напоминания", "Высокий"],
        ["FR-PUSH-03", "Навигация к заметке при нажатии на push", "Средний"],
        ["FR-PUSH-04", "Удаление FCM-токена при логауте", "Средний"],
    ]
    for r in push_reqs:
        r[2] = priority_text(r[2])
    story.append(make_table(["ID", "Требование", "Приоритет"], push_reqs, [24*mm, 118*mm, 28*mm]))

    story.append(PageBreak())

    # =============================================
    # 4. АРХИТЕКТУРА СИСТЕМЫ
    # =============================================
    story.append(Paragraph("4. АРХИТЕКТУРА СИСТЕМЫ", s['H1']))

    story.append(Paragraph("4.1 Общая схема", s['H2']))
    arch_text = """Flutter App (iOS/Android)
  |  HTTPS / REST API
  v
FastAPI Backend (Python)
  |
  +-- PostgreSQL (asyncpg) + pgvector
  +-- Redis (кэш, FSM)
  +-- APScheduler (напоминания, дайджест)
  |
  +-- DeepSeek API (LLM)
  +-- Yandex SpeechKit (STT)
  +-- Firebase FCM (push)
  +-- ЮКасса API (платежи)
  +-- Open-Meteo (погода)"""
    story.append(Paragraph(arch_text.replace('\n', '<br/>'), s['CodeBlock']))

    story.append(Paragraph("4.2 Архитектура мобильного приложения", s['H2']))
    story.append(Paragraph("Паттерн: <b>Feature-first + Repository + Riverpod</b>", s['Body']))

    arch_mobile = """Screen (StatelessWidget)
  v
Provider (@riverpod AsyncNotifier)
  v
Repository (бизнес-логика, кэш/сеть)
  v
Remote Source (Dio HTTP calls)
  v
REST API (/api/v1/*)"""
    story.append(Paragraph(arch_mobile.replace('\n', '<br/>'), s['CodeBlock']))

    story.append(Paragraph(
        "Каждая фича (auth, notes, habits, ai_agent, profile, payments, shopping_list, birthdays) "
        "-- отдельный модуль со своими data/, domain/, presentation/ слоями.", s['Body']))

    story.append(Paragraph("4.3 Навигация", s['H2']))
    story.append(Paragraph("4 вкладки в BottomNavigationBar:", s['Body']))
    nav_items = [
        "1. Заметки (главная)",
        "2. Привычки",
        "3. AI Агент (premium)",
        "4. Профиль",
    ]
    for n in nav_items:
        story.append(Paragraph(n, s['BulletCustom']))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Отдельные экраны (push-навигация):", s['Body']))
    push_screens = [
        "Детали заметки, Создание заметки, Создание привычки",
        "Paywall, Оплата (WebView)",
        "Достижения, Настройки, Управление памятью AI",
    ]
    for ps in push_screens:
        story.append(Paragraph(f"- {ps}", s['BulletCustom']))

    story.append(PageBreak())

    # =============================================
    # 5. ОПИСАНИЕ ЭКРАНОВ
    # =============================================
    story.append(Paragraph("5. ОПИСАНИЕ ЭКРАНОВ И UX-ПОТОКОВ", s['H1']))

    screens = [
        ("5.1 Экран логина (LoginScreen)",
         "Первый экран при неавторизованном состоянии.",
         ["Логотип и название 'VoiceNote AI'",
          "Инструкция: откройте @VoiceNoteBot -> /login -> введите код",
          "Поле ввода 6-значного кода + кнопка 'Войти'",
          "Разделитель 'или' + кнопка 'Войти через Telegram' (WebView)"],
         "Пользователь вводит код -> POST /auth/code -> access + refresh token -> SecureStorage -> главный экран"),

        ("5.2 Экран заметок (NotesListScreen)",
         "Главный экран. Список заметок с созданием.",
         ["AppBar: 'VoiceNote AI' + иконка поиска",
          "SegmentedControl: Активные | Архив | Покупки",
          "ListView с NoteCard (заголовок, дата, категория, чекбокс)",
          "Нижняя панель: кнопка микрофона (пульсирующая) + текстовое поле",
          "Shimmer-загрузка, Pull-to-refresh",
          "Свайп влево: архив, свайп вправо: удаление",
          "Long press на микрофон: запись; отпускание: отправка"],
         None),

        ("5.3 Экран деталей заметки (NoteDetailScreen)", None,
         ["Заголовок (summary_text), полный текст (редактируемый)",
          "Метаданные: категория (dropdown), дата, правило повтора",
          "Кнопки: Выполнено, Архив, Удалить, Поделиться ссылкой"],
         None),

        ("5.4 Экран привычек (HabitsScreen)", None,
         ["Дата 'Сегодня, DD MMMM'",
          "HabitCard: иконка, название, streak, кнопка Done!",
          "Еженедельная сетка (Пн-Вс): заполненные/пустые квадраты",
          "Кнопка '+ Создать' в AppBar"],
         None),

        ("5.5 Экран AI-агента (AiChatScreen) -- PREMIUM",
         "Для подписчиков: чат-интерфейс. Для бесплатных: PaywallScreen.",
         ["ListView с ChatBubble (user/assistant)",
          "TextField + кнопка отправки",
          "Кнопка 'Память' -> MemoryFactsScreen",
          "Индикатор 'печатает...' при ожидании"],
         None),

        ("5.6 Экран Paywall (PaywallScreen)", None,
         ["Иконка/иллюстрация + заголовок 'VoiceNote Premium'",
          "Список преимуществ (bullets)",
          "Два варианта: Месяц 299р / Год 2390р (-33%)",
          "Кнопка 'Подписаться' + текст 'Отмена в любой момент'"],
         "Tap -> POST /payments/create -> confirmation_url -> WebView ЮКасса -> webhook -> подписка активна -> возврат"),

        ("5.7 Экран профиля (ProfileScreen)", None,
         ["Аватар, имя, username",
          "Прогресс-бар уровня: 'Уровень N  XXX/YYY XP'",
          "Секция 'Достижения' (grid)",
          "Секция 'Настройки': часовой пояс, город, дайджест",
          "Секция 'Подписка': план, дата, управление",
          "Кнопка 'Выйти'"],
         None),
    ]

    for title, desc, elements, flow in screens:
        story.append(Paragraph(title, s['H2']))
        if desc:
            story.append(Paragraph(desc, s['Body']))
        if elements:
            for el in elements:
                story.append(Paragraph(f"- {el}", s['BulletCustom']))
        if flow:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(f"<b>Поток:</b> {flow}", s['Body']))

    story.append(PageBreak())

    # =============================================
    # 6. API-КОНТРАКТЫ
    # =============================================
    story.append(Paragraph("6. API-КОНТРАКТЫ", s['H1']))

    api_sections = [
        ("6.1 Авторизация", [
            ["POST", "/api/v1/auth/code", "Логин по коду", "{code}", "Token"],
            ["POST", "/api/v1/auth/login", "Telegram OAuth", "TelegramLoginData", "Token"],
            ["POST", "/api/v1/auth/refresh", "Обновление токенов", "{refresh_token}", "Token"],
            ["POST", "/api/v1/auth/logout", "Логаут", "{refresh_token}", "204"],
        ]),
        ("6.2 Профиль", [
            ["GET", "/api/v1/profile/me", "Получить профиль", "-", "UserProfile"],
            ["PUT", "/api/v1/profile/me", "Обновить профиль", "ProfileUpdate", "UserProfile"],
            ["GET", "/api/v1/profile/me/achievements", "Достижения", "-", "list[Achievement]"],
            ["POST", "/api/v1/profile/devices", "Регистрация FCM", "{fcm_token, platform}", "201"],
            ["DELETE", "/api/v1/profile/devices", "Удаление FCM", "{fcm_token}", "204"],
        ]),
        ("6.3 Заметки", [
            ["POST", "/api/v1/notes", "Создать заметку", "{text}", "Note"],
            ["GET", "/api/v1/notes", "Список", "?page&per_page&archived", "Paginated"],
            ["GET", "/api/v1/notes/{id}", "Получить одну", "-", "Note"],
            ["PUT", "/api/v1/notes/{id}", "Обновить текст", "{text}", "Note"],
            ["POST", "/api/v1/notes/{id}/complete", "Выполнить", "-", "Note"],
            ["POST", "/api/v1/notes/{id}/unarchive", "Разархивировать", "-", "Note"],
            ["DELETE", "/api/v1/notes/{id}", "Удалить", "-", "204"],
            ["POST", "/api/v1/notes/search", "AI-поиск", "{query}", "list[Note]"],
        ]),
        ("6.4 Голос", [
            ["POST", "/api/v1/voice/recognize", "Загрузка аудио", "multipart (audio)", "Note"],
        ]),
        ("6.5 Привычки", [
            ["GET", "/api/v1/habits", "Список привычек", "-", "list[Habit]"],
            ["POST", "/api/v1/habits", "Создать (LLM)", "{text}", "list[Habit]"],
            ["POST", "/api/v1/habits/{id}/track", "Отметить", "{date?, status}", "200"],
            ["GET", "/api/v1/habits/{id}/stats", "Статистика", "?days=7", "list[Stats]"],
            ["DELETE", "/api/v1/habits/{id}", "Удалить", "-", "204"],
        ]),
        ("6.6 Платежи", [
            ["POST", "/api/v1/payments/create", "Создать платёж", "{plan}", "{confirmation_url}"],
            ["POST", "/api/v1/payments/webhook", "Webhook ЮКасса", "Event", "200"],
            ["GET", "/api/v1/payments/subscription", "Статус подписки", "-", "Subscription"],
            ["POST", "/api/v1/payments/cancel", "Отмена", "-", "Subscription"],
        ]),
        ("6.7 AI-память (Premium)", [
            ["POST", "/api/v1/memory/chat", "Сообщение агенту", "{message}", "{reply}"],
            ["GET", "/api/v1/memory/conversations", "История", "?limit=50", "list[Message]"],
            ["GET", "/api/v1/memory/facts", "Факты", "-", "list[Fact]"],
            ["DELETE", "/api/v1/memory/facts/{id}", "Удалить факт", "-", "204"],
            ["DELETE", "/api/v1/memory/reset", "Сброс памяти", "-", "204"],
        ]),
        ("6.8 Списки покупок", [
            ["GET", "/api/v1/shopping-list", "Активный список", "-", "ShoppingList"],
            ["POST", "/api/v1/shopping-list/items", "Переключить товар", "{index, checked}", "ShoppingList"],
            ["POST", "/api/v1/shopping-list/items/add", "Добавить товар", "{item_name}", "ShoppingList"],
            ["POST", "/api/v1/shopping-list/archive", "Архивировать", "-", "204"],
        ]),
        ("6.9 Дни рождения", [
            ["GET", "/api/v1/birthdays", "Список", "?page&per_page", "Paginated"],
            ["POST", "/api/v1/birthdays", "Создать", "{name, date}", "Birthday"],
            ["DELETE", "/api/v1/birthdays/{id}", "Удалить", "-", "204"],
        ]),
    ]

    for section_title, rows in api_sections:
        story.append(Paragraph(section_title, s['H2']))
        story.append(make_table(
            ["Метод", "Путь", "Описание", "Тело", "Ответ"],
            rows,
            col_widths=[14*mm, 50*mm, 36*mm, 38*mm, 32*mm]
        ))

    story.append(PageBreak())

    # =============================================
    # 7. СХЕМА БАЗЫ ДАННЫХ
    # =============================================
    story.append(Paragraph("7. СХЕМА БАЗЫ ДАННЫХ", s['H1']))

    story.append(Paragraph("7.1 Существующие таблицы", s['H2']))
    existing_tables = [
        ["users", "telegram_id PK, username, first_name, is_vip, timezone, city_name, xp, level, daily_digest_*"],
        ["notes", "note_id PK, telegram_id FK, summary_text, corrected_text, category, due_date, recurrence_rule, llm_analysis_json"],
        ["note_shares", "Связи шаринга заметок между пользователями"],
        ["birthdays", "id PK, user_telegram_id FK, person_name, birth_day, birth_month, birth_year"],
        ["habits", "id PK, user_telegram_id FK, name, frequency_rule, reminder_time, is_active"],
        ["habit_trackings", "id PK, habit_id FK, track_date, status (done/skipped)"],
        ["achievements", "code PK, name, description, icon, xp_reward"],
        ["user_achievements", "user_telegram_id FK, achievement_code FK"],
        ["user_devices", "FCM-токены для push (fcm_token, platform)"],
        ["mobile_activation_codes", "Одноразовые коды для входа"],
        ["user_actions", "Аналитика: action_type, metadata JSONB"],
    ]
    story.append(make_table(["Таблица", "Ключевые поля"], existing_tables, [35*mm, 135*mm]))

    story.append(Paragraph("7.2 Новые таблицы", s['H2']))
    new_tables = [
        ["refresh_tokens", "token_hash TEXT UNIQUE, user_telegram_id FK, expires_at, revoked_at"],
        ["subscriptions", "user_telegram_id FK, plan (monthly/yearly), status, started_at, expires_at, auto_renew"],
        ["payments", "yookassa_payment_id UNIQUE, amount DECIMAL, currency, status, plan, metadata JSONB"],
        ["note_embeddings", "note_id FK UNIQUE, embedding vector(1536), model_version. HNSW index"],
        ["ai_conversations", "user_telegram_id FK, role (user/assistant), content, context_note_ids INTEGER[]"],
        ["user_memory_facts", "fact_text, source_type, embedding vector(1536). HNSW index"],
    ]
    story.append(make_table(["Таблица", "Ключевые поля"], new_tables, [35*mm, 135*mm]))

    story.append(PageBreak())

    # =============================================
    # 8. ИНТЕГРАЦИИ
    # =============================================
    story.append(Paragraph("8. ИНТЕГРАЦИИ С ВНЕШНИМИ СЕРВИСАМИ", s['H1']))

    integrations = [
        ("8.1 ЮКасса (платежи)", [
            "SDK: yookassa (Python)",
            "Тестовый режим: Sandbox с тестовыми картами",
            "Методы оплаты: банковские карты, SBP, YandexPay",
            "Webhook: POST /api/v1/payments/webhook, верификация IP ЮКасса",
            "IP-адреса: 185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, 77.75.154.128/25",
            "Чеки: обязательны по 54-ФЗ (fiscal receipt)",
            "Env: YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY",
        ]),
        ("8.2 DeepSeek API (LLM)", [
            "Классификация интентов (заметка / напоминание / покупки)",
            "Извлечение деталей (дата, время, категория)",
            "Семантический поиск по заметкам",
            "Парсинг привычек из текста",
            "Чат AI-агента (RAG с контекстом из заметок)",
            "Генерация embeddings (или OpenAI text-embedding-3-small)",
        ]),
        ("8.3 Yandex SpeechKit (STT)", [
            "Формат: OGG Opus, русский язык",
            "Конвертация M4A -> OGG через ffmpeg на сервере",
        ]),
        ("8.4 Firebase (push-уведомления)", [
            "Firebase Cloud Messaging v1",
            "APNs для iOS (сертификат в Firebase Console)",
            "Типы: напоминания, привычки, дайджест, подписки",
        ]),
        ("8.5 Open-Meteo (погода)", [
            "Бесплатный API прогноза для утреннего дайджеста",
            "Геокодирование города через Nominatim (OSM)",
        ]),
    ]

    for title, items in integrations:
        story.append(Paragraph(title, s['H2']))
        for item in items:
            story.append(Paragraph(f"- {item}", s['BulletCustom']))

    story.append(PageBreak())

    # =============================================
    # 9. БЕЗОПАСНОСТЬ
    # =============================================
    story.append(Paragraph("9. ТРЕБОВАНИЯ К БЕЗОПАСНОСТИ", s['H1']))

    sec_reqs = [
        ["SEC-01", "Токены хранятся в flutter_secure_storage (Keychain / Keystore)"],
        ["SEC-02", "Refresh-токены хешируются (SHA256) перед хранением в БД"],
        ["SEC-03", "Access-токены: TTL 15 минут"],
        ["SEC-04", "Webhook ЮКасса: верификация IP-адресов отправителя"],
        ["SEC-05", "HTTPS обязателен для всех API-вызовов"],
        ["SEC-06", "Rate limiting: voice 15/день (free), payments/create 5/час, memory/chat 60/час"],
        ["SEC-07", "Параметризованные SQL-запросы (asyncpg $1, $2)"],
        ["SEC-08", "Проверка владения ресурсом при каждой операции"],
        ["SEC-09", "Чувствительные данные (.env) не попадают в git"],
        ["SEC-10", "CORS: production-домен (не '*')"],
    ]
    story.append(make_table(["ID", "Требование"], sec_reqs, [20*mm, 150*mm]))

    # =============================================
    # 10. НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ
    # =============================================
    story.append(Paragraph("10. НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ", s['H1']))

    story.append(Paragraph("10.1 Производительность", s['H2']))
    perf_reqs = [
        ["API CRUD-операции", "< 500ms (95 перцентиль)"],
        ["Распознавание речи", "< 5 сек"],
        ["Ответ AI-агента", "< 10 сек"],
        ["Пагинация", "20 элементов по умолчанию"],
    ]
    story.append(make_table(["Метрика", "Целевое значение"], perf_reqs, [60*mm, 110*mm]))

    story.append(Paragraph("10.2 Надёжность", s['H2']))
    reliability = [
        "Uptime API: 99.5%",
        "Graceful degradation: если LLM недоступен, заметка создаётся без AI",
        "Retry-политика Dio: 3 попытки с exponential backoff",
        "Идемпотентность webhook ЮКасса (проверка по yookassa_payment_id)",
    ]
    for r in reliability:
        story.append(Paragraph(f"- {r}", s['BulletCustom']))

    story.append(Paragraph("10.3 Поддержка платформ", s['H2']))
    platforms = [
        ["Android", "API 21+ (Android 5.0+)"],
        ["iOS", "12.0+"],
        ["Flutter SDK", "3.22+"],
    ]
    story.append(make_table(["Платформа", "Минимальная версия"], platforms, [60*mm, 110*mm]))

    story.append(Paragraph("10.4 Локализация и оффлайн", s['H2']))
    story.append(Paragraph("- Основной язык: русский. Форматирование дат через intl.", s['BulletCustom']))
    story.append(Paragraph("- MVP без оффлайн-режима. При отсутствии сети: кэшированные данные (Hive) + сообщение об ошибке.", s['BulletCustom']))

    story.append(PageBreak())

    # =============================================
    # 11. ПЛАН РЕАЛИЗАЦИИ
    # =============================================
    story.append(Paragraph("11. ПЛАН РЕАЛИЗАЦИИ", s['H1']))

    phases = [
        ("Фаза 1: Бэкенд + MVP мобилки", "Недели 1-3", [
            ["CORS middleware", "Готово"],
            ["Refresh-токены (access 15 мин, refresh 30 дней)", "Готово"],
            ["FCM device registration endpoint", "Готово"],
            ["Расширение профиля (city, reminder, pre_reminder)", "Готово"],
            ["Voice upload endpoint (ffmpeg конвертация)", "Готово"],
            ["Habits API (CRUD + трекинг)", "Готово"],
            ["Flutter: auth, notes, note detail, create note, profile", "В работе"],
        ]),
        ("Фаза 2: Платежи + Подписки", "Недели 4-6", [
            ["Таблицы subscriptions + payments", "Запланировано"],
            ["ЮКасса SDK интеграция (payment_service.py)", "Запланировано"],
            ["API: create, webhook, subscription, cancel", "Запланировано"],
            ["Scheduler: проверка истёкших подписок", "Запланировано"],
            ["Flutter: Paywall, PaymentWebView, подписка в профиле", "Запланировано"],
        ]),
        ("Фаза 3: AI-память", "Недели 7-10", [
            ["pgvector + таблицы (embeddings, conversations, facts)", "Запланировано"],
            ["Embedding service + AI memory service (RAG)", "Запланировано"],
            ["API: chat, conversations, facts, reset", "Запланировано"],
            ["Интеграция embeddings в process_and_save_note()", "Запланировано"],
            ["Flutter: AiChatScreen, MemoryFactsScreen", "Запланировано"],
        ]),
        ("Фаза 4: Полировка + Публикация", "Недели 11-13", [
            ["Push-уведомления (firebase_messaging wiring)", "Запланировано"],
            ["UI привычек, покупок, дней рождения", "Запланировано"],
            ["Rate limiting (slowapi + Redis)", "Запланировано"],
            ["Тёмная тема", "Запланировано"],
            ["Публикация Google Play + App Store", "Запланировано"],
        ]),
    ]

    for phase_title, timeline, tasks in phases:
        story.append(Paragraph(f"{phase_title} ({timeline})", s['H2']))
        story.append(make_table(
            ["Задача", "Статус"],
            tasks,
            col_widths=[130*mm, 40*mm]
        ))

    story.append(PageBreak())

    # =============================================
    # 12. ГЛОССАРИЙ
    # =============================================
    story.append(Paragraph("12. ГЛОССАРИЙ", s['H1']))

    glossary = [
        ["STT", "Speech-to-Text -- распознавание речи"],
        ["LLM", "Large Language Model -- большая языковая модель"],
        ["RAG", "Retrieval-Augmented Generation -- генерация с дополненным извлечением"],
        ["pgvector", "Расширение PostgreSQL для векторных эмбеддингов"],
        ["Embedding", "Числовое векторное представление текста"],
        ["HNSW", "Hierarchical Navigable Small World -- алгоритм поиска ближайших соседей"],
        ["FCM", "Firebase Cloud Messaging -- push-уведомления"],
        ["JWT", "JSON Web Token -- токены авторизации"],
        ["ЮКасса", "Платёжный сервис (ранее Яндекс.Касса)"],
        ["SBP", "Система быстрых платежей ЦБ РФ"],
        ["54-ФЗ", "Федеральный закон о ККТ, обязывает отправлять чеки"],
        ["Streak", "Непрерывная серия выполнений привычки"],
        ["Paywall", "Экран, блокирующий доступ к платным функциям"],
        ["Deep linking", "Открытие экрана приложения по URL-ссылке"],
        ["Riverpod", "State management решение для Flutter"],
        ["Dio", "HTTP-клиент для Dart с interceptors"],
        ["go_router", "Декларативный роутер для Flutter"],
        ["freezed", "Кодогенерация иммутабельных моделей Dart"],
    ]
    story.append(make_table(
        ["Термин", "Определение"],
        glossary,
        col_widths=[30*mm, 140*mm]
    ))

    story.append(Spacer(1, 20*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_LINE))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Конец документа", s['DocMeta']))

    return story


def add_page_number(canvas_obj, doc):
    """Add page number to each page footer."""
    canvas_obj.saveState()
    canvas_obj.setFont(FONT_NAME, 8)
    canvas_obj.setFillColor(grey)
    page_num = canvas_obj.getPageNumber()
    text = f"VoiceNote AI -- Техническое задание  |  стр. {page_num}"
    canvas_obj.drawCentredString(A4[0] / 2, 12*mm, text)
    canvas_obj.restoreState()


def main():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=15*mm,
        title="VoiceNote AI - Техническое задание",
        author="Команда VoiceNote AI",
        subject="ТЗ на разработку мобильного приложения",
    )

    story = build_document()
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    print(f"PDF created successfully: {OUTPUT_PATH}")
    print(f"File size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
