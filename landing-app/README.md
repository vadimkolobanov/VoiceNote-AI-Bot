# Metodex Секретарь — Landing

Self-contained лендинг для нашего мобильного приложения. Отдельный от
бэкенда (`/src` в корне репо) и от мобилки (`/mobile`). Деплоится самостоятельно.

## Стек

- Next.js 15 + React 19 + TypeScript
- Tailwind 4
- Шрифты: Inter (body) + Space Grotesk (display) через `next/font`
- Никаких внешних API, всё статическое

## Локальная разработка

```bash
cd landing-app
npm install
npm run dev
```

Откроется `http://localhost:3000`.

## Сборка для прода

```bash
npm run build
npm start                 # запуск Node-сервера на порту 3000
```

`next.config.ts` использует `output: 'standalone'` — после `npm run build`
в `.next/standalone/` лежит самодостаточная сборка с минимумом
зависимостей. Это оптимально для Timeweb Apps и любого Node-хостинга.

## Деплой на Timeweb Apps

1. Создай в панели Timeweb Apps новое приложение типа **Node.js**.
2. Подключи этот репозиторий, укажи Working Directory — `landing-app/`.
3. Build command: `npm install && npm run build`
4. Start command: `npm start`
5. Port: `3000`
6. После первого деплоя в панели Timeweb привяжи свой домен
   (`secretary.metodex.ru` или любой) — Timeweb сам выпустит
   Let's Encrypt сертификат.

## Что внутри

- `src/app/page.tsx` — главная (Hero · Features · AppPreview · Pricing · FAQ · CTA)
- `src/app/not-found.tsx` — 404
- `src/app/layout.tsx` — корневой layout, шрифты, метаданные
- `src/app/globals.css` — Tailwind + кастомные `.fade-up` анимации

- `src/components/layout/` — шапка и футер
- `src/components/ui/FadeUp.tsx` — обёртка с IntersectionObserver-анимацией
- `src/components/secretary/` — 6 секций лендинга:
  - `Hero.tsx` — заголовок + анимированный мокап телефона
  - `Features.tsx` — 9 плиток возможностей
  - `AppPreview.tsx` — fake-окно «Что я о тебе знаю»
  - `Pricing.tsx` — Free + Pro
  - `FAQ.tsx` — 9 вопросов
  - `CTA.tsx` — финальный download-блок

- `src/hooks/useIntersectionObserver.ts` — хук для FadeUp

## TODO

- В `Hero`, `Pricing`, `CTA`, `Header` ссылка на RuStore = `https://www.rustore.ru/`
  (плейсхолдер). Подменишь на реальный URL карточки приложения после публикации.
- `/privacy` и `/terms` страницы — пока не сделаны, но в Footer ссылки уже есть.
