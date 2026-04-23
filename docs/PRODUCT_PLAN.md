# VoiceNote AI — Product Plan (Single Source of Truth)

> Этот документ — **единственный источник истины** для продукта. Любой агент или инженер, читая его, должен получить полный ответ на вопросы: «что делаем», «как делаем», «в каком порядке», «что НЕ делаем». Если возникает неоднозначность — уточнение вносится в этот файл и больше нигде.
>
> **Правило изменений:** менять скоуп, модель данных или экраны можно только явно, с датой и причиной в разделе `CHANGELOG` в конце документа. Без этого — план заморожен.

---

## 0. TL;DR

**Продукт:** голосовой личный ассистент, который работает как внешняя память. Пользователь говорит — ассистент записывает, понимает, сам раскладывает по трём временным срезам (сегодня / хроника / ритм) и со временем учится у пользователя.

**Платформы:** iOS + Android (Flutter). Бэкенд — FastAPI на существующей инфре. Telegram-бот **понижен до legacy-канала ввода** без собственных экранов, не упоминается в онбординге мобильного приложения (см. §16).

**Монетизация:** Pro 400 ₽/мес или 3 490 ₽/год. Pro = доступ к памяти и ИИ-агенту. Всё остальное бесплатно.

**Ключевой AI-принцип:** on-device STT по умолчанию (бесплатно для нас), серверный STT только как fallback для длинных записей. Все задачи раскладываются между DeepSeek (дёшево, из РФ напрямую), локальным BGE-M3 (эмбеддинги, 0 ₽) и Claude Haiku через свой Hetzner-прокси (только агент). См. §6 и §18.

**MVP готовности к сторам:** 10 милстоунов, описанных в §14.

**Ключевой принцип архитектуры:** одна сущность — `moment`. Все заметки, напоминания, привычки, покупки, дни рождения — фильтры над `moments`. Любая попытка завести параллельную таблицу «для одного случая» — отклоняется.

---

## 1. Видение и рамки

### 1.1. Позиционирование (одно предложение)
> «Говори мне всё. Я запомню, напомню и со временем стану тобой.»

### 1.2. Job-to-be-done
Пользователь хочет разгрузить голову: мысли, планы, мелочи быта, людей, желания — без трения, голосом, в любой момент. И получать обратно структурированные напоминания и ответы на вопросы о собственной жизни.

### 1.3. Чего продукт НЕ делает (жёсткие non-goals)
- ❌ Не Notion, не kanban, не подзадачи, не проекты
- ❌ Не соцсеть, не публичные профили, не шаринг между пользователями (кроме приватного sharing, см. §4.11 — вне MVP)
- ❌ Не мессенджер с друзьями
- ❌ Не групповые списки для семьи (post-MVP)
- ❌ Не веб-версия (только мобила + бот как канал ввода)
- ❌ Не self-hosted, не on-premise
- ❌ Никаких сторонних интеграций в MVP (Google Calendar, Todoist и т. д.)

### 1.4. Целевые пользователи MVP
Русскоговорящие взрослые 25–45, RU/UA/KZ рынки, использующие Android и iOS, привыкшие к голосовому вводу (Алиса, Сири). Платёжеспособная аудитория — те, кому важна память и напоминания («забываю всё»).

### 1.5. Успех MVP (количественные метрики)
- D1 retention ≥ 40 %
- D7 retention ≥ 20 %
- D30 retention ≥ 10 %
- Среднее количество моментов на активного пользователя в день ≥ 3
- Конверсия в Pro от D30-активных ≥ 5 %
- Crash-free sessions ≥ 99.5 %

---

## 2. UX-спецификация

### 2.1. Навигация — ровно три вкладки и один модал

```
┌────────────────────────────────────────────────┐
│                                                │
│               [ контент вкладки ]              │
│                                                │
│                                                │
│                      🎙️                        │  ← FAB в центре, всегда видна
│                                                │
├──────────┬──────────┬────────────┬──────────┤
│  Сегодня │  Хроника │   Ритм    │ Профиль  │  ← 4 таба, но Профиль маленький
└──────────┴──────────┴────────────┴──────────┘
```

**Четыре нижних таба:** Сегодня, Хроника, Ритм, Профиль. FAB микрофона — плавающая, над табами, всегда вызывает голосовой захват.

### 2.2. Карта экранов (полный список)

| # | Экран | Назначение | Состояния |
|---|---|---|---|
| S1 | Splash | Лого + тихая проверка токена | loading, ok, no-auth |
| S2 | Onboarding step 1 | Первый голосовой ввод | idle, recording, processing, done |
| S3 | Onboarding step 2 | Время утреннего дайджеста | — |
| S4 | Onboarding step 3 | Разрешения: микрофон, пуши | — |
| S5 | Auth (email) | Вход/регистрация | login, register, reset, error |
| S6 | **Сегодня** | Лента на 24ч | empty, list, loading, refreshing |
| S7 | **Хроника** | Все моменты по датам + поиск | list, search-mode, empty-query, ai-answer |
| S8 | **Ритм** | Повторяющиеся моменты | habits-list, upcoming-cycles, empty |
| S9 | **Профиль** | Настройки, подписка, выход | — |
| S10 | Детали момента | Full view, edit, delete, snooze | view, edit |
| S11 | Голосовой захват (модал) | Запись, прогресс, текст-подтверждение | recording, uploading, processing, confirm |
| S12 | Paywall | Оферта Pro | — |
| S13 | YooKassa WebView | Оплата | — |
| S14 | Поиск/вопрос к ИИ | Окно над Хроникой | idle, typing, loading, answer |
| S15 | **Что я о тебе знаю** | Список `facts` группами (люди/места/предпочтения/ритм), редактирование/удаление | empty, loaded, editing |
| S16 | **Расскажи о себе** (M10) | Активный вопросник, 5–7 вопросов | step1..stepN, summary |
| S17 | **Импорт данных** (M10) | Загрузка Telegram-экспорта / текстового файла, прогресс, итог | idle, uploading, processing, done, error |

**Больше экранов не существует.** Если возникает новый — сначала правится этот план.
S15 входит в MVP (читаемый просмотр + ручная правка фактов). S16 и S17 — M10 post-MVP.

### 2.3. Экран «Сегодня» (S6) — детальная спецификация

**Что показывается (порядок сверху вниз):**

1. **Приветствие** — одна строка, зависит от времени суток и от данных. Примеры:
   - «Доброе. Сегодня у тебя 3 дела и ДР у Ани.»
   - «Вечер. Осталось одно незакрытое напоминание.»
   - «Всё тихо. Можно записать что-нибудь новое.»

2. **Блок «Сейчас»** (если есть что-то в ближайшие 2 часа) — выделенная карточка.

3. **Блок «Сегодня»** — все моменты с гранью «время» на сегодня, отсортированные по времени. Каждый — карточка с:
   - Время (если есть)
   - Заголовок (generated by LLM)
   - Иконка типа (⏰ task, 🔁 habit, 🎂 birthday, 🛒 shopping)
   - Свайп вправо → выполнить (checkmark)
   - Свайп влево → отложить (quick snooze на +1ч / +1 день)
   - Тап → S10

4. **Блок «Завтра»** — свёрнутый по умолчанию, можно раскрыть.

5. **Пустое состояние:** крупная подпись *«Сегодня никаких дел. Запиши что-нибудь новое — я запомню»* и стрелка на FAB.

**Состояния:**
- Loading: skeleton-лоадер 3 карточек.
- Pull-to-refresh: обязательно.
- Ошибка сети: плашка сверху «Нет связи. Показываю последнее.»

### 2.4. Экран «Хроника» (S7)

**Лента моментов от новых к старым, сгруппировано по датам.**

Поверх ленты — поисковая строка с плейсхолдером *«Спроси меня о чём угодно…»*.
Поисковая строка работает в двух режимах, определяемых автоматически:
- **Литеральный поиск** (короткий запрос, 1–3 слова без вопросительного знака) — full-text search по `moments.text`.
- **Вопрос к ИИ** (длиннее или с «?», или начинается с «кто/что/когда/где/почему/помнишь») — отдаётся в `/api/v1/agent/ask`. Ответ показывается над лентой в виде карточки с цитатами моментов-источников.

**Любой свободный пользователь видит только последние 30 дней. Всё старше — затёрто плашкой «Память дальше 30 дней — в Pro».**

### 2.5. Экран «Ритм» (S8)

Два раздела:
1. **Привычки** — моменты с ежедневным/еженедельным повтором. Отображение: название + сетка 7 дней (heatmap) + серия (streak).
2. **Циклы** — всё остальное с повтором: ДР, зарплата, «раз в месяц позвонить бабушке», «каждую пятницу — отчёт».

Без XP, без ачивок. Есть только *серия* (сколько дней подряд) — это уже работающий драйвер.

### 2.6. Детали момента (S10)

