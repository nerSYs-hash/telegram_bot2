import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, AlertTriangle } from 'lucide-react';

const CATEGORIES = [
  { key: 'mining',       label: '💰 Майнинг' },
  { key: 'lottery',      label: '🎰 Лотерея' },
  { key: 'bingo',        label: '🎱 Бинго' },
  { key: 'monthly_gift', label: '🎁 Подарок месяца' },
  { key: 'referral',     label: '👥 Рефералы' },
  { key: 'bbs_bonus',    label: '❤️ BBS-бонусы' },
  { key: 'donate',       label: '🎁 Донаты' },
];

function todayISO(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export default function EconomyCancelMassModal({ token, onClose, onDone }) {
  const [category, setCategory] = useState(CATEGORIES[0].key);
  const [dateFrom, setDateFrom] = useState(todayISO(-7));
  const [dateTo,   setDateTo]   = useState(todayISO(0));
  const [userIds,  setUserIds]  = useState('');
  const [comment,  setComment]  = useState('');
  const [busy,     setBusy]     = useState(false);
  const [err,      setErr]      = useState(null);

  const valid = category && dateFrom && dateTo && comment.trim().length >= 3;

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);

    const ids = userIds.split(',')
      .map(s => s.trim())
      .filter(Boolean)
      .map(s => parseInt(s, 10))
      .filter(n => Number.isFinite(n));

    try {
      const res = await fetch('/api/economy/cancellations/mass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          category,
          date_from: dateFrom,
          date_to:   dateTo,
          user_ids:  ids.length ? ids : null,
          comment:   comment.trim(),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      onDone?.(data);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/40 z-[60]" />
      <div className="fixed inset-0 z-[61] flex items-center justify-center p-4 pointer-events-none">
        <div className="bg-sff rounded-3xl shadow-2xl w-full max-w-md pointer-events-auto
                        animate-in zoom-in-95 fade-in duration-200 max-h-[90vh] flex flex-col">
          {/* Шапка */}
          <div className="shrink-0 flex items-center justify-between p-5 border-b border-bd">
            <div>
              <div className="text-[10px] font-black text-orange-500 uppercase tracking-widest">Только лог</div>
              <h2 className="text-base font-black text-tx">Массовая отмена выплат</h2>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-sf2 rounded-xl transition active:scale-90">
              <X size={20} />
            </button>
          </div>

          {/* Тело */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {/* Раздел */}
            <label className="block">
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">Раздел</span>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="mt-1 w-full px-4 py-3 bg-sf2 border border-bd2 rounded-2xl
                           text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-sff">
                {CATEGORIES.map(c => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            </label>

            {/* Период */}
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-[10px] font-black text-txd uppercase tracking-widest">С даты</span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={e => setDateFrom(e.target.value)}
                  className="mt-1 w-full px-3 py-3 bg-sf2 border border-bd2 rounded-2xl
                             text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-sff"
                />
              </label>
              <label className="block">
                <span className="text-[10px] font-black text-txd uppercase tracking-widest">По дату</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={e => setDateTo(e.target.value)}
                  className="mt-1 w-full px-3 py-3 bg-sf2 border border-bd2 rounded-2xl
                             text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-sff"
                />
              </label>
            </div>

            {/* user_ids (опц.) */}
            <label className="block">
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">
                User ID через запятую (опционально)
              </span>
              <input
                type="text"
                value={userIds}
                onChange={e => setUserIds(e.target.value)}
                placeholder="например 12345, 67890"
                className="mt-1 w-full px-4 py-3 bg-sf2 border border-bd2 rounded-2xl
                           text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-sff"
              />
              <span className="text-[10px] text-lbl mt-1 block">
                Пусто — все юзеры за период
              </span>
            </label>

            {/* Комментарий */}
            <label className="block">
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">
                Комментарий (обязательно, ≥ 3 символа)
              </span>
              <textarea
                value={comment}
                onChange={e => setComment(e.target.value)}
                rows={2}
                placeholder="причина отмены"
                className="mt-1 w-full px-4 py-3 bg-sf2 border border-bd2 rounded-2xl
                           text-sm font-bold resize-none focus:outline-none focus:border-blue-400 focus:bg-sff"
              />
            </label>

            {/* Warn */}
            <div className="flex gap-2 p-3 bg-amber-50 border border-amber-200 rounded-2xl">
              <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
              <div className="text-[11px] text-amber-800 font-bold leading-tight">
                Массовая отмена работает только в режиме <span className="text-amber-900">log_only</span> —
                балансы не трогаем, но фиксируем затронутую сумму и юзеров в журнале.
              </div>
            </div>

            {err && (
              <div className="text-xs font-bold text-red-600 px-3 py-2 bg-red-50 border border-red-200 rounded-xl">
                ⚠️ {err}
              </div>
            )}
          </div>

          {/* Кнопки */}
          <div className="shrink-0 flex gap-2 p-5 border-t border-bd">
            <button
              onClick={onClose}
              disabled={busy}
              className="flex-1 py-3 bg-sf2 text-tx rounded-2xl text-xs font-black uppercase
                         tracking-widest active:scale-95 transition disabled:opacity-50">
              Отмена
            </button>
            <button
              onClick={submit}
              disabled={!valid || busy}
              className="flex-1 py-3 bg-orange-600 text-white rounded-2xl text-xs font-black uppercase
                         tracking-widest active:scale-95 transition disabled:opacity-50 disabled:cursor-not-allowed">
              {busy ? '…' : '📜 Зафиксировать'}
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}
