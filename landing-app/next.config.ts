import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Standalone-сборка: оптимально для Timeweb Apps / любого Node-хостинга.
  // Создаёт минимальный self-contained `.next/standalone/` со всеми
  // зависимостями для запуска через `node server.js`.
  output: 'standalone',
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
