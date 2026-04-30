'use client';

import { useState } from 'react';
import FadeUp from '@/components/ui/FadeUp';

const ITEMS: { q: string; a: string }[] = [
  {
    q: 'Где хранятся мои данные?',
    a: 'На сервере в России. Подключение по HTTPS, доступ — только по твоему токену. Не отдаём третьим сервисам, не используем для обучения моделей. Распознавание голоса работает прямо на устройстве — голос не покидает телефон, мы получаем уже текст.',
  },
  {
    q: 'Что если у меня нет интернета?',
    a: 'Чтобы сохранить момент, нужен интернет — он уходит на сервер для разбора и связей. Голос распознаётся прямо на устройстве, поэтому говорить можно даже в плохой связи: текст подождёт момента, когда сеть появится.',
  },
  {
    q: 'Кто-то ещё видит мои моменты?',
    a: 'Никто. Не показываем рекламодателям, не передаём в обучение моделей, не делимся с третьими сервисами. Это не оговорка — это бизнес-модель.',
  },
  {
    q: 'Как удалить всё?',
    a: 'Профиль → «Удалить мою память». Подтверждение в один тап — и всё уходит с сервера: моменты, привычки, факты, токены устройств. Без писем «вы уверены» и retention-окошек.',
  },
  {
    q: 'Это правда понимает русский?',
    a: 'Да. Распознавание речи и связи строятся на русскоязычной модели. Ругательства, имена, города, разговорные конструкции — всё на месте.',
  },
  {
    q: 'Что такое «факты», и чем они отличаются от моментов?',
    a: 'Момент — это разовое: «завтра встреча с Аней в 10». Факт — долгоиграющее: «жену зовут Диана, она работает в Сбере». Факты накапливаются автоматически из твоей речи и помогают мне отвечать осмысленно — «когда я последний раз говорил про маму?» работает только если я знаю, кто такая мама.',
  },
  {
    q: 'Что если я случайно создам неправильную привычку?',
    a: 'Открыл «Что я о тебе знаю» → удалил факт. То же самое с моментами — свайп, корзина. Без подтверждений, без задержек.',
  },
  {
    q: 'Pro и Free — что реально отличается?',
    a: 'Free покрывает базовое: голос, моменты, привычки, напоминания, дайджест. Pro нужен только если хочется AI-агента, который ищет по смыслу и автоматически вытаскивает факты из каждой записи. Платишь за память, которая работает на тебя.',
  },
  {
    q: 'Будет ли версия для iPhone?',
    a: 'Будет. Сейчас Android — там можно собирать память без ограничений системы. iOS-версия в работе, без точной даты.',
  },
];

function Item({ q, a, open, onToggle }: { q: string; a: string; open: boolean; onToggle: () => void }) {
  return (
    <div
      className="border-b transition-colors"
      style={{ borderColor: 'rgba(255,255,255,0.06)' }}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-6 py-6 text-left"
      >
        <span
          className="text-[17px] md:text-[18px] font-medium leading-[1.4] text-white"
          style={{ fontFamily: 'var(--font-space)', letterSpacing: '-0.01em' }}
        >
          {q}
        </span>
        <span
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center transition-transform duration-300"
          style={{
            background: 'rgba(255,255,255,0.06)',
            transform: open ? 'rotate(45deg)' : 'rotate(0)',
          }}
        >
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth={1.6} strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </span>
      </button>
      <div
        className="overflow-hidden transition-all duration-400"
        style={{
          maxHeight: open ? 240 : 0,
          opacity: open ? 1 : 0,
        }}
      >
        <p
          className="pb-6 text-[15px] leading-[1.65] max-w-[720px]"
          style={{ color: 'rgba(255,255,255,0.6)' }}
        >
          {a}
        </p>
      </div>
    </div>
  );
}

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="relative py-24 md:py-32" style={{ background: '#0c0c0f' }}>
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
      <div className="max-w-[860px] mx-auto px-6">
        <FadeUp>
          <div className="text-center mb-12 md:mb-16">
            <div
              className="inline-block px-3 py-1.5 rounded-full text-[11px] tracking-widest mb-5"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.6)',
              }}
            >
              ВОПРОСЫ
            </div>
            <h2
              className="text-3xl sm:text-4xl md:text-5xl font-semibold text-white tracking-[-0.02em] leading-tight"
              style={{ fontFamily: 'var(--font-space)' }}
            >
              Коротко и без воды.
            </h2>
          </div>
        </FadeUp>

        <FadeUp delay={0.05}>
          <div>
            {ITEMS.map((it, i) => (
              <Item
                key={it.q}
                q={it.q}
                a={it.a}
                open={open === i}
                onToggle={() => setOpen(open === i ? null : i)}
              />
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  );
}
