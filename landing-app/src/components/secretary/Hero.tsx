'use client';

import { useEffect, useState } from 'react';
import FadeUp from '@/components/ui/FadeUp';

const RU_STORE_URL = 'https://www.rustore.ru/'; // TODO: подставить реальный URL после публикации

type Demo = {
  kind: 'task' | 'habit' | 'note' | 'birthday';
  title: string;
  hint: string;
  when: string;
};

const DEMO: Demo[] = [
  { kind: 'task', title: 'Позвонить маме про дачу', hint: 'обещание', when: 'Сегодня · 18:00' },
  { kind: 'habit', title: 'Зарядка', hint: 'каждое утро', when: 'Завтра · 07:00' },
  { kind: 'note', title: 'Жена Диана работает в Сбере', hint: 'факт о близком', when: 'Сохранено в память' },
  { kind: 'birthday', title: 'ДР Жени', hint: 'не забыть поздравить', when: '23 апреля' },
  { kind: 'task', title: 'Купить торт на ДР Дианы', hint: 'связал с ДР жены', when: 'За 2 дня' },
];

const ICON: Record<Demo['kind'], { color: string; path: string; label: string }> = {
  task: {
    color: '#00E5FF',
    path: 'M12 6v6l4 2',
    label: 'Напоминание',
  },
  habit: {
    color: '#A78BFA',
    path: 'M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3',
    label: 'Привычка',
  },
  note: {
    color: '#34D399',
    path: 'M12 3l1.8 4.8L18 9l-4.2 1.2L12 15l-1.8-4.8L6 9l4.2-1.2z',
    label: 'Факт',
  },
  birthday: {
    color: '#FBBF24',
    path: 'M20 12v10H4V12M2 7h20v5H2zM12 22V7M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7zM12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z',
    label: 'ДР',
  },
};

