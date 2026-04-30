import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <div
        className="text-[120px] leading-none font-semibold mb-4"
        style={{
          fontFamily: 'var(--font-space)',
          background: 'linear-gradient(135deg, #00E5FF 0%, #A78BFA 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          letterSpacing: '-0.04em',
        }}
      >
        404
      </div>
      <h1
        className="text-2xl md:text-3xl font-semibold mb-3"
        style={{ fontFamily: 'var(--font-space)' }}
      >
        Страница не найдена
      </h1>
      <p className="max-w-sm mb-8" style={{ color: 'rgba(255,255,255,0.55)' }}>
        Может быть, опечатка в адресе. Или эту страницу мы ещё не сделали.
      </p>
      <Link
        href="/"
        className="inline-flex items-center h-11 px-6 rounded-full bg-white text-black hover:bg-neutral-200 transition-colors text-[14px] font-semibold"
        style={{ fontFamily: 'var(--font-space)' }}
      >
        На главную
      </Link>
    </div>
  );
}
