import type { PropsWithChildren, ReactNode } from 'react';
import { cn } from '@/shared/lib/cn';

type PanelProps = PropsWithChildren<{
  eyebrow?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  className?: string;
}>;

export function Panel({ eyebrow, title, subtitle, className, children }: PanelProps) {
  return (
    <section className={cn('grain-panel rounded-[28px] p-5 md:p-6', className)}>
      {eyebrow || title || subtitle ? (
        <header className="mb-5">
          {eyebrow ? <p className="text-xs uppercase tracking-[0.26em] text-[var(--text-dim)]">{eyebrow}</p> : null}
          {title ? <h2 className="mt-3 font-[var(--font-title)] text-2xl tracking-[0.06em]">{title}</h2> : null}
          {subtitle ? <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-mist)]">{subtitle}</p> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}
