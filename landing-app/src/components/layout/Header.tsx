'use client';

import { useEffect, useState } from 'react';

const NAV = [
  { href: '#features', label: 'Возможности' },
  { href: '#preview', label: 'Внутри' },
  { href: '#pricing', label: 'Тарифы' },
  { href: '#faq', label: 'Вопросы' },
];

const RU_STORE_URL = 'https://www.rustore.ru/';

export default function Header() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 6);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className="fixed top-0 inset-x-0 z-50 transition-all"
      style={{
        background: scrolled ? 'rgba(9,9,11,0.85)' : 'transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: scrolled
          ? '1px solid rgba(255,255,255,0.06)'
          : '1px solid transparent',
      }}
    >
      <div className="max-w-[1280px] mx-auto px-6 h-16 flex items-center justify-between">
        <a href="/" className="flex items-center gap-2.5">
          <span
            className="w-7 h-7 rounded-full"
            style={{
              background:
                'radial-gradient(circle at 50% 40%, #00E5FF, #00B8D4 60%, #064a5c 100%)',
              boxShadow: '0 0 12px rgba(0,229,255,0.4)',
            }}
          />
          <span
            className="text-[15px] font-semibold tracking-tight"
            style={{ fontFamily: 'var(--font-space)', color: '#fff' }}
          >
            Metodex<span style={{ color: 'rgba(255,255,255,0.45)' }}> · Секретарь</span>
          </span>
        </a>
        <nav className="hidden md:flex items-center gap-7">
          {NAV.map((n) => (
            <a
              key={n.href}
              href={n.href}
              className="text-[13px] transition-colors"
              style={{ color: 'rgba(255,255,255,0.6)' }}
            >
              {n.label}
            </a>
          ))}
        </nav>
        <a
          href={RU_STORE_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center h-9 px-4 rounded-full bg-white text-black hover:bg-neutral-200 transition-colors text-[13px] font-semibold"
          style={{ fontFamily: 'var(--font-space)' }}
        >
          Скачать
        </a>
      </div>
    </header>
  );
}
