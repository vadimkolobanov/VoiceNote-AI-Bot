'use client';

import FadeUp from '@/components/ui/FadeUp';

const FACTS = [
  { kind: 'person', label: 'Диана', sub: 'жена · Сбер на Кутузовском', accent: '#A78BFA' },
  { kind: 'person', label: 'Миша', sub: 'сын · 4 года', accent: '#A78BFA' },
  { kind: 'preference', label: 'не ем мясо', sub: 'предпочтение', accent: '#34D399' },
  { kind: 'schedule', label: 'бегаю по утрам в 7', sub: 'ритм', accent: '#FBBF24' },
  { kind: 'place', label: 'дом мамы в Истре', sub: 'место', accent: '#00E5FF' },
];

const HABIT_DAYS = [1, 1, 1, 0, 1, 1, 1]; // пн-вс

export default function AppPreview() {
  return (
    <section id="preview" className="relative py-24 md:py-32" style={{ background: '#0c0c0f' }}>
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
      <div className="max-w-[1280px] mx-auto px-6">
        <FadeUp>
          <div className="max-w-3xl mb-14 md:mb-20">
            <div
              className="inline-block px-3 py-1.5 rounded-full text-[11px] tracking-widest mb-5"
              style={{
                background: 'rgba(0,229,255,0.06)',
                border: '1px solid rgba(0,229,255,0.18)',
                color: '#00E5FF',
              }}
            >
              ВНУТРИ ПРИЛОЖЕНИЯ
            </div>
            <h2
              className="text-3xl sm:text-4xl md:text-5xl font-semibold text-white mb-5 tracking-[-0.02em] leading-tight"
              style={{ fontFamily: 'var(--font-space)' }}
            >
              Память растёт сама.
              <br />
              <span style={{ color: 'rgba(255,255,255,0.5)' }}>Тебе остаётся жить.</span>
            </h2>
            <p className="text-[17px] leading-relaxed max-w-[640px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Из любого голосового сообщения я вытаскиваю долгоиграющие факты
              — близких, места, привычки — и связываю их в единый профиль.
              Чем больше говоришь, тем умнее ответы.
            </p>
          </div>
        </FadeUp>

        <FadeUp delay={0.1}>
          <div
            className="rounded-3xl overflow-hidden border"
            style={{
              background: '#09090b',
              borderColor: 'rgba(255,255,255,0.08)',
              boxShadow: '0 60px 140px rgba(0,0,0,0.55)',
            }}
          >
            {/* Window chrome */}
            <div
              className="h-10 flex items-center gap-2 px-4 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.06)' }}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ff5f57' }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#febc2e' }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#28c840' }} />
              <div className="ml-4 text-[11px] tracking-wide" style={{ color: 'rgba(255,255,255,0.4)' }}>
                Metodex · Что я о тебе знаю
              </div>
            </div>

            <div className="grid lg:grid-cols-[260px_1fr]">
              {/* Sidebar */}
              <div
                className="p-5 border-r"
                style={{
                  background: 'rgba(255,255,255,0.015)',
                  borderColor: 'rgba(255,255,255,0.06)',
                }}
              >
                <div className="text-[10px] tracking-widest mb-4" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  ПАМЯТЬ
                </div>
                {[
                  { label: 'Люди', n: 8, color: '#A78BFA' },
                  { label: 'Места', n: 4, color: '#00E5FF' },
                  { label: 'Привычки', n: 3, color: '#FBBF24' },
                  { label: 'Предпочтения', n: 6, color: '#34D399' },
                ].map((c) => (
                  <div
                    key={c.label}
                    className="flex items-center justify-between py-2.5 px-3 rounded-xl mb-1"
                    style={{ background: 'rgba(255,255,255,0.02)' }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.color }} />
                      <span className="text-[13px]" style={{ color: 'rgba(255,255,255,0.85)' }}>
                        {c.label}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono" style={{ color: 'rgba(255,255,255,0.45)' }}>
                      {c.n}
                    </span>
                  </div>
                ))}

                <div className="mt-7 text-[10px] tracking-widest mb-4" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  СЕРИИ ПРИВЫЧЕК
                </div>
                <div className="px-3 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="flex items-center justify-between mb-2.5">
                    <span className="text-[13px]" style={{ color: 'rgba(255,255,255,0.85)' }}>
                      Зарядка
                    </span>
                    <span
                      className="text-[11px] font-semibold"
                      style={{ color: '#FBBF24' }}
                    >
                      🔥 6 дней
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {HABIT_DAYS.map((d, i) => (
                      <div
                        key={i}
                        className="flex-1 h-6 rounded-md"
                        style={{
                          background: d ? 'rgba(251,191,36,0.7)' : 'rgba(255,255,255,0.06)',
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Main */}
              <div className="p-7">
                <div className="grid grid-cols-3 gap-3 mb-7">
                  <Stat label="Всего фактов" value="34" accent="#00E5FF" />
                  <Stat label="Сегодня" value="3 · 1" sub="готово · просрочено" accent="#34D399" />
                  <Stat label="Активных" value="12" accent="#A78BFA" />
                </div>

                <div className="text-[10px] tracking-widest mb-3" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  ИЗВЛЕЧЕНО АВТОМАТИЧЕСКИ
                </div>
                <div className="space-y-2">
                  {FACTS.map((f) => (
                    <div
                      key={f.label}
                      className="flex items-center gap-4 px-4 py-3 rounded-2xl border"
                      style={{
                        background: 'rgba(255,255,255,0.02)',
                        borderColor: 'rgba(255,255,255,0.05)',
                      }}
                    >
                      <div
                        className="w-8 h-8 rounded-lg flex-shrink-0"
                        style={{ background: `${f.accent}20`, border: `1px solid ${f.accent}40` }}
                      />
                      <div className="flex-1">
                        <div className="text-[14px] font-medium" style={{ color: '#fff' }}>
                          {f.label}
                        </div>
                        <div className="text-[12px]" style={{ color: 'rgba(255,255,255,0.45)' }}>
                          {f.sub}
                        </div>
                      </div>
                      <div
                        className="text-[10px] tracking-wider px-2 py-0.5 rounded-full"
                        style={{
                          background: 'rgba(52,211,153,0.10)',
                          color: '#34D399',
                          border: '1px solid rgba(52,211,153,0.25)',
                        }}
                      >
                        AI
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
}) {
  return (
    <div
      className="px-4 py-4 rounded-2xl border"
      style={{
        background: `${accent}08`,
        borderColor: `${accent}25`,
      }}
    >
      <div className="text-[11px] tracking-widest mb-1.5" style={{ color: 'rgba(255,255,255,0.5)' }}>
        {label}
      </div>
      <div
        className="text-[26px] font-semibold leading-none"
        style={{ fontFamily: 'var(--font-space)', color: '#fff', letterSpacing: '-0.02em' }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[11px] mt-1.5" style={{ color: 'rgba(255,255,255,0.45)' }}>
          {sub}
        </div>
      )}
    </div>
  );
}
