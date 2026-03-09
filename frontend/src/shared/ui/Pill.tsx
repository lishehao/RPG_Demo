import type { ReactNode } from 'react';
import { cn } from '@/shared/lib/cn';

type PillProps = {
  children: ReactNode;
  tone?: 'neutral' | 'low' | 'medium' | 'high' | 'success';
};

const toneClasses = {
  neutral: 'bg-[rgba(255,248,229,0.12)] text-[var(--text-mist)] border border-[rgba(255,232,206,0.12)]',
  low: 'bg-[rgba(158,203,107,0.24)] text-[#e7f8c8] border border-[rgba(158,203,107,0.24)]',
  medium: 'bg-[rgba(255,209,102,0.22)] text-[#fff1c2] border border-[rgba(255,209,102,0.22)]',
  high: 'bg-[rgba(255,138,61,0.24)] text-[#ffd0b1] border border-[rgba(255,138,61,0.24)]',
  success: 'bg-[rgba(120,220,170,0.22)] text-[#d4ffe9] border border-[rgba(120,220,170,0.2)]',
} as const;

export function Pill({ children, tone = 'neutral' }: PillProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.14em]', toneClasses[tone])}>
      {children}
    </span>
  );
}
