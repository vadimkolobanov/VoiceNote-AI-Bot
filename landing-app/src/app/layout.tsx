import type { Metadata } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-inter',
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Metodex Секретарь — голосовой AI и второй мозг',
  description:
    'Зажми микрофон, расскажи как другу — момент, мысль, обещание. Я разложу по полочкам, свяжу с прошлым, напомню вовремя. Без рекламы, без трекеров, голос распознаётся прямо на устройстве.',
  keywords: [
    'голосовой ассистент',
    'AI-секретарь',
    'второй мозг',
    'память',
    'привычки',
    'напоминания',
    'голосовые заметки',
    'Methodex',
    'Метод­екс',
  ],
  openGraph: {
    title: 'Metodex Секретарь — голосовой AI и второй мозг',
    description:
      'Голос → момент за 1 секунду. Помню всех твоих близких. Подсказываю, когда забыл.',
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Metodex',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body>{children}</body>
    </html>
  );
}
