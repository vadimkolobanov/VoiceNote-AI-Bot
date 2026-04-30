'use client';

import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';

interface FadeUpProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}

export default function FadeUp({ children, delay = 0, className = '' }: FadeUpProps) {
  const { ref, isVisible } = useIntersectionObserver();
  return (
    <div
      ref={ref}
      className={`fade-up ${isVisible ? 'visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}