Поля:
- Полный текст (editable)
- Заголовок (editable)
- Дата/время (picker) — можно удалить, тогда момент теряет грань «время»
- Повтор (rrule builder: никогда / ежедневно / еженедельно / ежемесячно / ежегодно / кастом)
- Теги-грани (read-only чипсы: «покупки», «человек: мама», «место: зал» — проставлены ИИ, пользователь может удалить)
- Статус: активен / выполнен / архив
- Аудио-оригинал — кнопка «▶️ Послушать запись» (если был голос)

Действия: Сохранить, Удалить, Дублировать, Поделиться ссылкой (post-MVP).

### 2.7. Голосовой захват (S11)

**Один модал, три секунды магии.**

1. Тап на FAB → немедленный старт записи, haptic feedback, круглая кнопка пульсирует.
2. Во время записи: waveform визуализация, таймер, кнопка «Отмена» и «Стоп».
3. По стопу (или автостопу по тишине 1.5с): плашка «Понимаю…», идёт upload + STT + LLM.
4. Через ~2–4 секунды показывается **подтверждение**:
   - распознанный текст (editable tap-to-edit)
   - угаданные грани чипсами (время, люди, повтор)
   - одна большая кнопка **«Сохранить»** и маленькая «Отменить»
5. Если момент распознан как напоминание — в подтверждении показан preview «Напомню: завтра в 15:00».

**Важно:** пользователь может нажать «Сохранить» моментально — мы уже начали обработку в фоне. Не блокировать UI.

### 2.8. Onboarding (S2–S4) — 90 секунд от установки до первой ценности

Экран 1: **«Расскажи мне одну вещь, которую не хочешь забыть»** — большой микрофон. Нельзя пропустить. После записи показать, как момент появился в «Сегодня».

Экран 2: **«Когда утром напоминать про план на день?»** — три варианта: 7:00 / 8:00 / 9:00 + «не надо».

Экран 3: **«Разреши пуши и микрофон — без них не работает»** — два system-дайлога, каждый с предварительным объяснением на своём экране.

После — сразу на «Сегодня».

**Нет запросов email/таймзоны/имени на онбординге.** Email — только при первой попытке открыть Профиль или перед Pro. Таймзона — из устройства. Имя — из первого момента, если его можно извлечь, или «друг».

### 2.9. Редполитикал (characterguide)

Один голос, обязательный для всех текстов (UI, пуши, дайджест, ошибки).

**Тональность:** умный внимательный друг. Знает тебя. Не льстит, не подобострастен. Короткие фразы. Без канцелярита.

**Правила:**
- «ты», не «вы»
- Никогда не «Пользователь», «Задача», «Действие выполнено»
- Глаголы в настоящем/будущем, не в пассиве
- Короткие предложения (≤ 12 слов)
- Эмодзи — точечно, максимум один на сообщение, и только функциональные (🎂 ДР, 🛒 покупки, ⏰ напоминание). Никаких 🌟✨💫.

**Примеры замены:**

| ❌ Плохо | ✅ Хорошо |
|---|---|
| Ваше напоминание успешно создано | Запомнил. Толкну тебя в четверг в 15:00. |
| Задача выполнена | Красавчик. Минус один пункт. |
| Ошибка распознавания речи | Не расслышал. Ещё раз? |
| Ваши задачи на сегодня | Сегодня у тебя три дела и ДР у Ани. |
| Достигнут дневной лимит | На сегодня лимит кончился. Завтра снова послушаю сколько хочешь. |
| Подписка оформлена | Добро пожаловать в Pro. Теперь я помню всё. |

**Копирайтер — один человек или один LLM-промпт.** Не правим по месту, правим в `copy.ru.arb` централизованно.

---

## 3. Архитектура системы (высокий уровень)

```
┌─────────────────────────────────────────────────────────────┐
│                      Каналы ввода                            │
│  Mobile (Flutter)  │  Telegram bot (aiogram)  │  Alice skill │
└────────┬─────────────────┬───────────────────────┬──────────┘
         │ HTTPS/JWT       │ webhook               │ webhook
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI backend                         │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐    │
│  │ REST API   │ │  Webhooks  │ │  APScheduler         │    │
│  │ (moments,  │ │ (TG,Alice, │ │  (напоминания,       │    │
│  │  agent,    │ │  YooKassa) │ │   утренний дайджест) │    │
│  │  auth,pay) │ │            │ │                      │    │
│  └──────┬─────┘ └──────┬─────┘ └───────────┬──────────┘    │
│         │              │                    │               │
│  ┌──────▼──────────────▼────────────────────▼──────────┐   │
│  │              Services (domain layer)                 │   │
│  │  MomentService · AgentService · BillingService      │   │
│  │  PushService · VoiceService · FacetExtractor        │   │
│  └──────────────────────┬───────────────────────────────┘   │
└─────────────────────────┼──────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┬──────────────┐
         ▼                ▼                ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────┐
│ PostgreSQL   │  │   Redis      │  │ DeepSeek   │  │ Yandex STT │
│ + pgvector   │  │ (cache, fsm, │  │ (LLM)      │  │            │
│              │  │  rate-limit) │  │            │  │            │
└──────────────┘  └──────────────┘  └────────────┘  └────────────┘
                                          ▲
                                          │
                                    ┌─────┴──────┐
                                    │  FCM (pushes) │
                                    └───────────────┘
                                    ┌───────────────┐
                                    │  YooKassa API │
                                    └───────────────┘
```

**Принципы:**
- Все каналы входа пишут в один и тот же слой сервисов. Mobile, Bot, Alice — это только транспорт.
- Домен-модель чистая: сервисы не знают про Telegram и про Flutter.
- APScheduler — единственный планировщик. Никаких cron'ов и setTimeout на клиенте.
- Redis — рабочий, не обязательный (graceful degradation).

---

## 4. Модель данных (финальная, frozen)

### 4.1. Основная таблица `moments`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE moments (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Сырые данные
    raw_text        TEXT NOT NULL,              -- то, что сказал/написал пользователь
    source          TEXT NOT NULL,              -- 'voice' | 'text' | 'forward' | 'alice' | 'manual'
    audio_url       TEXT,                       -- S3/локальный путь к оригиналу, может быть NULL
    language        TEXT DEFAULT 'ru',

    -- Структурированные данные от LLM
    title           TEXT NOT NULL,              -- короткий заголовок (≤ 60 симв)
    summary         TEXT,                       -- расширенный пересказ, если raw_text > 200 симв
    facets          JSONB NOT NULL DEFAULT '{}',-- см. 4.2

    -- Временные грани (дублируют facets для индексов)
    occurs_at       TIMESTAMPTZ,                -- когда событие (напоминание/встреча)
    rrule           TEXT,                       -- RFC 5545 rrule, если повтор
    rrule_until     TIMESTAMPTZ,                -- конец повтора (опционально)

    -- Статус
    status          TEXT NOT NULL DEFAULT 'active', -- 'active' | 'done' | 'archived' | 'trashed'
    completed_at    TIMESTAMPTZ,

    -- Эмбеддинг для семантического поиска/агента (BGE-M3, self-hosted)
    embedding       vector(1024),               -- BGE-M3 размерность

    -- Метаданные
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_via     TEXT NOT NULL DEFAULT 'mobile', -- 'mobile' | 'bot' | 'alice' | 'system'
    llm_version     TEXT,                       -- какая версия промптов обработала
    client_id       UUID UNIQUE                 -- для идемпотентности при офлайн-синке
);

CREATE INDEX idx_moments_user_occurs    ON moments(user_id, occurs_at) WHERE status='active';
CREATE INDEX idx_moments_user_created   ON moments(user_id, created_at DESC);
CREATE INDEX idx_moments_user_rrule     ON moments(user_id) WHERE rrule IS NOT NULL;
CREATE INDEX idx_moments_facets_gin     ON moments USING gin(facets);
CREATE INDEX idx_moments_embedding      ON moments USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 4.2. Формат `facets` (jsonb)

```jsonc
{
  "kind": "task",              // "task" | "note" | "habit" | "shopping" | "birthday" | "cycle" | "thought"
  "people": ["мама", "Аня"],   // нормализованные имена из контактов пользователя (см. facts)
  "places": ["зал"],
  "topics": ["здоровье"],       // фиксированный словарь: работа, здоровье, семья, деньги, быт, идея, эмоция, покупки
  "priority": "normal",         // "low" | "normal" | "high" (MVP: только normal, авто-high если явно)
  "mood": null,                 // "positive" | "neutral" | "negative" | null — только если явно из голоса
  "shopping_items": [           // если kind="shopping"
    {"text":"молоко","qty":2,"unit":"л","checked":false}
  ]
}
```

**Правило:** любое расширение `facets` — это правка этого раздела + миграция данных. Не добавлять поля «на лету».

### 4.3. Таблица `users`

