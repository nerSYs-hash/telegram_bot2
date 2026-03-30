import {useEffect, useState} from 'react';
import {API_BASE} from './api';
import type {EconomyData, Transaction} from './types';

type Props = {
  userId: number;
  onBack: () => void;
};

const TYPE_LABELS: Record<string, string> = {
  message_reward: 'Награда за сообщение',
  referral_reward: 'Реферальная награда',
  transfer: 'Перевод',
  admin_transfer: 'Перевод (admin)',
  lottery_prize: 'Лотерея',
  shop_purchase: 'Покупка в магазине',
  shop_refund: 'Возврат из магазина',
  bonus: 'Бонус',
  daily_bonus: 'Ежедневный бонус',
  donation: 'Донат',
  admin_grant: 'Начисление',
  admin_deduct: 'Списание',
  bbs_bonus: 'BBS бонус',
  freeze: 'Заморозка',
  unfreeze: 'Разморозка',
};

function typeLabel(type: string) {
  return TYPE_LABELS[type] ?? type.replace(/_/g, ' ');
}

function fmt(v: number) {
  return new Intl.NumberFormat('ru-RU').format(v);
}

function fmtTs(ts: string | null) {
  if (!ts) return '—';
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(ts.replace(' ', 'T') + 'Z'));
  } catch {
    return ts;
  }
}

async function fetchEconomy(userId: number): Promise<EconomyData> {
  const res = await fetch(`${API_BASE}/api/mini-app/economy/${userId}?limit=50`);
  if (!res.ok) throw new Error(`Economy ${res.status}`);
  const body = await res.json();
  if (!body.ok) throw new Error(body.error ?? 'unknown error');
  return body.economy as EconomyData;
}

type TxnRowProps = {txn: Transaction; userId: number};
function TxnRow({txn, userId}: TxnRowProps) {
  const isIn = txn.direction === 'in';
  return (
    <div className="flex items-start gap-3 rounded-[18px] border border-white/8 bg-black/20 px-4 py-3">
      <div
        className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-base ${
          isIn
            ? 'bg-emerald-400/15 text-emerald-300'
            : 'bg-rose-400/15 text-rose-300'
        }`}
      >
        {isIn ? '↓' : '↑'}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium text-stone-200">
            {typeLabel(txn.type)}
          </span>
          <span
            className={`shrink-0 text-sm font-semibold tabular-nums ${
              isIn ? 'text-emerald-300' : 'text-rose-300'
            }`}
          >
            {isIn ? '+' : '−'}{fmt(txn.amount)} 💎
          </span>
        </div>
        {txn.description && (
          <p className="mt-0.5 truncate text-xs text-stone-500">{txn.description}</p>
        )}
        <p className="mt-1 text-[11px] text-stone-600">{fmtTs(txn.timestamp)}</p>
      </div>
    </div>
  );
}

export default function EconomyPage({userId, onBack}: Props) {
  const [data, setData] = useState<EconomyData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEconomy(userId)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });
  }, [userId]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#22324b_0%,_#101826_45%,_#090d14_100%)] px-4 py-6 text-stone-100">
      <div className="mx-auto flex w-full max-w-md flex-col gap-4">

        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-white/8 text-stone-300 transition-colors hover:bg-white/15 active:scale-95"
          >
            ←
          </button>
          <h2 className="text-xl font-semibold text-stone-100">Экономика</h2>
        </div>

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
            {/* Balance hero */}
            <section className="overflow-hidden rounded-[28px] border border-white/10 bg-white/8 p-6 shadow-[0_24px_80px_rgba(0,0,0,0.28)] backdrop-blur">
              <p className="text-xs uppercase tracking-[0.28em] text-amber-200/70">Баланс</p>
              <div className="mt-2 flex items-end gap-2">
                <span className="text-5xl font-bold tabular-nums leading-none text-white">
                  {fmt(data.balance)}
                </span>
                <span className="mb-1 text-2xl">💎</span>
              </div>
              {data.frozenBalance > 0 && (
                <p className="mt-2 text-sm text-stone-400">
                  🔒 заморожено: {fmt(data.frozenBalance)} 💎
                </p>
              )}
            </section>

            {/* Stats row */}
            <div className="grid grid-cols-2 gap-3">
              <section className="rounded-[22px] border border-emerald-300/20 bg-emerald-400/8 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-emerald-200/70">Получено</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-200">
                  +{fmt(Math.round(data.totalReceived))}
                </p>
                <p className="text-xs text-stone-500">💎 всего</p>
              </section>
              <section className="rounded-[22px] border border-rose-300/20 bg-rose-400/8 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-rose-200/70">Потрачено</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-rose-200">
                  −{fmt(Math.round(data.totalSent))}
                </p>
                <p className="text-xs text-stone-500">💎 всего</p>
              </section>
            </div>

            {/* Transaction history */}
            <section className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-xs uppercase tracking-[0.28em] text-amber-200/70">
                История операций
                {data.transactions.length > 0 && (
                  <span className="ml-2 rounded-full bg-white/10 px-2 py-0.5 text-stone-400">
                    {data.transactions.length}
                  </span>
                )}
              </p>

              {data.transactions.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">Операций пока нет.</p>
              ) : (
                <div className="mt-3 space-y-2">
                  {data.transactions.map((txn) => (
                    <TxnRow key={txn.id} txn={txn} userId={userId} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
