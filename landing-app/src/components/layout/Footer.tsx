export default function Footer() {
  return (
    <footer
      className="border-t py-12"
      style={{
        background: '#09090b',
        borderColor: 'rgba(255,255,255,0.06)',
      }}
    >
      <div className="max-w-[1280px] mx-auto px-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center gap-2.5">
          <span
            className="w-6 h-6 rounded-full"
            style={{
              background:
                'radial-gradient(circle at 50% 40%, #00E5FF, #00B8D4 60%, #064a5c 100%)',
              boxShadow: '0 0 10px rgba(0,229,255,0.35)',
            }}
          />
          <span
            className="text-[13px] font-medium"
            style={{ fontFamily: 'var(--font-space)', color: 'rgba(255,255,255,0.85)' }}
          >
            Metodex Секретарь
          </span>
        </div>
        <nav className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[12px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
          <a href="/privacy" className="hover:text-white transition-colors">Политика конфиденциальности</a>
          <a href="/terms" className="hover:text-white transition-colors">Соглашение</a>
          <a href="mailto:hello@metodex.ru" className="hover:text-white transition-colors">hello@metodex.ru</a>
        </nav>
        <div className="text-[12px]" style={{ color: 'rgba(255,255,255,0.35)' }}>
          © {new Date().getFullYear()} Metodex
        </div>
      </div>
    </footer>
  );
}
