'use client';

import FadeUp from '@/components/ui/FadeUp';

const RU_STORE_URL = 'https://www.rustore.ru/';

export default function CTA() {
  return (
    <section className="relative py-24 md:py-32" style={{ background: '#09090b' }}>
      <div className="max-w-[1100px] mx-auto px-6">
        <FadeUp>
          <div
            className="relative rounded-3xl px-8 py-16 md:py-20 text-center overflow-hidden"
            style={{
              background:
                'linear-gradient(135deg, rgba(0,229,255,0.08) 0%, rgba(167,139,250,0.05) 50%, rgba(255,255,255,0.02) 100%)',
              border: '1px solid rgba(0,229,255,0.18)',
            }}
          >
            {/* Decorative glow orbs */}
            <div
              className="absolute -top-16 -left-16 w-72 h-72 rounded-full blur-3xl opacity-40"
              style={{ background: 'radial-gradient(circle, #00E5FF, transparent 70%)' }}
            />
            <div
              className="absolute -bottom-16 -right-16 w-72 h-72 rounded-full blur-3xl opacity-30"
              style={{ background: 'radial-gradient(circle, #A78BFA, transparent 70%)' }}
            />

            <div className="relative">
              <h2
                className="text-3xl sm:text-4xl md:text-5xl font-semibold text-white mb-5 tracking-[-0.02em] leading-[1.1]"
                style={{ fontFamily: 'var(--font-space)' }}
              >
                Начни помнить за&nbsp;себя.
              </h2>
              <p
                className="text-[16px] md:text-[18px] mb-10 max-w-[560px] mx-auto"
                style={{ color: 'rgba(255,255,255,0.65)' }}
              >
                Бесплатно. Email и пароль — и сразу в дело.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-3">
                <a
                  href={RU_STORE_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 px-7 rounded-full bg-white text-black hover:bg-neutral-200 transition-colors text-[15px] font-semibold"
                  style={{ fontFamily: 'var(--font-space)', height: 52 }}
                >
                  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                  </svg>
                  Скачать в RuStore
                </a>
                <span className="text-[14px]" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  APK напрямую · скоро в Google Play
                </span>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}