```sql
CREATE TABLE users (
    id                  BIGSERIAL PRIMARY KEY,
    email               TEXT UNIQUE,           -- null для bot-only пользователей (legacy)
    password_hash       TEXT,                  -- argon2id
    telegram_id         BIGINT UNIQUE,         -- null для mobile-only
    display_name        TEXT,
    timezone            TEXT NOT NULL DEFAULT 'Europe/Moscow',
    locale              TEXT NOT NULL DEFAULT 'ru',
    digest_hour         SMALLINT DEFAULT 8,    -- 0..23, null = не слать
    pro_until           TIMESTAMPTZ,           -- null = не Pro; NOT NULL AND > now() = Pro
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ            -- soft delete для GDPR
);
```

**Flag `is_pro` вычисляется:** `pro_until IS NOT NULL AND pro_until > now()`. Никогда не хранится.

### 4.4. Таблица `facts` (память об пользователе)

```sql
CREATE TABLE facts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,  -- 'person' | 'place' | 'preference' | 'schedule' | 'other'
    key         TEXT NOT NULL,  -- нормализованный ключ: 'мама', 'зал_fitnesshouse'
    value       JSONB NOT NULL, -- { "name": "Анна", "phone": "+7...", "birthday": "03-15", "rel": "мама" }
    confidence  REAL NOT NULL DEFAULT 0.5,  -- 0..1
    source_moment_ids BIGINT[] NOT NULL DEFAULT '{}',
    embedding   vector(1024),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, kind, key)
);
```

### 4.5. Таблица `agent_conversations`

Хранит историю чата с ИИ (S14). Для MVP — один длинный тред на пользователя.

```sql
CREATE TABLE agent_messages (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,  -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    cited_moment_ids BIGINT[],
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_msgs_user ON agent_messages(user_id, created_at);
```

### 4.6. Таблица `subscriptions`