function PhoneMock() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 2400);
    return () => clearInterval(id);
  }, []);
  const visible = Math.min(DEMO.length, 2 + (tick % (DEMO.length - 1)));

  return (
    <div className="relative mx-auto" style={{ maxWidth: 360 }}>
      {/* Glow */}
      <div
        className="absolute inset-0 -z-10 blur-3xl opacity-40"
        style={{
          background: 'radial-gradient(circle at 50% 40%, rgba(0,229,255,0.45), transparent 60%)',
        }}
      />
      <div
        className="rounded-[36px] overflow-hidden border"
        style={{
          background: '#0c0c0f',
          borderColor: 'rgba(255,255,255,0.08)',
          boxShadow: '0 50px 120px rgba(0,0,0,0.55)',
        }}
      >
        {/* Status bar */}
        <div
          className="h-9 flex items-center justify-between px-5 text-[10px] tracking-widest"
          style={{ color: 'rgba(255,255,255,0.5)' }}
        >
          <span>09:41</span>
          <span className="font-mono">●●● 100%</span>
        </div>

        {/* App header */}
        <div className="px-5 pt-3 pb-4">
          <div className="text-[10px] tracking-[0.2em]" style={{ color: '#00E5FF' }}>
            METODEX · СЕГОДНЯ
          </div>
          <div
            className="mt-1 text-[22px] font-semibold leading-tight"
            style={{ fontFamily: 'var(--font-space)', letterSpacing: '-0.02em' }}
          >
            Доброе утро.
            <br />
            <span style={{ color: 'rgba(255,255,255,0.55)' }}>3 в работе · 1 просрочено</span>
          </div>
        </div>

        {/* Items */}
        <div className="px-3 pb-3 space-y-2">
          {DEMO.slice(0, visible).map((d, i) => {
            const ic = ICON[d.kind];
            return (
              <div
                key={`${d.title}-${i}`}
                className="flex items-start gap-3 p-3 rounded-2xl border transition-all duration-500"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  borderColor: 'rgba(255,255,255,0.06)',
                  animation: i === visible - 1 ? 'fadeInRow 0.6s ease' : undefined,
                }}
              >
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: `${ic.color}15` }}
                >
                  <svg
                    width={16}
                    height={16}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={ic.color}
                    strokeWidth={1.6}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d={ic.path} />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium" style={{ color: '#fff' }}>
                    {d.title}
                  </div>
                  <div
                    className="text-[11px] mt-0.5"
                    style={{ color: 'rgba(255,255,255,0.45)' }}
                  >
                    {ic.label} · {d.when}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Mic FAB */}
        <div className="px-5 pt-3 pb-7 flex justify-center">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center"
            style={{
              background: 'radial-gradient(circle at 50% 40%, #00E5FF, #00B8D4 65%, #007a99 100%)',
              boxShadow: '0 0 40px rgba(0,229,255,0.4), 0 8px 16px rgba(0,0,0,0.4)',
            }}
          >
            <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="2" width="6" height="12" rx="3" />
              <path d="M5 10v2a7 7 0 0 0 14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
          </div>
        </div>
      </div>
      <style jsx>{`
        @keyframes fadeInRow {
          from {
            opacity: 0;
            transform: translateY(-6px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}

export default function Hero() {
  return (
    <section
      className="relative pt-32 pb-24 md:pt-40 md:pb-32 overflow-hidden"
      style={{ background: '#09090b' }}
    >
      {/* Soft cyan halo behind text */}
      <div
        className="absolute inset-0 -z-10 opacity-50"
        style={{
          background:
            'radial-gradient(ellipse at 25% 30%, rgba(0,229,255,0.10), transparent 55%)',
        }}
      />
      <div className="max-w-[1280px] mx-auto px-6 grid lg:grid-cols-[1.1fr_0.9fr] gap-16 items-center">
        <FadeUp>
          <div>
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] tracking-widest mb-7"
              style={{
                background: 'rgba(0,229,255,0.08)',
                border: '1px solid rgba(0,229,255,0.25)',
                color: '#00E5FF',
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: '#00E5FF', boxShadow: '0 0 8px #00E5FF' }}
              />
              ГОЛОСОВОЙ AI · ВТОРОЙ МОЗГ
            </div>
            <h1
              className="text-[44px] sm:text-[56px] md:text-[68px] font-semibold leading-[1.02] tracking-[-0.03em] text-white"
              style={{ fontFamily: 'var(--font-space)' }}
            >
              Говори мне всё.
              <br />
              Я <span style={{ color: '#00E5FF' }}>запомню</span>, напомню
              <br />
              и со временем стану тобой.
            </h1>
            <p
              className="mt-7 text-[18px] leading-[1.6] max-w-[560px]"
              style={{ color: 'rgba(255,255,255,0.65)' }}
            >
              Зажми микрофон, расскажи как другу — момент, мысль, обещание.
              Я разложу по полочкам, свяжу с прошлым и подскажу, когда нужно.
            </p>

            <div className="mt-10 flex flex-wrap gap-3">
              <a
                href={RU_STORE_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 h-13 px-7 rounded-full bg-white text-black hover:bg-neutral-200 transition-colors text-[15px] font-semibold"
                style={{ fontFamily: 'var(--font-space)', height: 52 }}
              >
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                </svg>
                Скачать в RuStore
              </a>
              <a
                href="#features"
                className="inline-flex items-center gap-2 h-13 px-7 rounded-full transition-colors text-[15px] font-medium"
                style={{
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: 'rgba(255,255,255,0.85)',
                  fontFamily: 'var(--font-space)',
                  height: 52,
                }}
              >
                Узнать больше →
              </a>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-[13px]">
              <span className="flex items-center gap-2" style={{ color: 'rgba(255,255,255,0.55)' }}>
                <Dot color="#34D399" />
                Голос — на устройстве
              </span>
              <span className="flex items-center gap-2" style={{ color: 'rgba(255,255,255,0.55)' }}>
                <Dot color="#34D399" />
                Без трекеров
              </span>
              <span className="flex items-center gap-2" style={{ color: 'rgba(255,255,255,0.55)' }}>
                <Dot color="#34D399" />
                Без рекламы
              </span>
            </div>
          </div>
        </FadeUp>

        <FadeUp delay={0.08}>
          <PhoneMock />
        </FadeUp>
      </div>
    </section>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />;
}
