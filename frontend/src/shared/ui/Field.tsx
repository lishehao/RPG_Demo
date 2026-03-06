import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react';
import { cn } from '@/shared/lib/cn';

type BaseProps = {
  label: string;
  hint?: string;
  rightSlot?: ReactNode;
};

type InputFieldProps = BaseProps &
  InputHTMLAttributes<HTMLInputElement> & {
    multiline?: false;
  };

type TextareaFieldProps = BaseProps &
  TextareaHTMLAttributes<HTMLTextAreaElement> & {
    multiline: true;
  };

export function Field(props: InputFieldProps | TextareaFieldProps) {
  if (props.multiline) {
    const { label, hint, rightSlot, className, multiline: _multiline, ...rest } = props;

    return (
      <label className="block space-y-3">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span className="font-semibold uppercase tracking-[0.18em] text-[var(--text-dim)]">{label}</span>
          {rightSlot}
        </div>

        <textarea
          className={cn(
            'min-h-28 w-full rounded-[24px] border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-3 text-[var(--text-ivory)] outline-none transition placeholder:text-[var(--text-dim)] focus:border-[rgba(239,126,69,0.62)] focus:bg-[rgba(255,248,229,0.08)]',
            className,
          )}
          {...rest}
        />

        {hint ? <p className="text-sm text-[var(--text-dim)]">{hint}</p> : null}
      </label>
    );
  }

  const { label, hint, rightSlot, className, multiline: _multiline, ...rest } = props;

  return (
    <label className="block space-y-3">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold uppercase tracking-[0.18em] text-[var(--text-dim)]">{label}</span>
        {rightSlot}
      </div>

      <input
        className={cn(
          'w-full rounded-full border border-[var(--line)] bg-[rgba(255,248,229,0.05)] px-4 py-3 text-[var(--text-ivory)] outline-none transition placeholder:text-[var(--text-dim)] focus:border-[rgba(239,126,69,0.62)] focus:bg-[rgba(255,248,229,0.08)]',
          className,
        )}
        {...rest}
      />

      {hint ? <p className="text-sm text-[var(--text-dim)]">{hint}</p> : null}
    </label>
  );
}
