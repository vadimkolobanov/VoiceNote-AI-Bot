# VoiceNote AI — Mobile

Полноценное мобильное приложение VoiceNote AI для iOS и Android. Реализовано на Flutter согласно [техническому заданию](../docs/TECHNICAL_REQUIREMENTS.pdf).

> **Важно.** Мобильный проект работает независимо от Telegram: никакой привязки к боту, Telegram Login Widget или одноразовым кодам из бота. Аутентификация — по email/паролю через собственные эндпоинты бэкенда (`/api/v1/auth/email/*`).

## Стек

| Слой | Технология |
|---|---|
| Фреймворк | Flutter 3.22+ (Dart 3.4+) |
| State management | Riverpod (`flutter_riverpod`) + `StateNotifier` |
| HTTP | Dio + кастомный `AuthInterceptor` (refresh + retry) |
| Навигация | go_router с ShellRoute и auth-guard-ом |
| Secure storage | flutter_secure_storage (Keychain / Keystore) |
| Аудио | `record` (M4A/AAC) + `permission_handler` |
| Платежи | `webview_flutter` (ЮКасса confirmation_url) |
| Push | `firebase_messaging` + `flutter_local_notifications` |
| UI | Material 3, Google Fonts (Inter), Shimmer |

## Структура проекта

```
lib/
├── main.dart                 # Bootstrap: Env, intl, ProviderScope
├── app.dart                  # MaterialApp.router, темы, локализация
├── core/
│   ├── config/env.dart       # Переменные окружения из assets/.env
│   ├── theme/                # Material 3 design system
│   ├── router/               # go_router + auth redirect
│   ├── network/              # Dio + AuthInterceptor (JWT refresh)
│   ├── storage/              # SecureTokenStorage
│   ├── errors/               # ApiException (маппит DioException -> UI)
│   └── utils/                # Форматтеры дат
├── features/
│   ├── auth/                 # Email/password вход, регистрация, сессия
│   ├── notes/                # CRUD заметок + AI-поиск + пагинация + свайпы
│   ├── voice/                # Запись микрофона -> /voice/recognize
│   ├── habits/               # Привычки + weekly grid
│   ├── ai_agent/             # Чат с AI-агентом (premium) + Память
│   ├── payments/             # Paywall + WebView ЮКасса
│   ├── profile/              # Профиль, настройки, достижения
│   ├── shopping_list/        # Совместный список покупок
│   └── birthdays/            # Дни рождения
└── shared/widgets/           # AppShell (BottomNav), shimmer, empty/error
```

Каждая фича построена по трёхслойной feature-first архитектуре:
`data/` (модели, репозиторий) → `application/` (Riverpod контроллер/состояние) → `presentation/` (экраны, виджеты).

## Настройка

### 1. Установить зависимости

```bash
cd mobile
flutter pub get
```

### 2. Настроить окружение

```bash
cp assets/.env.example assets/.env
# отредактируйте API_BASE_URL под свой бэкенд
```

### 3. Шрифты (опционально)

Скачайте [Inter](https://fonts.google.com/specimen/Inter) и положите `.ttf` файлы в `assets/fonts/`. Без них приложение всё равно запустится — используется fallback от Google Fonts.

### 4. Firebase

Для push-уведомлений добавьте `android/app/google-services.json` и `ios/Runner/GoogleService-Info.plist` (получить в Firebase Console).

### 5. Подготовить бэкенд

В корне репозитория выполнить миграцию:

```bash
psql $DATABASE_URL -f mobile/migrations/001_add_mobile_auth.sql
```

Подключить роутер в `src/web/app.py`:

```python
from src.web.api import mobile_auth
app.include_router(mobile_auth.router, prefix="/api/v1")
```

Добавить зависимость:

```bash
pip install bcrypt pydantic[email]
```

### 6. Запуск

```bash
flutter run                      # debug
flutter build apk --release      # Android
flutter build ipa                # iOS (требует macOS + Xcode)
```

## Ключевые архитектурные решения

- **JWT refresh без гонок.** `AuthInterceptor` держит `_refreshInFlight` — один Future на все параллельные 401, чтобы не гонять refresh в несколько потоков. При провале — колбэк `onSessionExpired` сбрасывает сессию, `go_router` сам уводит на `/login`.
- **Router как единый источник правды для навигации.** `refreshListenable` слушает `SessionController`; redirect-логика покрывает splash / auth / shell.
- **Paywall-first для premium-фичи.** Экран AI Агента встраивает `PaywallScreen(inline: true)`, если у пользователя нет VIP. Повторной навигации не требуется.
- **Optimistic UI** для tracking привычек и удаления заметок — при ошибке состояние откатывается.
- **Никаких генерированных моделей в репозитории.** Сначала были взяты freezed/json_serializable, но в итоге остановились на ручных `fromJson` — быстрее компиляция, проще ревью, нет зависимости от build_runner на старте.

## API совместимость

Приложение общается с существующим FastAPI бэкендом (`src/web/api/*`). Единственное добавление к бэкенду — `src/web/api/mobile_auth.py` (email/password).

| Эндпоинт | Использование |
|---|---|
| `POST /auth/email/register` | Регистрация |
| `POST /auth/email/login` | Логин |
| `POST /auth/refresh` | Рефреш (общий с Telegram auth) |
| `POST /auth/email/logout` | Логаут |
| `GET  /profile/me` | Загрузка профиля |
| `PUT  /profile/me` | Настройки |
| `GET /notes`, `POST /notes`, `PUT /notes/{id}`, `DELETE /notes/{id}`, `POST /notes/{id}/complete`, `POST /notes/search` | Заметки |
| `POST /voice/recognize` | Голос → заметка |
| `GET/POST /habits`, `POST /habits/{id}/track`, `GET /habits/{id}/stats` | Привычки |
| `POST /memory/chat`, `GET /memory/facts`, `DELETE /memory/reset` | AI-агент |
| `POST /payments/create`, `GET /payments/subscription`, `POST /payments/cancel` | Подписка |
| `GET/POST/DELETE /shopping-list`, `/shopping-list/items*` | Покупки |
| `GET/POST/DELETE /birthdays` | Дни рождения |

## Безопасность

- Access-токены живут 15 минут, refresh — 30 дней.
- Refresh-токены хешируются (SHA-256) в БД (existing backend).
- Пароли — bcrypt, 12 раундов.
- Все токены в `flutter_secure_storage` (Keychain / EncryptedSharedPreferences).
- HTTPS обязателен в production (проверяется по `Env.isProduction`).
- Верификация email/пароля: минимум 8 символов, буква + цифра.

## Чего ещё нет (из ТЗ)

- Firebase FCM wiring (регистрация токена уже готова в `ProfileRepository.registerDevice`, остаётся подключить обработчик `onMessage` в `main.dart` и показать разрешение).
- Deep links для возврата после оплаты (`app_links` в зависимостях, но слушатель пока не добавлен).
- Оффлайн-режим через Hive (зависимость добавлена, но кэширование не реализовано).

## Тесты

```bash
flutter test
```

Основные точки для покрытия — `AuthInterceptor`, `SessionController`, маппинг JSON → модели.
