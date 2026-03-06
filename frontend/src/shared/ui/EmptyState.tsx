import type { ReactNode } from 'react';

type EmptyStateProps = {
  title: string;
  body: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="rounded-[28px] border border-dashed border-[var(--line-strong)] bg-[rgba(255,248,229,0.04)] px-6 py-10 text-center">
      <div className="mx-auto max-w-xl">
        <p className="text-xs uppercase tracking-[0.24em] text-[var(--text-dim)]">Awaiting Signal</p>
        <h3 className="mt-3 font-[var(--font-title)] text-2xl tracking-[0.06em]">{title}</h3>
        <div className="mt-3 text-sm leading-7 text-[var(--text-mist)]">{body}</div>
        {action ? <div className="mt-6">{action}</div> : null}
      </div>
    </div>
  );
}
