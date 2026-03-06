import type { ReactNode } from 'react';
import { cn } from '@/shared/lib/cn';

type PillProps = {
  children: ReactNode;
  tone?: 'neutral' | 'low' | 'medium' | 'high' | 'success';
};

const toneClasses = {
  neutral: 'bg-[rgba(255,248,229,0.08)] text-[var(--text-mist)]',
  low: 'bg-[rgba(139,154,98,0.18)] text-[#dbe8b6]',
  medium: 'bg-[rgba(245,179,111,0.18)] text-[#f7d5a1]',
  high: 'bg-[rgba(239,126,69,0.18)] text-[#ffc3a6]',
  success: 'bg-[rgba(120,192,156,0.18)] text-[#b9f0d3]',
} as const;

export function Pill({ children, tone = 'neutral' }: PillProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.14em]', toneClasses[tone])}>
      {children}
    </span>
  );
}
