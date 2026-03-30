import type {BootstrapResponse} from './types';

type Props = {
  loading: boolean;
  error: string | null;
  data: BootstrapResponse | null;
  onGoProfile: () => void;
  onGoBbs: () => void;
};

function fmt(v: number) {
  return new Intl.NumberFormat('ru-RU').format(v);
}

const SECTION_ICONS: Record<string, string> = {
  profile: '👤',
  bbs: '💬',
  economy: '💎',
};

export default function HomePage({loading, error, data, onGoProfile, onGoBbs}: Props) {
  const platform = window.Telegram?.WebApp?.platform ?? 'browser';
  const version = window.Telegram?.WebApp?.version ?? 'dev';

  function handleSectionClick(id: string) {
    if (id === 'profile') onGoProfile();
    else if (id === 'bbs') onGoBbs();
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#22324b_0%,_#101826_45%,_#090d14_100%)] px-4 py-6 text-stone-100">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-md flex-col gap-4">

        {/* Hero */}
        <section className="overflow-hidden rounded-[28px] border border-white/10 bg-white/8 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] backdrop-blur">
          <p className="text-[11px] uppercase tracking-[0.35em] text-amber-200/80">Pulse Mini App</p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight text-stone-50">
            Профиль, BBS<br />и экономика.
          </h1>
          <div className="mt-5 flex flex-wrap gap-2 text-xs text-stone-200/80">
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
              mode: {data?.launchMode ?? '…'}
            </span>
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
              platform: {platform}
            </span>
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1">
              v{version}
            </span>
          </div>
        </section>

        {/* Loading / Error */}
        {loading && (
          <section className="rounded-[24px] border border-cyan-300/20 bg-cyan-400/10 p-5 text-sm text-cyan-50">
            Загружаю данные…
          </section>
        )}
        {error && (
          <section className="rounded-[24px] border border-rose-300/20 bg-rose-400/10 p-5 text-sm text-rose-50">
            Ошибка: {error}
          </section>
        )}

        {data && (
          <>
            {/* Compact user card */}
            <section className="rounded-[28px] border border-white/10 bg-[#111927]/90 p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400/30 to-indigo-500/30 text-lg font-semibold text-white ring-1 ring-white/10">
                    {data.user.displayName.slice(0, 1).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-base font-semibold text-white">{data.user.displayName}</div>
                    <div className="text-xs text-stone-400">
                      {data.user.isOwner ? 'owner' : data.user.isAdmin ? 'admin' : 'member'}
                      {' · '}{fmt(data.user.balance)} 💎
                    </div>
                  </div>
                </div>
                {data.user.isLinked && (
                  <button
                    onClick={onGoProfile}
                    className="rounded-2xl bg-cyan-400/15 px-4 py-2 text-sm font-medium text-cyan-200 transition-colors hover:bg-cyan-400/25 active:scale-95"
                  >
                    Профиль →
                  </button>
                )}
              </div>
            </section>

            {/* Feature navigation */}
            <section className="rounded-[28px] border border-white/10 bg-white/8 p-5">
              <p className="text-xs uppercase tracking-[0.28em] text-amber-200/70">Навигация</p>
              <div className="mt-3 space-y-3">
                {data.sections.map((s) => (
                  <button
                    key={s.id}
                    onClick={s.state === 'ready' ? () => handleSectionClick(s.id) : undefined}
                    disabled={s.state !== 'ready'}
                    className={`w-full rounded-[22px] border p-4 text-left transition-all ${
                      s.state === 'ready'
                        ? 'cursor-pointer border-cyan-300/20 bg-cyan-400/10 hover:bg-cyan-400/15 active:scale-[0.98]'
                        : 'cursor-default border-white/10 bg-black/20 opacity-70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 text-2xl">{SECTION_ICONS[s.id] ?? '•'}</span>
                        <div>
                          <div className="text-base font-semibold text-stone-100">{s.title}</div>
                          <div className="mt-1 text-sm leading-6 text-stone-400">{s.description}</div>
                        </div>
                      </div>
                      <span
                        className={`mt-1 shrink-0 rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
                          s.state === 'ready'
                            ? 'bg-emerald-300/15 text-emerald-100'
                            : 'bg-amber-300/15 text-amber-100'
                        }`}
                      >
                        {s.state === 'ready' ? 'ready' : 'next'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </>
        )}

      </div>
    </main>
  );
}