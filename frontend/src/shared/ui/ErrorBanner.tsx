import { ApiClientError } from '@/shared/api/client';

type ErrorBannerProps = {
  error: unknown;
};

export function ErrorBanner({ error }: ErrorBannerProps) {
  if (!error) {
    return null;
  }

  if (error instanceof ApiClientError) {
    return (
      <div className="rounded-[24px] border border-[rgba(239,126,69,0.28)] bg-[rgba(239,126,69,0.1)] px-4 py-3 text-sm text-[#ffcfb7]">
        <div className="font-bold uppercase tracking-[0.14em]">{error.code}</div>
        <div className="mt-1">{error.message}</div>
        {error.requestId ? <div className="mt-1 text-xs text-[#f2b494]">Request ID: {error.requestId}</div> : null}
      </div>
    );
  }

  return (
    <div className="rounded-[24px] border border-[rgba(239,126,69,0.28)] bg-[rgba(239,126,69,0.1)] px-4 py-3 text-sm text-[#ffcfb7]">
      {error instanceof Error ? error.message : 'Unexpected error'}
    </div>
  );
}
