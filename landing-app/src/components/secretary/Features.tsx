'use client';

import FadeUp from '@/components/ui/FadeUp';

type Feature = {
  title: string;
  body: string;
  accent: string;
  iconPath: string;
  pro?: boolean;
};

const FEATURES: Feature[] = [
  {
    title: 'Голос за секунду',
    body:
      'Зажми микрофон — наговори как другу. Распознавание идёт прямо на устройстве, текст уходит на сервер уже готовым.',
    accent: '#00E5FF',
    iconPath:
      'M9 2h6v12a3 3 0 0 1-3 3 3 3 0 0 1-3-3z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3',
  },
  {
    title: 'Я разложу сам',
    body:
      'Из «завтра в 10 встреча с Аней» появится момент с временем и связью с человеком. Из «жена работает в Сбере» — факт в твою память.',
    accent: '#00E5FF',
    iconPath: 'M3 6h18M3 12h18M3 18h12',
  },
  {
    title: 'Помню всех твоих',
    body:
      'Имена, роли, привычки, места. Про Дианку завтра — это про твою жену Диану из Сбера, не про новую персону. Память не плодит дубли.',
    accent: '#A78BFA',
    iconPath:
      'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  },
  {
    title: 'Привычки по-человечески',
    body:
      'Зарядка по утрам — не «задача со статусом». Это ритм. Сегодня выполнил — отметил, завтра она снова в Сегодня.',
    accent: '#A78BFA',
    iconPath:
      'M17 1l4 4-4 4 M3 11V9a4 4 0 0 1 4-4h14 M7 23l-4-4 4-4 M21 13v2a4 4 0 0 1-4 4H3',
  },
  {
    title: 'Просрочил — увижу',
    body:
      'Карточки, до которых не дошли руки, выделены красным. Дайджест утром: 3 в работе, 2 готово, 1 просрочено — не теряется.',
    accent: '#FF6B6B',
    iconPath:
      'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01',
  },
  {
    title: 'Спроси меня — я помню',
    body:
      '«Когда я последний раз говорил про маму?» — найду по смыслу, не по словам. Семантический поиск по всей твоей истории.',
    accent: '#00E5FF',
    iconPath: 'M21 21l-4.35-4.35 M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0z',
    pro: true,
  },
  {
    title: 'Inline-кнопки в пуше',
    body:
      'Напоминание пришло — тапнул «Готово» прямо на уведомлении, не открывая приложение. Или «+15 мин», если не сейчас.',
    accent: '#34D399',
    iconPath:
      'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0',
  },
  {
    title: 'Расскажи — я выпишу',
    body:
      'Отдельный режим: рассказываешь длинно про себя, близких, привычки. Я разбираю и складываю в память. В Хронику ничего не уходит.',
    accent: '#34D399',
    iconPath:
      'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8',
  },
  {
    title: 'Удалить — одним тапом',
    body:
      'Профиль → «Удалить мою память». Без писем, без retention-окошек. Уйдёт всё: моменты, привычки, факты, токены устройств.',
    accent: '#FF6B6B',
    iconPath:
      'M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2',
  },
];

export default function Features() {
  return (
    <section
      id="features"
      className="relative py-24 md:py-32"
      style={{ background: '#09090b' }}
    >
      <div className="max-w-[1280px] mx-auto px-6">
        <FadeUp>
          <div className="max-w-3xl mb-14 md:mb-20">
            <div
              className="inline-block px-3 py-1.5 rounded-full text-[11px] tracking-widest mb-5"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.6)',
              }}
            >
              ВОЗМОЖНОСТИ
            </div>
            <h2
              className="text-3xl sm:text-4xl md:text-5xl font-semibold text-white mb-5 tracking-[-0.02em] leading-tight"
              style={{ fontFamily: 'var(--font-space)' }}
            >
              Не приложение для заметок.
              <br />
              <span style={{ color: 'rgba(255,255,255,0.5)' }}>
                Внешняя память твоей жизни.
              </span>
            </h2>
            <p className="text-[17px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Каждая фича — про одну простую вещь: меньше думать о том, как
              запомнить. Больше — о том, что важно прямо сейчас.
            </p>
          </div>
        </FadeUp>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
          {FEATURES.map((f, i) => (
            <FadeUp key={f.title} delay={(i % 3) * 0.05}>
              <div
                className="group relative h-full p-7 rounded-3xl transition-all duration-300"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                {f.pro && (
                  <div
                    className="absolute top-5 right-5 px-2 py-0.5 rounded-full text-[10px] tracking-widest font-semibold"
                    style={{
                      background: 'rgba(0,229,255,0.12)',
                      color: '#00E5FF',
                      border: '1px solid rgba(0,229,255,0.3)',
                    }}
                  >
                    PRO
                  </div>
                )}
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center mb-5"
                  style={{
                    background: `${f.accent}15`,
                    border: `1px solid ${f.accent}30`,
                  }}
                >
                  <svg
                    width={20}
                    height={20}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={f.accent}
                    strokeWidth={1.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d={f.iconPath} />
                  </svg>
                </div>
                <h3
                  className="text-[19px] font-semibold mb-3 text-white"
                  style={{ fontFamily: 'var(--font-space)', letterSpacing: '-0.01em' }}
                >
                  {f.title}
                </h3>
                <p className="text-[13.5px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>
                  {f.body}
                </p>
              </div>
            </FadeUp>
          ))}
        </div>
      </div>
    </section>
  );
}
