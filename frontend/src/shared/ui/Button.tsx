import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { cn } from '@/shared/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost';

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> & {
  variant?: Variant;
  wide?: boolean;
};

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-[linear-gradient(135deg,rgba(239,126,69,0.96),rgba(245,179,111,0.84))] text-[#21140e] shadow-[0_16px_36px_rgba(239,126,69,0.24)] hover:brightness-105',
  secondary:
    'border border-[var(--line)] bg-[rgba(255,248,229,0.06)] text-[var(--text-ivory)] hover:border-[var(--line-strong)] hover:bg-[rgba(255,248,229,0.1)]',
  ghost:
    'text-[var(--text-mist)] hover:bg-[rgba(255,248,229,0.05)] hover:text-[var(--text-ivory)]',
};

export function Button({ children, className, variant = 'primary', wide = false, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-full px-5 py-3 text-sm font-extrabold tracking-[0.08em] uppercase transition disabled:cursor-not-allowed disabled:opacity-50',
        wide && 'w-full',
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
