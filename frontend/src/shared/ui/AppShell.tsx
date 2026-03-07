import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/shared/store/authStore';
import { cn } from '@/shared/lib/cn';
import type { PropsWithChildren } from 'react';

type NavItem = {
  label: string;
  href: string;
};

type AppShellProps = PropsWithChildren<{
  eyebrow: string;
  title: string;
  modeLabel: string;
  navItems: NavItem[];
}>;

export function AppShell({ children, eyebrow, title, modeLabel, navItems }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="page-shell px-4 py-4 text-[var(--text-ivory)] md:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col rounded-[32px] border border-[var(--line)] bg-[rgba(8,8,10,0.55)] p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_24px_90px_rgba(0,0,0,0.45)] backdrop-blur-xl md:p-6">
        <header className="grid gap-4 rounded-[26px] border border-[var(--line)] bg-[rgba(255,248,229,0.04)] px-5 py-4 md:px-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="min-w-0">
            <p className="break-words text-xs uppercase tracking-[0.32em] text-[var(--text-dim)]">{eyebrow}</p>
            <h1 className="mt-2 break-words font-[var(--font-title)] text-2xl tracking-[0.08em] text-[var(--text-ivory)] md:text-3xl">
              {title}
            </h1>
          </div>

          <div className="flex min-w-0 flex-col gap-3 xl:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-[rgba(245,179,111,0.16)] px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-[var(--ember-soft)]">
                {modeLabel}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <nav className="flex flex-wrap items-center gap-2 rounded-[20px] border border-[var(--line)] bg-[rgba(255,255,255,0.03)] p-1.5">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className={cn(
                      'rounded-full px-4 py-2 text-sm font-semibold transition',
                      location.pathname.startsWith(item.href)
                        ? 'bg-[linear-gradient(135deg,rgba(239,126,69,0.26),rgba(245,179,111,0.14))] text-[var(--text-ivory)]'
                        : 'text-[var(--text-dim)] hover:text-[var(--text-ivory)]',
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>

              <button
                type="button"
                onClick={() => {
                  logout();
                  navigate('/login');
                }}
                className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--text-mist)] transition hover:border-[var(--line-strong)] hover:text-[var(--text-ivory)]"
              >
                Sign Out
              </button>
            </div>
          </div>
        </header>

        <main className="mt-4 flex-1 min-w-0">{children}</main>
      </div>
    </div>
  );
}
