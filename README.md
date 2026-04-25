# VoiceNote AI

> «Говори мне всё. Я запомню, напомню и со временем стану тобой.»

Голосовой личный ассистент-внешняя память. iOS + Android (Flutter) клиент,
FastAPI backend на PostgreSQL + pgvector, LLM через DeepSeek (с fallback'ом),
оплата через YooKassa. Полная спецификация продукта — в [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md).

---

## Структура репо

```
.
├── docs/PRODUCT_PLAN.md    # единственный источник истины
├── src/                    # backend (FastAPI)
│   ├── core/               # config, logging
│   ├── db/                 # SQLAlchemy 2.0 async + 9 ORM моделей (§4)
│   ├── services/
│   │   ├── auth_service.py     # email/password, JWT, refresh rotation
│   │   ├── security.py         # argon2id, JWT
│   │   ├── moments/            # доменный сервис + skip-LLM heuristic
│   │   ├── llm_router/         # фасад над DeepSeek/Claude (§6.0)
│   │   ├── billing/            # YooKassa client + BillingService
│   │   └── rate_limit.py       # фикс-окно лимитер (§5.1)
│   ├── web/api/v1/         # /api/v1/* — auth, moments, facts, agent,
│   │                        # profile, push, billing, health
│   └── web/middleware/     # rate-limit middleware
├── alembic/                # миграции БД (V1 init, V2 billing)
├── tests/unit/             # 78 unit-тестов
├── mobile/                 # Flutter app (Riverpod + go_router + Dio + WebView)
│   └── lib/features/       # auth, today, timeline, rhythm, profile,
│                           # voice_capture, moments, moment_details,
│                           # facts (S15), agent, paywall, billing
├── dev_app.py              # dev-only ASGI factory (uvicorn)
├── docker-compose.dev.yml  # локальный Postgres+Redis fallback
└── .env.example            # шаблон env-переменных backend
```

---

## Quick start (свежий клон)

### Требования

- **Python 3.12+**, `pip`
- **Flutter 3.22+**, `flutter doctor` зелёный
- **PostgreSQL 16 + pgvector**: либо managed-провайдер с предустановленным
  pgvector, либо локальный через `docker compose -f docker-compose.dev.yml up -d`
- (опционально) **Redis 7** для rate-limit; без него работает на in-memory KV
- Для оплаты в M7: тестовый кабинет [yookassa.ru](https://yookassa.ru)

### 1. Backend

```bash
git clone https://github.com/vadimkolobanov/VoiceNote-AI-Bot.git
cd VoiceNote-AI-Bot

# venv
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/macOS

# deps
pip install -r requirements.txt

# config
cp .env.example .env
# → открой .env и заполни DB_*, JWT_SECRET_KEY, DEEPSEEK_API_KEY

# миграции
python -m alembic upgrade head

# запуск (dev)
python -m uvicorn dev_app:app --host 0.0.0.0 --port 8765
```

Smoke-тест:

```bash
curl http://localhost:8765/health
# {"status":"ok","version":"dev","db":"ok"}

curl -X POST http://localhost:8765/api/v1/auth/email/register \
  -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"hunter22_strong","display_name":"Я"}'
```

### 2. Mobile (Flutter)

```bash
cd mobile
cp assets/.env.example assets/.env
# → открой assets/.env и поставь API_BASE_URL под свой стенд:
#   • Android emulator   → http://10.0.2.2:8765
#   • iOS simulator      → http://localhost:8765
#   • Физический девайс  → http://<LAN-IP>:8765 (uvicorn должен слушать 0.0.0.0)

flutter pub get
flutter run
```

### 3. Тесты

```bash
# backend (78 unit тестов)
pytest tests/unit/ -v

# mobile (lint)
cd mobile && flutter analyze
```

---

## Что нужно дозабрать отдельно (не в git)

История проекта пишется в git, но **секреты туда не уходят**.
При переезде на другой комп их надо принести руками:

| Файл | Откуда взять |
|---|---|
| `.env` (корень) | заполнить руками из `.env.example`. Пароль БД — у провайдера. |
| `mobile/assets/.env` | копия из `mobile/assets/.env.example` |
| Firebase service account JSON | Firebase Console → Project Settings → Service Accounts → Generate new private key. Положить в корень с именем `*-firebase-adminsdk-*.json` (gitignore покрывает паттерн). |
| API ключи (DeepSeek, YooKassa, Yandex SpeechKit) | соответствующие кабинеты, скопировать в `.env` |

---

## Где мы по плану (§14)

| M | Что | Status |
|---|---|---|
| M0 | Очистка legacy | ✅ `a5e935a` |
| M1 | Backend foundation (SA + alembic V1 + auth) | ✅ `155390c` |
| M2.1 | Moments core (LLMRouter + heuristics + CRUD) | ✅ `a9b428b` |
| M2.2 | Facts/profile/push/agent + rate-limit | ✅ `aef7922` |
| M3 | Claude Haiku через Hetzner | ⏸ DeepSeek-fallback работает |
| M4 | Mobile shell (4 таба + auth + voice modal) | ✅ `ace007e` |
| M5 | Mobile moments (Today/Timeline/Details) | ✅ `89191e7` |
| M5.5 | Реальная voice-запись + `/voice/moment` | ⏸ |
| M6 | Mobile rhythm/facts/agent/paywall/editable profile | ✅ `6a61f0f` |
| M7 | YooKassa billing (mock + production-ready) | ✅ `842d4ae` |
| M8 | Polish + store assets + beta | ⏸ |
| M9 | Store submission (RuStore + Google Play) | ⏸ |
| M10 | Learning (S16/S17 + bulk import) | ⏸ post-MVP |

---

## Полезные команды

```bash
# Backend dev-сервер
python -m uvicorn dev_app:app --host 0.0.0.0 --port 8765

# Новая миграция
python -m alembic revision --autogenerate -m "описание"
python -m alembic upgrade head

# Откат на ступень
python -m alembic downgrade -1

# Mobile
cd mobile
flutter analyze
flutter run
flutter build apk --release       # Android, без подписи store-варианта
```

---

## Ссылки

- Спецификация: [`docs/PRODUCT_PLAN.md`](docs/PRODUCT_PLAN.md)
- Дизайн-токены: [`mobile/lib/core/theme/mx_tokens.dart`](mobile/lib/core/theme/mx_tokens.dart)
- Промпты LLM: [`src/services/llm_router/prompts/`](src/services/llm_router/prompts/)
- Старый легаси-README: см. `git show 438b0c8:README.md` (если нужен исторический контекст)