```sql
CREATE TABLE subscriptions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    provider        TEXT NOT NULL,   -- 'yookassa'
    external_id     TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL,   -- 'pro_monthly' | 'pro_yearly'
    status          TEXT NOT NULL,   -- 'pending' | 'active' | 'cancelled' | 'failed'
    started_at      TIMESTAMPTZ,
    ends_at         TIMESTAMPTZ,
    raw_payload     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.7. Таблица `push_tokens`

```sql
CREATE TABLE push_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL,  -- 'ios' | 'android'
    token       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, token)
);
```

### 4.8. Таблица `scheduled_jobs` (состояние планировщика)

APScheduler хранит свои джобы сам. Для бэкапа/аудита дублируем в таблицу:

```sql
CREATE TABLE scheduled_jobs (
    id              TEXT PRIMARY KEY,        -- 'moment:{id}:remind' | 'user:{id}:digest'
    user_id         BIGINT,
    moment_id       BIGINT,
    kind            TEXT NOT NULL,           -- 'reminder' | 'digest' | 'pre_reminder' | 'habit_check'
    run_at          TIMESTAMPTZ NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.9. Старые таблицы — миграция

Старые: `notes`, `reminders`, `habits`, `habit_entries`, `shopping_list`, `shopping_items`, `birthdays`, `user_achievements`.

**Миграция одноразовая (`V2__collapse_to_moments.sql`):**
1. Создать `moments` и связанные (п. 4.1–4.8).
2. Перенести `notes` → `moments` с `facets.kind` вычисленным из `type`/`category`.
3. Перенести `reminders`, которых нет в `notes`, → `moments` с `kind="task"`, `occurs_at`.
4. Перенести `habits` → `moments` с `kind="habit"`, `rrule`.
5. Перенести `shopping_items` → `moments` с `kind="shopping"`, `facets.shopping_items`.
6. Перенести `birthdays` → `moments` с `kind="birthday"`, годовым rrule.
7. Посчитать эмбеддинги для всех импортированных моментов (фоновый job).
8. **После успешной миграции старые таблицы переименовываются в `_legacy_*` и живут 30 дней. Потом `DROP`.**
9. Удалить `user_achievements`, `user.xp` — безвозвратно.

### 4.10. Идемпотентность и офлайн

Клиент генерирует UUID v4 (`client_id`) на каждый создаваемый момент. При оффлайн-синке клиент отправляет массив, сервер игнорирует дубли по `client_id`.

### 4.11. Post-MVP сущности (не делать в MVP, только зарезервировать пространство)

- `moment_shares` — приватный шаринг момента по ссылке.
- `families` — общие списки покупок.
- `integrations` — внешние календари.

### 4.12. Таблица `import_jobs` (M10, для bulk-импорта)

```sql
CREATE TABLE import_jobs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,     -- 'telegram_json' | 'text' | 'markdown'
    status          TEXT NOT NULL,     -- 'uploading' | 'processing' | 'done' | 'failed'
    progress        REAL DEFAULT 0.0,  -- 0..1
    file_path       TEXT,              -- временный путь, удаляется после обработки
    messages_total  INTEGER,
    messages_processed INTEGER,
    moments_created INTEGER DEFAULT 0,
    facts_created   INTEGER DEFAULT 0,
    summary         JSONB,             -- итоговый отчёт для UI
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_import_jobs_user ON import_jobs(user_id, created_at DESC);
```

**Приватность:** `file_path` обнуляется и файл удаляется сразу после `status='done'` или `'failed'`. Сырые сообщения в БД не сохраняются — только извлечённые факты и моменты.

---

## 5. Backend API (полный контракт)

### 5.1. Общие правила

- Базовый URL: `https://api.voicenote.ai/api/v1`
- Auth: `Authorization: Bearer <jwt>`, JWT access 30 минут, refresh 30 дней.
- Все таймстемпы — ISO8601 UTC.
- Ошибки: `{ "error": { "code": "INVALID_CREDENTIALS", "message": "…" } }`. Коды — const list, см. `src/web/errors.py`.
- Rate limit (per user): 60 req/min на `/moments`, 20 req/min на `/agent/ask`, 10 req/min на `/voice/recognize`.
- **Дневные лимиты** (enforced в middleware, reset в 00:00 UTC, Redis counters):

| Метрика | Free | Pro |
|---|---|---|
| Минут серверного STT в сутки | **2** | **30** |
| Вопросов к агенту в сутки | 0 (paywall) | **20** |
| Создаваемых моментов в сутки | 30 | 200 |
| Макс длина одного голосового | 2 мин | 5 мин |

On-device STT на клиенте **не считается** в лимит — он бесплатен для нас.

### 5.2. Endpoints (frozen)

**Auth:**
```
POST /auth/email/register   { email, password, display_name? } → { access, refresh, user }
POST /auth/email/login      { email, password } → { access, refresh, user }
POST /auth/refresh          { refresh } → { access, refresh }
POST /auth/logout           { refresh } → 204
POST /auth/reset/request    { email } → 204
POST /auth/reset/confirm    { token, new_password } → 204
POST /auth/delete           → 204   (soft delete + все данные через 14 дней)
```

**Moments (основной CRUD):**
```
GET    /moments?view=today|timeline|rhythm&cursor=<id>&limit=50 → { items:[], next_cursor }
GET    /moments/{id}          → Moment
POST   /moments               { client_id, raw_text, source, occurs_at?, rrule? } → Moment
                              (LLM обогащает facets в фоне, возвращает сразу)
PATCH  /moments/{id}          partial update → Moment
DELETE /moments/{id}          → 204 (soft: status=trashed)
POST   /moments/{id}/complete → Moment (status=done)
POST   /moments/{id}/snooze   { until } → Moment
POST   /moments/bulk          { items: [{client_id, raw_text, ...}] } → {items: [...]}  (офлайн-синк)
```

**Voice capture:**
```
POST /voice/recognize   multipart(audio)           → { raw_text, confidence }
POST /voice/moment      multipart(audio, client_id)→ Moment   (STT + LLM + save в одном вызове)
```

**Agent (Pro):**
```
POST /agent/ask         { question } → { answer, cited_moments: [{id,title,snippet}] }
GET  /agent/history?cursor=<id>       → { items:[AgentMessage], next_cursor }
```

**Facts (просмотр и редактирование; S15 — в MVP):**
```
GET    /facts?kind=person|place|preference|schedule|other → [Fact]
POST   /facts                 { kind, key, value }       → Fact   (ручное добавление)
PATCH  /facts/{id}            partial update              → Fact
DELETE /facts/{id}                                        → 204
```

**Learning (M10 post-MVP):**
```
POST /learning/about-me/answer  { question_id, answer_text } → { extracted_facts: [Fact] }
POST /import/telegram           multipart(file)              → { job_id }
POST /import/text               multipart(file)              → { job_id }
GET  /import/{job_id}                                         → ImportJob (status + progress + summary)
```

**Shopping list (представление):**
```
GET /views/shopping   → { items:[{moment_id, text, qty, unit, checked}] }
PATCH /views/shopping/{item_id} { checked: true|false } → ok
```

**Rhythm (представление):**
```
GET /views/rhythm → { habits:[MomentWithStreak], cycles:[Moment] }
```

**Billing (YooKassa):**
```
GET  /billing/plans                         → [Plan]
POST /billing/subscribe  { plan }           → { confirmation_url }
POST /billing/webhook    (YooKassa callback) → 200
GET  /billing/status                         → { pro_until, plan?, auto_renew }
POST /billing/cancel                        → ok
```

**Push:**
```
POST /push/register    { token, platform } → ok
POST /push/unregister  { token }           → 204
```

**Profile:**
```
GET   /profile                   → User
PATCH /profile                   { display_name?, timezone?, digest_hour?, locale? } → User
```

### 5.3. Формат `Moment` (response)

```json
{
  "id": 12345,
  "client_id": "uuid-v4",
  "raw_text": "купить молоко и хлеб завтра в магазине",
  "title": "Купить молоко и хлеб",
  "summary": null,
  "facets": { "kind": "shopping", "shopping_items": [{"text":"молоко","qty":1,"unit":"","checked":false}] },
  "occurs_at": "2026-04-23T17:00:00Z",
  "rrule": null,
  "status": "active",
  "source": "voice",
  "audio_url": "/audio/abc.m4a",
  "created_at": "2026-04-22T14:02:00Z",
  "updated_at": "2026-04-22T14:02:00Z"
}
```

---

## 6. AI-пайплайн

### 6.0. Распределение по провайдерам (frozen)

Все LLM/STT-вызовы идут через единую абстракцию `LLMRouter` / `STTRouter`. Прямых импортов `anthropic`, `deepseek`, `yandexcloud` в коде бизнес-логики **нет** — только `router.chat(task=..., ...)`.

| Задача | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| STT короткое (< 45 с) | **on-device** (iOS SFSpeech / Android SpeechRecognizer) | SaluteSpeech | Yandex SpeechKit |
| STT длинное (≥ 45 с) | SaluteSpeech | Yandex SpeechKit | — |
| Facet extraction | DeepSeek-V3 (`deepseek-chat`) | GigaChat-Lite | YandexGPT Lite |
| Facts extraction (Pro only) | DeepSeek-V3 | GigaChat-Lite | — |
| Embeddings | **BGE-M3** (self-host на CPU бэка) | — | — |
| Agent Q&A (Pro) | **Claude Haiku 4.5** через свой Hetzner-прокси | DeepSeek-V3 | — |
| Дайджест утром | DeepSeek-V3 | GigaChat-Lite | — |
| Проактивные подсказки (Pro) | DeepSeek-V3 | — | — |
| Import bulk (M10) | DeepSeek-V3 | — | — |

**Политика fallback:** при 5xx/timeout primary — переключение на fallback-1, при его отказе — fallback-2. Если отказали все — graceful error в духе редполитикала (*«я сегодня перегружен, попробуй через час»*), без crash.

### 6.1. Голос → момент (on-device first стратегия)

**Клиент (Flutter) пытается распознать голос на устройстве. Audio уходит на сервер только если это невозможно или запись длинная.**

```
[Client] запись audio (Opus 16kbps, mono, 16kHz)
  ├─ длина < 45 сек И on-device API доступен
  │    → SFSpeechRecognizer (iOS) / SpeechRecognizer (Android)
  │    → raw_text готов локально
  │    → POST /moments { raw_text, source:'voice', audio_url:null }
  │
  └─ длина ≥ 45 сек ИЛИ on-device упал ИЛИ юзер нажал «распознать точнее»
       → upload audio → POST /voice/moment
       → [SaluteSpeech Recognition] → raw_text
       → лимит минут проверяется ДО отправки (см. §5.1)

[Server] получил raw_text
  → [LLMRouter.classify]
     ├─ тривиальный текст (< 5 слов, без цифр/дат, явные паттерны)
     │   → heuristic title + kind, LLM пропускаем
     └─ иначе → DeepSeek-V3 extract_facets
  → save moment (status=active)
  → [BGE-M3 batch queue] ← эмбеддинг (только если юзер Pro ИЛИ за последние 30 дней)
  → APScheduler jobs (reminder/habit если occurs_at/rrule)
  → фон: extract_facts (только Pro-юзеры)
  → return Moment (клиент уже держит оптимистичную копию из drift)
```

**Целевая P95 latency от конца записи до возврата Moment:**
- on-device ветка: **≤ 1.5 сек**
- server-STT ветка: **≤ 4 сек**

### 6.2. Промпт `extract_facets` (единый, заменяет все текущие)

Файл: `src/services/llm/prompts/extract_facets.md` (Markdown, jinja-подстановки).

Структура промпта:
1. **System:** роль («ты — ассистент, который превращает мысли пользователя в структурированные моменты»)
2. **Context:** таймзона пользователя, сегодняшняя дата, ≤ 10 последних facts (кратко, только для Pro), ≤ 5 последних moment-titles
3. **Input:** `raw_text`
4. **Output:** строгий JSON с полями `title`, `summary?`, `kind`, `occurs_at?`, `rrule?`, `people?`, `places?`, `topics?`, `priority?`, `shopping_items?`
5. **Few-shot:** 6 эталонных примеров (по 1 на каждый kind)
6. **Включает `@characterguide`** (см. §2.9 и §6.6)

Версионирование: `llm_version = "extract_facets_v1"` — пишется в момент.

### 6.3. Агент (S7/S14) — только Pro

```
[Client] user question
  → POST /agent/ask { question }
  → [BGE-M3] embed question
  → pgvector retrieve top-10 moments by cosine similarity (filter user_id, status!='trashed')
  → retrieve top-5 facts (filter user_id)
  → [LLMRouter.agent_ask → Claude Haiku 4.5 via Hetzner proxy]
     prompt: system(characterguide + guardrail) + retrieved_context + question
  → answer + citations (moment ids)
  → save agent_message (role='assistant', cited_moment_ids)
  → кэш ответа в Redis на 10 минут по (user_id, question_hash)
  → return { answer, cited_moments: [...] }
```

**Guardrails:**
- Отвечает только на основе retrieved контекста. Если ничего не нашлось — честно: *«Не помню, расскажи мне»*.
- Цитаты обязательны — UI показывает, на какие моменты опирался ответ.
- Top-10 моментов, не top-20 — экономия токенов ×2.

### 6.4. Facts extraction (фоновый job, только для Pro-юзеров)

После каждого нового момента Pro-юзера — async task `extract_facts_from_moment(moment_id)`:
- Если упомянут человек → upsert `fact(kind=person, key=normalized_name)`.
- Если место — то же с `kind=place`.
- Предпочтение («я не ем мясо») — `kind=preference`.
- Регулярность («каждый четверг я в зале») — `kind=schedule`.

Для Free-юзеров факты **не извлекаются** — это экономит 50 % DeepSeek-вызовов и валидирует ценность Pro.

Promt: `src/services/llm/prompts/extract_facts.md`.

### 6.5. Утренний дайджест

Джоба на `digest_hour` каждого пользователя:
```
gather today's moments (occurs_at between now and +24h)
  + upcoming birthdays (next 7 days)
  + habits due today
  → [DeepSeek-V3: digest_write prompt с characterguide]
  → FCM push + inbox message
```

### 6.6. Характер ассистента — встроен в промпты

Каждый генерирующий промпт включает блок `@characterguide` из §2.9 через jinja-include. Один файл, один голос во всех каналах.

### 6.7. Микро-оптимизации, включённые с M2

Заложить в пайплайн сразу, не после:

1. **Skip-LLM для тривиальных моментов.** Регекс + словарь триггеров определяют `kind` для текстов < 5 слов без дат/цифр (*«купить молоко»*, *«позвонить маме»*). Покрывает 20–30 % моментов.
2. **Batch эмбеддинги.** BGE-M3 получает партию 16–32 текста за вызов; очередь ждёт 2 сек или 16 моментов.
3. **Redis-кэш ответов агента** на 10 минут по ключу `(user_id, sha1(question))`.
4. **Opus 16 kbps** для всех голосовых на клиенте (вместо m4a ~64 kbps). SaluteSpeech принимает.
5. **VAD на клиенте** (`silero-vad` через FFI или native) — вырезает тишину до upload, сокращает длительность на 20–40 %. M6 priority.
6. **Эмбеддинги только для Pro или для моментов за последние 30 дней.** Free-юзеру поиск по старой хронике закрыт paywall'ом — эмбеддинг не нужен.
7. **Top-10 а не top-20** в RAG для агента.

### 6.8. Learning pipeline (M10)

Три канала обучения, один pipeline:

**Канал A — пассивный (работает в MVP через §6.4):** каждый момент Pro-юзера → facts.

**Канал B — активный вопросник (S16, M10):**
```
5–7 вопросов по one-by-one
  → каждый ответ → DeepSeek extract_facts_from_answer
  → upsert facts с confidence=0.8 (высокий — юзер явно сказал)
  → summary screen с правкой
```

**Канал C — bulk import (S17, M10):**
```
multipart upload → import_jobs (status=uploading)
  → async worker (Celery/RQ):
     1. Парсинг файла (Telegram JSON / text / markdown)
     2. Фильтр: только сообщения юзера (from_id == user)
     3. Chunking по 50 сообщений
     4. Для каждого чанка: DeepSeek extract → facts + moments (с source='import')
     5. Прогресс в import_jobs.progress
  → по завершении: summary (сколько людей/мест/обещаний найдено)
  → файл удаляется физически
  → UI показывает S17 итог
```

**Приватность импорта:**
- Перед upload — экран-предупреждение с чекбоксом *«Я понимаю, что мои сообщения будут обработаны на сервере»*.
- Исходный файл удаляется **сразу** после обработки (successful или failed).
- Обрабатываются только сообщения самого пользователя (not chat partners).
- Юзер может удалить все импортированные моменты одним действием (`DELETE /import/{job_id}` делает soft-delete всех связанных moments).

### 6.2. Промпт `extract_facets` (единый, заменяет все текущие)

Файл: `src/services/llm/prompts/extract_facets.md` (Markdown, jinja-подстановки).

Структура промпта:
1. **System:** роль («ты — ассистент, который превращает мысли пользователя в структурированные моменты»)
2. **Context:** таймзона пользователя, сегодняшняя дата, ≤ 10 последних facts (кратко), ≤ 5 последних moment-titles (для устранения дублей «мама» = «мать» = «мамуля»)
3. **Input:** `raw_text`
4. **Output:** строгий JSON с полями `title`, `summary?`, `kind`, `occurs_at?`, `rrule?`, `people?`, `places?`, `topics?`, `priority?`, `shopping_items?`
5. **Few-shot:** 6 эталонных примеров (по 1 на каждый kind)

Версионирование: `llm_version = "extract_facets_v1"` — пишется в момент.

### 6.3. Агент (S7/S14)

```
user question
  → embed question
  → retrieve top-20 moments by cosine similarity (filter user_id, time range)
  → retrieve top-10 facts
  → [DeepSeek: agent_answer prompt with retrieved context]
  → answer + citations (moment ids)
  → save agent_message
```

**Guardrail:** агент отвечает только на основе retrieved моментов/фактов. Если ничего не нашлось — честно говорит «не помню, расскажи мне».

### 6.4. Facts extraction (background job)

После каждого нового момента — фоновая задача `extract_facts_from_moment(moment_id)`:
- Если в моменте упомянут человек → создать/обновить `fact(kind=person, key=normalized_name)`.
- Если место — то же с `kind=place`.
- Если предпочтение («я не ем мясо», «я люблю кофе без сахара») — `kind=preference`.

Promt: `src/services/llm/prompts/extract_facts.md`.

### 6.5. Утренний дайджест

Джоба на `digest_hour` каждого пользователя:
```
gather today's moments (occurs_at between now and +24h)
  + upcoming birthdays (next 7 days)
  + habits due today
  → [DeepSeek: digest_write prompt with characterguide]
  → send push + inbox message
```

### 6.6. Характер ассистента — встроен в промпты

Каждый генерирующий промпт включает блок `@characterguide` из §2.9. Один файл, подключается через include.

---

## 7. Mobile app (Flutter) — архитектура

### 7.1. Стек (frozen)

| Область | Выбор | Почему |
|---|---|---|
| Язык | Dart 3.x | нативный Flutter |
| State | Riverpod + StateNotifier | текущий выбор, user prefers handwritten |
| Router | `go_router` | декларативный, хорошо для 4 табов + deep links |
| HTTP | Dio + AuthInterceptor | JWT refresh со single-flight |
| Local DB | `drift` (sqlite) | нужно для офлайна, full-text search локально |
| Secure storage | `flutter_secure_storage` | JWT/refresh |
| Audio record | `record` + `path_provider` | **Opus 16 kbps**, mono, 16kHz |
| **On-device STT** | `speech_to_text: ^7.x` | обёртка SFSpeech (iOS) + SpeechRecognizer (Android). Default канал. |
| VAD (M6+) | `silero-vad` через FFI или native wrapper | вырезание тишины до upload |
| Audio play | `just_audio` | |
| Push | `firebase_messaging` + FCM | |
| Payments | `webview_flutter` + YooKassa WebView | mandated RU |
| i18n | `flutter_localizations` + ARB | централизованный copy |
| Analytics | `firebase_analytics` + собственный `/events` endpoint | продуктовая аналитика |
| Crash | `firebase_crashlytics` | |
| Tests | `flutter_test`, `mocktail`, `patrol` (e2e) | |

**Запрещено:** `json_serializable`, `freezed` в MVP (уже решено — user preference). Hand-written `fromJson`/`toJson`.

### 7.2. Структура папок

```
mobile/lib/
├── main.dart
├── app.dart
├── core/
│   ├── config/            (env, endpoints)
│   ├── network/           (DioClient, AuthInterceptor, ApiException)
│   ├── storage/           (SecureStorage, LocalDb drift)
│   ├── routing/           (AppRouter, guards)
│   ├── theme/             (MX tokens, typography, colors)
│   ├── widgets/           (общие: MxButton, MxCard, MxSheet, MxEmpty)
│   ├── l10n/              (ARB файлы)
│   └── utils/             (date_fmt, rrule_fmt, haptics)
├── features/
│   ├── auth/
│   │   ├── data/          (AuthRepository, dto)
│   │   ├── domain/        (AuthController StateNotifier)
│   │   └── presentation/  (LoginScreen, RegisterScreen, ResetScreen)
│   ├── onboarding/
│   ├── moments/           (единственная фича-слой данных — общая для today/timeline/rhythm)
│   │   ├── data/          (MomentRepository, MomentDto, local sync)
│   │   └── domain/        (MomentsController, providers: todayProvider, timelineProvider, rhythmProvider)
│   ├── today/             (только UI, читает todayProvider)
│   ├── timeline/          (UI + поиск)
│   ├── rhythm/            (UI: habits heatmap, cycles)
│   ├── moment_details/    (S10)
│   ├── voice_capture/     (S11)
│   ├── agent/             (S14, интегрирован в timeline search)
│   ├── profile/
│   ├── billing/           (paywall + webview)
│   └── push/              (FCM wiring)
└── shared/
    ├── models/            (Moment, User, Fact, AgentMessage)
    └── extensions/
```

**Удалить существующие разделы `features/notes`, `features/habits`, `features/birthdays`, `features/shopping_list`, `features/tasks`, `features/ai_agent` после миграции UI на `moments`.**

### 7.3. Ключевые инженерные решения

- **Офлайн-first для capture.** Любой новый момент сразу пишется в drift с `sync_status=pending`. Отдельный `SyncWorker` шлёт батчем на `/moments/bulk`. UI никогда не ждёт сети.
- **Todo-list и Хроника читают drift**, не API напрямую. API — источник истины при синхронизации; между синхронизациями показываем локал.
- **Синхронизация:** pull на запуске + pull-to-refresh + push при успешной отправке own change. Инкрементальный pull по `updated_at > last_sync_at`.
- **Аудио не sync'ается офлайн.** Если нет сети — аудио лежит локально, `audio_url` проставляется после первого успешного upload.
- **Темы:** light/dark. Dark — бесплатная функция (не Pro). Системная по умолчанию.
- **Haptics:** `HapticFeedback.mediumImpact` на FAB press, `selectionClick` на свайпы.

### 7.4. Навигация (go_router)

```
/                    → SplashGuard → /today | /auth/login | /onboarding
/onboarding          → steps 1-3
/auth/login, /auth/register, /auth/reset
/today               (tab)
/timeline            (tab)
/rhythm              (tab)
/profile             (tab)
/moment/:id          (push)
/capture             (modal, fullscreen-dialog)
/paywall             (modal)
/billing/yk/:url     (webview modal)
/settings            (push из profile)
```

### 7.5. Тест-стратегия

- Unit: все Controllers + Repositories (мок Dio, мок drift) — покрытие ≥ 70 %.
- Widget: каждый screen имеет golden-test с `empty`, `loaded`, `error` состояниями.
- Integration (patrol): 5 сценариев:
  1. Онбординг → первый момент → появление в Сегодня.
  2. Создать напоминание голосом → получить пуш → complete.
  3. Создать привычку → отметить 3 дня → увидеть streak.
  4. Спросить ИИ → получить ответ с цитатой.
  5. Paywall → оплата (тестовый магазин YooKassa).

---

## 8. Платежи (YooKassa)

### 8.1. Планы

| Код | Цена | Доступ |
|---|---|---|
| `pro_monthly` | **400 ₽/мес** | Вся память, агент, проактив, безлимит на практике |
| `pro_yearly` | **3 490 ₽/год** | То же, выгоднее ~27 % |

### 8.2. Pro-функции (единственный список)

1. **Память глубже 30 дней** в Хронике (semantic search и просмотр).
2. **Вопросы к ИИ** (`/agent/ask`) — Claude Haiku на твоих данных.
3. **«Что я о тебе знаю»** — facts-извлечение из моментов (у Free — только сырые моменты, без персонального портрета).
4. **Проактивные подсказки** — ассистент сам пишет *«давно не звонил папе, у него ДР через неделю»*.
5. **Детекция конфликтов** расписания.
6. **Pre-reminders** (напомнить за N минут).
7. **Расширенные лимиты голоса** (30 мин серверного STT/день против 2 у Free; on-device у обоих без лимита).
8. **Импорт данных** (M10) — Telegram-экспорт, текстовые файлы.
9. **Активный вопросник о себе** (M10, S16).

**Всё, что не в списке — бесплатно.** Это закрывает вопрос «а это Pro или нет» раз и навсегда.

### 8.3. Flow

1. Пользователь жмёт «Pro» (из Профиля или paywall-сценария).
2. `POST /billing/subscribe` → получает `confirmation_url`.
3. Открывается WebView → YooKassa confirm.
4. Возврат на `app://billing/callback`.
5. Клиент дергает `GET /billing/status` до тех пор, пока не `pro_until > now()` (или до таймаута 30с).
6. Параллельно сервер получает webhook от YooKassa → обновляет `subscriptions` и `users.pro_until`.

### 8.4. Paywall-триггеры (где показывать)

- При попытке спросить ИИ.
- При попытке свайпнуть хронику дальше 30 дней.
- При превышении 30 минут голоса в сутки (с объяснением).
- Один раз в неделю на экране Профиль (баннер).

**Запрещено:** показывать paywall при открытии приложения, мешать основному loop.

---

## 9. Push-уведомления

### 9.1. Каналы (Android) / категории (iOS)

| ID | Когда |
|---|---|
| `reminder` | Напоминание по моменту с `occurs_at` |
| `habit_check` | Ежедневный прогон привычек |
| `digest` | Утренний дайджест |
| `proactive` | Проактивные подсказки (Pro) |
| `system` | Ошибки оплаты, смена пароля |

### 9.2. Payload-схема

```json
{
  "type": "reminder",
  "moment_id": 12345,
  "title": "Купить молоко",
  "body": "Через 30 минут — магазин у дома.",
  "actions": ["done", "snooze_1h"],
  "deep_link": "app://moment/12345"
}
```

Actions обрабатываются даже без открытия приложения (iOS notification actions, Android notification buttons) — через background isolate, который дергает `POST /moments/{id}/complete`.

---

## 10. Безопасность и приватность

### 10.1. Данные

- JWT: HS256, secret из env, ротация refresh при каждом использовании.
- Пароли: argon2id (moderate profile).
- Голосовые файлы: хранятся 30 дней, потом удаляются (cron job).
- Эмбеддинги удаляются вместе с моментом.
- GDPR: `DELETE /auth/delete` → soft-delete, через 14 дней — полное удаление каскадом.

### 10.2. Юридическое

- Политика конфиденциальности (ru, en): обязательна для сторов. Шаблон в `docs/legal/PRIVACY.md`.
- Пользовательское соглашение: `docs/legal/TERMS.md`.
- Оферта публичного договора (152-ФЗ для RU): `docs/legal/OFFER.md`.
- Все три — хостятся на `voicenote.ai/legal/*`, линки в настройках и в сторах.
- 152-ФЗ: хостинг БД в РФ (или согласие на трансгран). Для MVP — хостинг в РФ.

### 10.3. Secrets

Все секреты в env, загружаются через Pydantic Settings. Никаких `.env` в репо. `firebase-service-account.json` на сервере — монтируется через docker secrets.

---

## 11. Инфраструктура и деплой

### 11.1. Backend

- Python 3.12, FastAPI, Uvicorn за gunicorn.
- Docker image: multi-stage, ~150 МБ.
- БД: PostgreSQL 16 + pgvector, managed (Yandex.Cloud или Timeweb RU).
- Redis 7 — тот же provider.
- Audio storage: S3-совместимое (Yandex Object Storage).
- Деплой: GitHub Actions → docker push → compose pull на VPS.
- Healthcheck: `GET /health` возвращает 200 + версии.

### 11.2. Миграции

Alembic. Каждая миграция реверсируемая (down()). CI проверяет `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` на тестовой БД.

### 11.3. Мониторинг

- Sentry (errors, performance) — backend + mobile.
- Prometheus-метрики через `/metrics` (latency percentiles, LLM cost).
- Uptime: UptimeRobot на `/health`.

### 11.4. Логи

JSON-структурированный stdout → docker log driver → Loki (post-MVP, для MVP хватит docker logs).

### 11.5. Бэкапы

- БД: pg_dump ежедневно, хранение 14 дней.
- S3: встроенное версионирование.

---

## 12. Аналитика и метрики

### 12.1. Events (фиксированный список)

```
app_open
onboarding_step_completed  { step }
moment_created             { source, kind }
moment_completed
voice_capture_started
voice_capture_saved        { duration_ms, latency_ms }
agent_question_asked       { is_pro }
paywall_shown              { trigger }
paywall_purchased          { plan }
push_opened                { type }
screen_view                { screen }
```

Шлём и в Firebase Analytics, и в собственный `POST /events` (батчем каждые 30 сек).

### 12.2. Dashboards

- Retention cohorts (D1/D7/D30)
- Moments per DAU
- Voice latency P50/P95
- LLM cost per DAU
- Pro conversion rate

---

## 13. Store submission

### 13.1. Общие ассеты

- Иконка: 1024×1024 PNG, без прозрачности.
- Feature graphic (Android): 1024×500.
- Скриншоты: 6.5" iPhone (5 шт), 5.5" iPhone (5 шт), Android phone (5 шт), Android 7" tablet (3 шт).
- Превью-видео: 30 сек, вертикальное, 1080×1920. Сценарий: голос → момент → напоминание → ответ ИИ.
- Текст описания: короткое (80 симв) + длинное (4000 симв). Шаблоны в `docs/store/`.
- Ключевые слова (AppStore): голосовые заметки, напоминания, дневник, ассистент, память, привычки.

### 13.2. App Store (iOS)

- App ID в Apple Developer.
- Provisioning, certificates — через Fastlane match.
- Privacy manifest (`PrivacyInfo.xcprivacy`) — обязателен с 2024.
- Data collection disclosure: email, voice, usage. Не шлём рекламным сетям.
- App Review Information: тестовый аккаунт с Pro.
- Пометка про голос: «Приложение использует микрофон для записи голосовых заметок. Аудио обрабатывается на наших серверах и удаляется через 30 дней.»

### 13.3. Google Play

- Play Console, signing by Google.
- Data safety form: email, voice, crash data. Encrypted in transit, deletable on request.
- Target SDK: latest required.
- AAB билд, не APK.
- Политика о подписках: auto-renew disclosure, cancel instructions.

### 13.4. YooKassa review

- Юрлицо/ИП подключено.
- Возврат средств: политика в оферте (7 дней на отказ по подписке).
- Webhook URL подтверждён.

---

## 14. План выполнения (милстоуны)

Каждый милстоун = PR + acceptance criteria. Следующий не начинается, пока предыдущий не зелёный.

### M0 — Подготовка (1 неделя)
- Заморозить репозиторий legacy (ветка `legacy-v0.9.2`).
- Создать чистую ветку `v1.0`.
- Удалить `ANALYSIS_IMPROVEMENTS.md`, `FEATURE_IDEAS.md`, `IMPROVEMENTS_SUGGESTIONS.md`, `IMPROVED_PROMPTS_EXAMPLES.py`, `weather_test.py`, `apple-touch-icon.png`, `CNAME`, `index.html`, `favicon.ico` (артефакты не относящиеся к продукту).
- Этот план — в `docs/PRODUCT_PLAN.md` (уже здесь).

**Acceptance:** чистый tree, один план, ничего не удалено из работающего кода без миграции.

### M1 — Backend foundation
- Схема БД из §4.
- Alembic миграции: `V1__init.sql` (новая схема), `V2__import_legacy.sql` (перенос).
- Auth endpoints (§5.2 auth).
- Health + configs + logger.
- Unit-тесты модели и auth.

**Acceptance:** новая БД стоит, старые данные перенесены на staging, `/auth/*` работают, тесты зелёные.

### M2 — Moments API + LLM pipeline
- `POST /moments`, `GET /moments`, `/moments/{id}/*` endpoints.
- `/voice/moment` с STT (SaluteSpeech + Yandex fallback).
- **LLMRouter и STTRouter абстракции** с политикой fallback (§6.0). Никаких прямых импортов провайдеров в бизнес-логике.
- Промпты `extract_facets`, `extract_facts`.
- **Skip-LLM heuristics** для тривиальных моментов (§6.7.1).
- **BGE-M3 self-hosted** на CPU бэка, batch-очередь.
- APScheduler интеграция (reminders, digest).
- **RateLimiter middleware** с дневными лимитами (§5.1).
- Pytest: ≥ 40 тестов, P95 latency voice→moment ≤ 4с (server-STT) / ≤ 1.5с (on-device) на staging.

**Acceptance:** через curl можно создать момент голосом, получить напоминание, отметить выполненным. LLMRouter логирует стоимость каждого вызова.

### M3 — Agent + Facts (Pro-only)
- **Caddy reverse-proxy на Hetzner** для `api.anthropic.com`, env `ANTHROPIC_BASE_URL` в бэке.
- `/agent/ask`, `/agent/history` через Claude Haiku 4.5.
- Redis-кэш ответов на 10 мин.
- Facts extraction async job (только для Pro-юзеров).
- `GET/POST/PATCH/DELETE /facts`.
- RAG с pgvector, top-10 моментов + top-5 фактов.
- Guardrails: ответы только с цитатами, fallback «не помню».
- Graceful degradation: Claude Haiku → DeepSeek-V3 при 5xx/квоте.

**Acceptance:** Pro-юзер получает осмысленные ответы с цитатами. Facts накапливаются только для Pro. В логах виден свитч на fallback при симулированном отказе Anthropic.

### M4 — Mobile core shell
- Проект Flutter, структура §7.2.
- Routing, theme, l10n, localization.
- Auth screens + онбординг.
- Dio + drift + secure storage.
- Splash guard.

**Acceptance:** можно зарегистрироваться, пройти онбординг, увидеть пустой экран «Сегодня».

### M5 — Mobile: Capture + Today + Timeline
- **Voice capture модал (S11) с on-device STT как default.** Opus 16 kbps. Fallback на server-STT для длинных.
- Today tab (S6).
- Timeline tab (S7) + поиск (literal).
- Moment details (S10).
- Офлайн-sync через drift + `client_id` идемпотентность.
- Client-side telemetry: сколько секунд on-device, сколько server-STT, latency.

**Acceptance:** голосом создаю момент на iOS и Android → на обоих on-device STT работает → он в Сегодня → свайп done работает → Timeline показывает историю → офлайн-создание синхронизируется. Средняя доля server-STT < 20 % по нашей телеметрии.

### M6 — Mobile: Rhythm + Profile + Agent + Facts UI
- Rhythm tab (S8).
- Shopping as view (фильтр в Timeline + иконка в Today).
- Profile (S9) + настройки (timezone, digest_hour, темы, подключение Telegram-канала).
- **S15 «Что я о тебе знаю»** — список facts с группировкой, редактирование, удаление.
- AI question в Timeline search (интеграция с `/agent/ask`), paywall triggers.
- VAD на клиенте (опционально, если успевает).

**Acceptance:** все 4 таба работают, ИИ отвечает с цитатами, paywall показывается в нужных триггерах, Pro-юзер видит свои накопленные facts в S15 и может их править.

### M7 — Push + Billing
- FCM + notification channels.
- Pushes через `PushService` (reminder, digest, habit_check).
- Notification actions (done/snooze) через background handler.
- YooKassa subscribe flow + webhook + status poll.
- Paywall (S12).

**Acceptance:** пуш пришёл, done через пуш закрыл момент, оплатил Pro — через 10 сек приложение знает.

### M8 — Polish + Store prep
- Golden-tests всех экранов.
- 5 patrol e2e тестов.
- Sentry + Firebase Analytics.
- Аудио cleanup job.
- Store-ассеты.
- Legal docs на домене.
- TestFlight + Google Play Internal Testing.
- Beta: 20 пользователей, 2 недели, фиксы.

**Acceptance:** crash-free ≥ 99.5 %, ретеншн на бете D7 ≥ 20 %, ответы YooKassa/Apple/Google — ок.

### M9 — Release
- App Store + Google Play submission.
- Мониторинг первых 72 часов.
- Hotfix-стратегия: feature flags через `/profile` response для rollback.

### M10 — Learning (post-MVP, через 4–8 недель после M9)
Вторая волна. Большая маркетинговая фича.

- **S16 «Расскажи о себе»** — активный вопросник из 5–7 голосовых/текстовых вопросов.
- **S17 «Импорт данных»** — Telegram JSON export и текстовые файлы.
- Бэкенд:
  - `import_jobs` таблица (§4.12)
  - `/import/telegram`, `/import/text`, `/import/{job_id}` endpoints
  - `/learning/about-me/answer`
  - Async worker (RQ или Celery) для bulk-обработки
  - Chunking по 50 сообщений, прогресс в реальном времени
  - Авто-удаление исходных файлов после обработки
- Privacy: экран-предупреждение + явное согласие перед upload
- PR/маркетинг: «ассистент теперь знает тебя с первой минуты»

**Acceptance:** Pro-юзер загружает Telegram-экспорт → через N минут получает экран «я узнал 23 близких человека и 47 незакрытых обещаний, смотрим?». Может удалить всё одной кнопкой.

### M11+ — Триггерные оптимизации (по метрикам, не по календарю)

- **≥ 500 DAU:** бенчмарки self-hosted Whisper на аренде RTX 4090 на сутки, подсчёт окупаемости.
- **≥ 3000 DAU:** переход на self-hosted Whisper Large v3 + faster-whisper на собственном GPU-VPS. SaluteSpeech отключается.
- **≥ 5000 DAU:** эксперимент с self-hosted Qwen 2.5 7B / Llama 3.1 для facet extraction.
- **≥ 10000 DAU:** full in-house stack, внешние API только для агента.

---

## 15. Роли и границы агентов

Чтобы параллельные AI-агенты не мешали друг другу:

| Агент | Область ответственности | Файлы, которые трогает |
|---|---|---|
| `backend-agent` | FastAPI, БД, LLM, APScheduler | `src/**`, `alembic/**`, `tests/**` |
| `mobile-agent` | Flutter | `mobile/**` |
| `devops-agent` | Docker, CI, миграции деплоя | `Dockerfile`, `.github/**`, `docker-compose.yml` |
| `copy-agent` | Все тексты UI, пуши, дайджест | `mobile/lib/core/l10n/*.arb`, `src/services/llm/prompts/*.md` |
| `bot-agent` | Telegram-бот как канал ввода | `src/bot/**` (упрощённый, только capture) |

**Правила взаимодействия:**
- Никакой агент не меняет `docs/PRODUCT_PLAN.md`, `alembic/versions/*`, `src/web/api/schemas.py` без явной записи в CHANGELOG этого документа.
- Контракт API (§5.2) — ground truth. Mobile и Backend синхронизируются только через него.
- Формат `facets` (§4.2) — меняется только через миграцию.

---

## 16. Telegram-бот: статус legacy-канала и чистка репозитория

### 16.1. Бот — правила существования после v1.0

Бот **не удаляется**, но радикально ужимается. Причина: Telegram забанен в РФ (основной рынок), работает в BY/UA/KZ, существующие юзеры сидят там. Убивать — терять, но строить на нём UX — тоже нельзя.

**Что оставляем в боте:**
- Приём голосовых → создание момента
- Приём текста → создание момента
- Пересылка сообщений → создание момента
- Inline-кнопки на push-уведомлениях: *выполнено* / *отложить*
- Одна команда `/link_email email@…` для bot-only юзеров, которые хотят переехать в мобилу

**Что удаляем из бота полностью:**
- Меню, inline-клавиатуры вне пуш-уведомлений
- Команды `/notes`, `/reminders`, `/habits`, `/shopping`, `/birthdays`, `/stats`, `/settings`
- FSM-state для создания чего-либо через диалог
- Админ-панель (переезжает в web-админку или убирается до post-MVP)
- Любые экраны выбора «это заметка или напоминание?» — теперь всё через LLM автоматически

**Маркетинг и онбординг:**
- Сторы, лендинг, реклама говорят **только** про мобильное приложение.
- В онбординге мобилы бот **не упоминается**.
- Единственная точка подключения бота — в Профиле → «Подключить Telegram (опционально)», глубоко спрятана.

### 16.2. Файлы на удаление (в M0)

Артефакты старой эпохи, создают шум:

- `ANALYSIS_IMPROVEMENTS.md`
- `FEATURE_IDEAS.md`
- `IMPROVEMENTS_SUGGESTIONS.md`
- `IMPROVED_PROMPTS_EXAMPLES.py`
- `weather_test.py`
- `apple-touch-icon.png`, `favicon.ico`, `CNAME`, `index.html` (артефакты неуказанного назначения)
- `src/services/gamification_service.py` + `src/migrate_gamification.py` (гейм не делаем)
- `src/services/weather_service.py` (не в продукте MVP)
- `mobile/lib/features/notes`, `features/habits`, `features/birthdays`, `features/shopping_list`, `features/tasks`, `features/ai_agent` — после миграции UI на `features/moments`.
- В `src/bot/`: все handlers кроме capture (`voice.py`, `text.py`, `forward.py`) и `notifications.py` (inline-кнопки на пушах). См. §16.1.

---

## 17. Открытые решения, которые должен принять владелец (до M1)

Заморозить явно, иначе будут пересмотры.

**Закрыто:**
- ✅ **Цены Pro:** 400 ₽/мес, 3 490 ₽/год (v1.1, 2026-04-22).
- ✅ **Anthropic gateway:** свой Caddy-прокси на Hetzner (v1.1, 2026-04-22).
- ✅ **STT-стратегия:** on-device first, SaluteSpeech fallback, без GPU-VPS в MVP (v1.1).
- ✅ **Эмбеддинги:** self-hosted BGE-M3 на CPU бэка, vector(1024).
- ✅ **Telegram-бот:** legacy-канал без экранов, §16.

**Открыто (решить до M1):**

1. **Хостинг БД:** Yandex.Cloud Managed Postgres vs Timeweb vs собственный VPS с postgres-контейнером. Рекомендую Yandex.Cloud (152-ФЗ из коробки + pgvector).
2. **Регион аудио-хранилища:** Yandex Object Storage, бакет `ru-central1` — подтвердить.
3. **Юрлицо для YooKassa:** ИП или ООО? От этого зависит оферта.
4. **Название в сторах:** «VoiceNote AI» — есть ли конфликты по trademark? Проверить перед M8.
5. **Месячный AI-бюджет:** 300 000 ₽ (§18.2) — это потолок паники. Реалистичный план при 1000 DAU — 30 000 ₽/мес. Подтвердить порог.

---

## 18. AI-экономика и мониторинг (frozen)

### 18.1. Принцип: предсказуемость важнее оптимальности

Разработка ведётся так, чтобы **никакой пользователь и никакой всплеск активности не мог привести к неконтролируемому сгоранию токенов**. Если выбор стоит между «сделать ответ умнее» и «сделать расход предсказуемым» — выбираем второе.

### 18.2. Четыре слоя защиты от burn-through

**Слой 1: Hard-лимиты на уровне юзера** (см. §5.1). Enforced в `RateLimiter` middleware, Redis counters, reset в 00:00 UTC. Free юзер физически не может потратить больше лимита в день.

**Слой 2: Месячный бюджетный потолок приложения.** Хардкод в admin-config: 300 000 ₽/мес на всю ИИ-инфру. При 50 % — info в Telegram админа, при 80 % — warning, при 100 % — автоматический режим деградации (слой 4).

**Слой 3: Per-user дневной cost-ceiling.** Каждый вызов `LLMRouter`/`STTRouter` пишет стоимость в Redis по ключу `cost:user:{id}:{YYYY-MM-DD}`. Лимит: Free — 5 ₽/день, Pro — 30 ₽/день. Абьюзеры получают throttle: *«ты сегодня активно общаешься, дай отдышусь»*. Статистика топ-10 абьюзеров — в Grafana.

**Слой 4: Graceful degradation.**
- При исчерпании дневного бюджета агента → Claude Haiku → DeepSeek-V3 молча.
- При падении DeepSeek → GigaChat-Lite / YandexGPT Lite.
- При падении всех — honest error в характере ассистента: *«Извини, я сегодня перегружен. Попробуй через час.»* Никаких 5xx для юзера.

### 18.3. Метрики и алерты (Grafana-дашборд «AI economy»)

Шесть обязательных панелей, смотрим ежедневно:

1. **₽/день по каждой задаче** (STT / DeepSeek / Anthropic / другое) — stacked area chart.
2. **₽/DAU сегодня** — gauge, целевой ≤ 10 ₽.
3. **₽/Pro-юзер за 7 дней** — должно быть ≤ 60 ₽ (при цене 400 и марже > 0).
4. **Top-10 самых дорогих юзеров за 24ч** — таблица, ссылка на user_id, сигнал об абьюзе.
5. **Прогноз расхода до конца месяца** — линейная экстраполяция текущей day-rate.
6. **Unit-economics** — Revenue (от YooKassa) − AI cost. Positive / negative для прошлых 30 дней.

Алерты в Telegram админа:
- `ai.daily_cost > 15 000 ₽` → warning
- `ai.user.cost > 50 ₽/день` → investigate-alert
- `ai.provider.5xx_rate > 5 %` → fallback-alert
- `ai.monthly_budget.usage > 80 %` → emergency-alert

### 18.4. Логирование стоимости

Каждый вызов `LLMRouter.chat(...)` / `STTRouter.recognize(...)` пишет в таблицу `ai_usage`:

```sql
CREATE TABLE ai_usage (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(id),
    task        TEXT NOT NULL,       -- 'facet_extract' | 'agent_ask' | 'stt_server' | ...
    provider    TEXT NOT NULL,       -- 'deepseek' | 'claude-haiku' | 'salute' | ...
    input_tokens  INTEGER,
    output_tokens INTEGER,
    audio_seconds INTEGER,
    cost_rub      NUMERIC(10,4) NOT NULL,
    latency_ms    INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_usage_user_day ON ai_usage(user_id, created_at);
CREATE INDEX idx_ai_usage_task_day ON ai_usage(task, created_at);
```

Из этой таблицы питаются все 6 панелей Grafana.

### 18.5. Юнит-экономика — расчётная модель

Базовые предположения для MVP (при on-device STT default):

| Метрика | Free DAU | Pro DAU |
|---|---|---|
| Server-STT минут/день | ~0.3 (20 % всех голосовых) | ~2 |
| DeepSeek вызовов/день | 3 | 10 |
| Claude Haiku вопросов/день | 0 | 3 |
| Embeddings/день | 0 (только Pro или 30d) | 10 |
| **Итого стоимость/день** | **~0.2 ₽** | **~8 ₽** |
| Revenue/день | 0 | 13.3 ₽ (400/30) |
| **Маржа/день** | −0.2 ₽ | **+5.3 ₽** |

**Сценарии масштаба:**

| DAU | Free:Pro | Выручка/мес | AI-расход/мес | **Итого** |
|---|---|---|---|---|
| 300 | 290:10 | 4 000 | 3 400 | +600 ₽ (около нуля) |
| 1 000 | 900:100 | 40 000 | 29 400 | +10 600 ₽ |
| 3 000 | 2 700:300 | 120 000 | 88 200 | +31 800 ₽ (точка для GPU-перехода) |
| 10 000 | 9 000:1 000 | 400 000 | 294 000 | +106 000 ₽ |

**Wildcard риски:**
- Если on-device STT доля падает ниже 70 % → стоимость Pro DAU растёт линейно. Триггер: мониторить `stt_server_share` метрику.
- Если Claude Haiku дорожает / блокируется → перейти на DeepSeek-V3 для агента (слой 4).
- Если DeepSeek вводит rate limits → включить GigaChat-Lite (fallback уже в коде).

### 18.6. Правило инженеров

Добавляешь новый LLM-вызов в код?
1. Сначала иди в §6.0 и добавь его в таблицу с явным primary/fallback.
2. В `LLMRouter` опиши стоимость вызова.
3. Оцени: **сколько это будет стоить на 1000 DAU в день?** Если > 500 ₽/день — пересмотри задачу.
4. Добавь в `ai_usage` логирование.
5. Протестируй degradation: что произойдёт, если провайдер упал?

Без этих пяти шагов PR не мержится.

---

## CHANGELOG

- **2026-04-22 (v1.0)** — первая заморозка плана. Автор — консолидация концепции + анализ текущего репо.
- **2026-04-22 (v1.1)** — внесены решения владельца:
  - Pricing: Pro 400 ₽/мес, 3 490 ₽/год (было 299 / 2 490).
  - Telegram-бот понижен до legacy-канала, §16 переписан.
  - Добавлены экраны S15 (MVP), S16+S17 (M10).
  - Добавлен новый милстоун M10 «Learning» и M11+ триггерные оптимизации.
  - AI-стек зафиксирован: on-device STT default, SaluteSpeech fallback, DeepSeek-V3, self-hosted BGE-M3 (vector(1024)), Claude Haiku 4.5 через свой Hetzner-прокси.
  - Отказ от GPU-VPS в MVP из-за финансов. Whisper self-host — при ≥ 3000 DAU.
  - Добавлен раздел §6.0 (распределение провайдеров с fallback политиками) и §18 (AI-экономика и мониторинг).
  - Добавлены дневные rate-limits в §5.1.
  - Добавлена таблица `ai_usage` (§18.4) и `import_jobs` (§4.12).
  - Обновлены милстоуны M2, M3, M5, M6 с учётом новых требований.
