'use client';

import FadeUp from '@/components/ui/FadeUp';

const RU_STORE_URL = 'https://www.rustore.ru/';

const FREE = [
  'Голосовой ввод и моменты без лимитов',
  'Привычки с дневным трекингом',
  'Напоминания + утренний дайджест',
  'Inline-кнопки в пушах',
  'Память и факты — последние 30 дней',
];

const PRO = [
  'Всё из Free',
  'Спроси меня — AI-агент с поиском по всей памяти',
  'Авто-извлечение фактов из каждой записи',
  'Безлимитная история',
  'Режим «Расскажи о себе» — обучение памяти',
  'Семантический поиск по моментам',
];

export default function Pricing() {
  return (
    <section id="pricing" className="relative py-24 md:py-32" style={{ background: '#09090b' }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <FadeUp>
          <div className="max-w-3xl mb-14 md:mb-20 text-center mx-auto">
            <div
              className="inline-block px-3 py-1.5 rounded-full text-[11px] tracking-widest mb-5"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.6)',
              }}
            >
              ТАРИФЫ
            </div>
            <h2
              className="text-3xl sm:text-4xl md:text-5xl font-semibold text-white mb-5 tracking-[-0.02em] leading-tight"
              style={{ fontFamily: 'var(--font-space)' }}
            >
              Бесплатно для всех.
              <br />
              <span style={{ color: 'rgba(255,255,255,0.5)' }}>
                Pro — для тех, кому нужен агент.
              </span>
            </h2>
            <p className="text-[16px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Первые 7 дней Pro даём попробовать без оплаты. Дальше — отказался,
              остаёшься на Free, ничего не теряешь.
            </p>
          </div>
        </FadeUp>

        <div className="grid md:grid-cols-2 gap-5 max-w-[920px] mx-auto">
          {/* Free */}
          <FadeUp>
            <div
              className="relative h-full p-8 md:p-10 rounded-[28px]"
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="text-[13px] tracking-widest mb-3" style={{ color: 'rgba(255,255,255,0.55)' }}>
                FREE
              </div>
              <div
                className="flex items-baseline gap-2 mb-2"
                style={{ fontFamily: 'var(--font-space)' }}
              >
                <span className="text-[44px] font-semibold text-white tracking-[-0.02em]">0 ₽</span>
                <span className="text-[14px]" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  навсегда
                </span>
              </div>
              <p className="text-[14px] leading-relaxed mb-7" style={{ color: 'rgba(255,255,255,0.55)' }}>
                Всё, что нужно для базовой памяти. Без рекламы, без срока.
              </p>
              <a
                href={RU_STORE_URL}
                target="_blank"
                rel="noreferrer"
                className="block text-center w-full h-12 leading-[3rem] rounded-full transition-colors text-[14px] font-medium mb-7"
                style={{
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: 'rgba(255,255,255,0.85)',
                  fontFamily: 'var(--font-space)',
                }}
              >
                Начать бесплатно
              </a>
              <ul className="space-y-3">
                {FREE.map((f) => (
                  <Item key={f} text={f} />
                ))}
              </ul>
            </div>
          </FadeUp>

          {/* Pro */}
          <FadeUp delay={0.05}>
            <div
              className="relative h-full p-8 md:p-10 rounded-[28px]"
              style={{
                background:
                  'linear-gradient(180deg, rgba(0,229,255,0.06) 0%, rgba(167,139,250,0.04) 100%), rgba(255,255,255,0.02)',
                border: '1px solid rgba(0,229,255,0.25)',
                boxShadow: '0 0 80px rgba(0,229,255,0.08)',
              }}
            >
              <div
                className="absolute -top-3 left-10 px-3 py-1 rounded-full text-[10px] tracking-widest font-semibold"
                style={{
                  background: '#00E5FF',
                  color: '#000',
                }}
              >
                СПРОСИ МЕНЯ
              </div>
              <div className="text-[13px] tracking-widest mb-3" style={{ color: '#00E5FF' }}>
                PRO
              </div>
              <div
                className="flex items-baseline gap-2 mb-2"
                style={{ fontFamily: 'var(--font-space)' }}
              >
                <span className="text-[44px] font-semibold text-white tracking-[-0.02em]">
                  390 ₽
                </span>
                <span className="text-[14px]" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  / месяц
                </span>
              </div>
              <p className="text-[14px] leading-relaxed mb-7" style={{ color: 'rgba(255,255,255,0.55)' }}>
                Память, которая отвечает. Не просто хранит — понимает по смыслу.
              </p>
              <a
                href={RU_STORE_URL}
                target="_blank"
                rel="noreferrer"
                className="block text-center w-full h-12 leading-[3rem] rounded-full bg-white text-black hover:bg-neutral-200 transition-colors text-[14px] font-semibold mb-7"
                style={{ fontFamily: 'var(--font-space)' }}
              >
                Попробовать Pro 7 дней
              </a>
              <ul className="space-y-3">
                {PRO.map((f) => (
                  <Item key={f} text={f} highlight />
                ))}
              </ul>
            </div>
          </FadeUp>
        </div>
      </div>
    </section>
  );
}

function Item({ text, highlight }: { text: string; highlight?: boolean }) {
  return (
    <li className="flex items-start gap-3 text-[13.5px] leading-[1.55]">
      <svg
        width={16}
        height={16}
        viewBox="0 0 24 24"
        fill="none"
        stroke={highlight ? '#00E5FF' : '#34D399'}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="flex-shrink-0 mt-0.5"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
      <span style={{ color: highlight ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.65)' }}>
        {text}
      </span>
    </li>
  );
}
