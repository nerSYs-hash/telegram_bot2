import {startTransition, useEffect, useState} from 'react';
import type {BbsProfile, BbsResponse, BbsActionResponse} from './types';
import {API_BASE} from './api';

type Props = {
  userId: number;
  onBack: () => void;
};

function safeJson(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('ru-RU', {day: 'numeric', month: 'short', year: 'numeric'}).format(new Date(iso));
  } catch {
    return iso;
  }
}

type ViewState = 'loading' | 'no-profile' | 'profile' | 'error' | 'deleting' | 'deleted';

export default function BbsPage({userId, onBack}: Props) {
  const [view, setView] = useState<ViewState>('loading');
  const [profile, setProfile] = useState<BbsProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/mini-app/bbs/${userId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<BbsResponse>;
      })
      .then((payload) => {
        startTransition(() => {
          if (!payload.ok) {
            setError(payload.error ?? 'Ошибка загрузки');
            setView('error');
          } else if (!payload.hasProfile || !payload.profile) {
            setView('no-profile');
          } else {
            setProfile(payload.profile);
            setView('profile');
          }
        });
      })
      .catch((e: Error) => startTransition(() => { setError(e.message); setView('error'); }));
  }, [userId]);

  async function handleDelete() {
    setView('deleting');
    setConfirmDelete(false);
    try {
      const res = await fetch(`${API_BASE}/api/mini-app/bbs/${userId}`, {method: 'DELETE'});
      const payload = await res.json() as BbsActionResponse;
      startTransition(() => {
        if (payload.ok) {
          setView('deleted');
          setProfile(null);
        } else {
          setError(payload.error ?? 'Не удалось удалить');
          setView('profile');
        }
      });
    } catch (e) {
      startTransition(() => {
        setError((e as Error).message);
        setView('profile');
      });
    }
  }

  const city = safeJson(profile ? JSON.stringify(profile.city) : null);
  const roles = safeJson(profile ? JSON.stringify(profile.roles) : null);
  const goals = safeJson(profile ? JSON.stringify(profile.goals) : null);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#22324b_0%,_#101826_45%,_#090d14_100%)] px-4 py-6 text-stone-100">
      <div className="mx-auto flex w-full max-w-md flex-col gap-4">

        {/* Header */}
        <header className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/8 text-stone-300 transition-colors hover:bg-white/12 active:scale-90"
            aria-label="Назад"
          >
            ←
          </button>
          <h1 className="text-xl font-semibold text-white">BBS — анкета</h1>
        </header>

        {/* States */}
        {view === 'loading' && (
          <section className="rounded-[24px] border border-cyan-300/20 bg-cyan-400/10 p-5 text-sm text-cyan-50">
            Загружаю анкету…
          </section>
        )}

        {view === 'error' && (
          <section className="rounded-[24px] border border-rose-300/20 bg-rose-400/10 p-5 text-sm text-rose-50">
            {error}
          </section>
        )}

        {view === 'deleting' && (
          <section className="rounded-[24px] border border-amber-300/20 bg-amber-400/10 p-5 text-sm text-amber-50">
            Удаляю анкету…
          </section>
        )}

        {view === 'deleted' && (
          <section className="rounded-[24px] border border-emerald-300/20 bg-emerald-400/10 p-5">
            <p className="text-sm font-semibold text-emerald-100">Анкета удалена</p>
            <p className="mt-1 text-xs text-emerald-200/70">Ты можешь создать новую через бота командой /bbs</p>
          </section>
        )}

        {/* No profile */}
        {view === 'no-profile' && (
          <section className="rounded-[28px] border border-white/10 bg-[#111927]/90 p-6 text-center">
            <div className="text-4xl">💬</div>
            <h2 className="mt-3 text-xl font-semibold text-white">Анкеты нет</h2>
            <p className="mt-2 text-sm text-stone-400 leading-6">
              Создай анкету через бота командой <span className="font-mono text-cyan-300">/bbs</span>,
              затем вернись сюда — она появится здесь.
            </p>
          </section>
        )}

        {/* Profile card */}
        {view === 'profile' && profile && (
          <>
            {/* Status badge */}
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${profile.isPublished ? 'bg-emerald-300/15 text-emerald-100' : 'bg-amber-300/15 text-amber-100'}`}>
                {profile.isPublished ? '✅ Опубликована' : '⏳ Не опубликована'}
              </span>
              {profile.reactionCount > 0 && (
                <span className="rounded-full bg-rose-400/15 px-3 py-1 text-xs text-rose-200">
                  ❤️ {profile.reactionCount}
                </span>
              )}
            </div>

            {/* Main info */}
            <section className="rounded-[28px] border border-white/10 bg-[#111927]/90 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-semibold text-white">{profile.name}</h2>
                  <p className="mt-1 text-sm text-stone-400">{profile.age} лет</p>
                  {city.length > 0 && (
                    <p className="mt-1 text-sm text-stone-300">📍 {city.join(', ')}</p>
                  )}
                </div>
                {profile.username && (
                  <span className="mt-1 text-xs text-stone-400">@{profile.username}</span>
                )}
              </div>

              {profile.about && (
                <div className="mt-4 rounded-[18px] bg-white/4 p-3">
                  <p className="text-xs uppercase tracking-widest text-stone-500">О себе</p>
                  <p className="mt-2 text-sm leading-6 text-stone-200 whitespace-pre-wrap">{profile.about}</p>
                </div>
              )}
            </section>

            {/* Tags */}
            {(roles.length > 0 || goals.length > 0) && (
              <section className="rounded-[28px] border border-white/10 bg-white/8 p-5">
                {roles.length > 0 && (
                  <div>
                    <p className="text-xs uppercase tracking-[0.28em] text-stone-400">Роль</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {roles.map((r) => (
                        <span key={r} className="rounded-full border border-indigo-300/20 bg-indigo-400/10 px-3 py-1 text-xs text-indigo-200">{r}</span>
                      ))}
                    </div>
                  </div>
                )}
                {goals.length > 0 && (
                  <div className={roles.length > 0 ? 'mt-4' : ''}>
                    <p className="text-xs uppercase tracking-[0.28em] text-stone-400">Цели</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {goals.map((g) => (
                        <span key={g} className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-200">{g}</span>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Dates */}
            <section className="rounded-[28px] border border-white/10 bg-white/8 p-5">
              <p className="text-xs uppercase tracking-[0.28em] text-stone-400">Даты</p>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-stone-400">Создана</span>
                  <span className="text-stone-100">{fmtDate(profile.createdAt)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-stone-400">Опубликована</span>
                  <span className="text-stone-100">{fmtDate(profile.publishedAt)}</span>
                </div>
              </div>
            </section>

            {/* Delete */}
            <section className="rounded-[28px] border border-rose-400/20 bg-rose-400/8 p-5">
              <p className="text-sm font-medium text-rose-100">Удалить анкету</p>
              <p className="mt-1 text-xs text-rose-200/70">
                Анкета будет удалена из базы данных и из чата. Это действие необратимо.
              </p>
              {!confirmDelete ? (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="mt-4 w-full rounded-[18px] border border-rose-400/30 bg-rose-500/15 py-2.5 text-sm font-medium text-rose-200 transition-colors hover:bg-rose-500/25 active:scale-[0.98]"
                >
                  🗑 Удалить анкету
                </button>
              ) : (
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="flex-1 rounded-[18px] border border-white/10 bg-white/8 py-2.5 text-sm text-stone-300 hover:bg-white/12"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleDelete}
                    className="flex-1 rounded-[18px] bg-rose-500/80 py-2.5 text-sm font-semibold text-white hover:bg-rose-500 active:scale-[0.98]"
                  >
                    Да, удалить
                  </button>
                </div>
              )}
            </section>
          </>
        )}

      </div>
    </main>
  );
}
