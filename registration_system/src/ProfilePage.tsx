import {startTransition, useEffect, useState} from 'react';
import type {ProfileData, ProfileResponse} from './types';
import {API_BASE} from './api';

type Props = {
  userId: number;
  onBack: () => void;
};

function fmt(v: number) {
  return new Intl.NumberFormat('ru-RU').format(v);
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function initials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() || '?';
}

function roleLabel(p: ProfileData): string {
  if (p.isOwner) return 'Owner';
  if (p.isAdmin) return 'Admin';
  if (p.isLeft) return 'Покинул чат';
  return 'Участник';
}

function roleBadge(p: ProfileData): string {
  if (p.isOwner) return 'bg-amber-300/20 text-amber-100';
  if (p.isAdmin) return 'bg-indigo-300/20 text-indigo-100';
  if (p.isLeft) return 'bg-rose-300/20 text-rose-100';
  return 'bg-emerald-300/20 text-emerald-100';
}

export default function ProfilePage({userId, onBack}: Props) {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/mini-app/profile/${userId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<ProfileResponse>;
      })
      .then((payload) => {
        startTransition(() => {
          if (payload.ok && payload.profile) {
            setProfile(payload.profile);
          } else {
            setError(payload.error ?? 'Профиль не найден');
          }
          setLoading(false);
        });
      })
      .catch((e: Error) => {
        startTransition(() => {
          setError(e.message);
          setLoading(false);
        });
      });
  }, [userId]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#22324b_0%,_#101826_45%,_#090d14_100%)] px-4 py-6 text-stone-100">
      <div className="mx-auto flex w-full max-w-md flex-col gap-4">

        {/* Back header */}
        <header className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/8 text-stone-300 transition-colors hover:bg-white/12 active:scale-90"
            aria-label="Назад"
          >
            ←
          </button>
          <h1 className="text-xl font-semibold text-white">Профиль</h1>
        </header>

        {loading && (
          <section className="rounded-[24px] border border-cyan-300/20 bg-cyan-400/10 p-5 text-sm text-cyan-50">
            Загружаю профиль…
          </section>
        )}
        {error && (
          <section className="rounded-[24px] border border-rose-300/20 bg-rose-400/10 p-5 text-sm text-rose-50">
            {error}
          </section>
        )}

        {profile && (
          <>
            {/* Avatar + name */}
            <section className="rounded-[28px] border border-white/10 bg-[#111927]/90 p-6">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400/30 to-indigo-500/40 text-2xl font-semibold text-white shadow-[0_0_24px_rgba(56,189,248,0.15)] ring-2 ring-white/10">
                  {initials(profile.displayName)}
                </div>
                <div className="min-w-0">
                  <h2 className="text-2xl font-semibold text-white">{profile.displayName}</h2>
                  <p className="mt-1 text-sm text-stone-400">
                    {profile.username ? `@${profile.username}` : `ID: ${profile.userId}`}
                  </p>
                  <span className={`mt-2 inline-block rounded-full px-3 py-0.5 text-xs font-medium ${roleBadge(profile)}`}>
                    {roleLabel(profile)}
                  </span>
                </div>
              </div>
            </section>

            {/* Balance */}
            <section className="grid grid-cols-2 gap-3">
              <div className="rounded-[22px] border border-emerald-400/20 bg-emerald-400/8 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-emerald-200/70">Баланс</p>
                <p className="mt-2 text-2xl font-semibold text-emerald-100">{fmt(profile.balance)}</p>
                <p className="mt-1 text-xs text-stone-400">💎 Pulse</p>
              </div>
              <div className="rounded-[22px] border border-indigo-400/20 bg-indigo-400/8 p-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-indigo-200/70">Заморожено</p>
                <p className="mt-2 text-2xl font-semibold text-indigo-100">{fmt(profile.frozenBalance)}</p>
                <p className="mt-1 text-xs text-stone-400">💎 Pulse</p>
              </div>
            </section>

            {/* Activity stats */}
            <section className="rounded-[28px] border border-white/10 bg-white/8 p-5">
              <p className="text-xs uppercase tracking-[0.28em] text-stone-400">Активность</p>
              <div className="mt-3 grid grid-cols-3 gap-3">
                <div className="rounded-[18px] bg-black/20 p-3 text-center">
                  <div className="text-xl font-semibold text-white">{fmt(profile.stats.totalMessages)}</div>
                  <div className="mt-1 text-[11px] text-stone-400">сообщений</div>
                </div>
                <div className="rounded-[18px] bg-black/20 p-3 text-center">
                  <div className="text-xl font-semibold text-white">{fmt(profile.stats.reactionsGiven)}</div>
                  <div className="mt-1 text-[11px] text-stone-400">реакций</div>
                </div>
                <div className="rounded-[18px] bg-black/20 p-3 text-center">
                  <div className="text-xl font-semibold text-white">{fmt(profile.referralCount)}</div>
                  <div className="mt-1 text-[11px] text-stone-400">рефералов</div>
                </div>
              </div>
            </section>

            {/* Dates */}
            <section className="rounded-[28px] border border-white/10 bg-white/8 p-5">
              <p className="text-xs uppercase tracking-[0.28em] text-stone-400">Даты</p>
              <div className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-stone-400">В чате с</span>
                  <span className="text-stone-100">{fmtDate(profile.joinedAt)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-stone-400">Последняя активность</span>
                  <span className="text-stone-100">{fmtDate(profile.lastActive)}</span>
                </div>
              </div>
            </section>

            {/* BBS + referral */}
            <section className="grid grid-cols-2 gap-3">
              <div
                className={`rounded-[22px] border p-4 ${
                  profile.hasBbsProfile
                    ? 'border-rose-400/20 bg-rose-400/8'
                    : 'border-white/10 bg-black/20'
                }`}
              >
                <p className="text-[11px] uppercase tracking-[0.18em] text-stone-400">BBS</p>
                <p className="mt-2 text-sm font-medium text-white">
                  {profile.hasBbsProfile ? '💌 Анкета есть' : 'Нет анкеты'}
                </p>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-black/20 p-4">
                <p className="text-[11px] uppercase tracking-[0.18em] text-stone-400">Реф. код</p>
                <p className="mt-2 break-all font-mono text-xs text-cyan-200">
                  {profile.referralCode ?? '—'}
                </p>
              </div>
            </section>

          </>
        )}

      </div>
    </main>
  );
}
