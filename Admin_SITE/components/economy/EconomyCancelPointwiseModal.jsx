// EconomyCancelPointwiseModal — модалка точечной отмены по ID транзакции.

import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, AlertTriangle } from 'lucide-react';

const MODES = [
  {
    key: 'deduct',
    label: 'Списать с баланса',
    desc: 'Если хватает 💎 у юзера — спишем сумму, банк +amount.',
    cls:  'bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border-[color-mix(in_oklab,var(--danger)_40%,transparent)] text-danger',
  },
  {
    key: 'debt',
    label: 'Уйти в долг',
    desc: 'Списать даже в минус (баланс может стать отрицательным).',
    cls:  'bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border-[color-mix(in_oklab,var(--warn)_40%,transparent)] text-warn',
  },
  {
    key: 'log_only',
    label: 'Только лог',
    desc: 'Балансы не трогаем, оставляем след в истории отмен.',
    cls:  'bg-sf2 border-bd2 text-tx',
  },
];

export default function EconomyCancelPointwiseModal({ token, onClose, onDone }) {
  const [txId, setTxId]     = useState('');
  const [mode, setMode]     = useState('deduct');
  const [comment, setComm]  = useState('');
  const [busy, setBusy]     = useState(false);
  const [err, setErr]       = useState(null);

  const valid = /^\d+$/.test(txId.trim()) && comment.trim().length >= 3;

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch('/api/economy/cancellations/pointwise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          tx_id:   parseInt(txId.trim(), 10),
          mode,
          comment: comment.trim(),
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
                        animate-in zoom-in-95 fade-in duration-200">
          {/* Шапка */}
          <div className="flex items-center justify-between p-5 border-b border-bd">
            <div>
              <div className="text-[10px] font-black text-danger uppercase tracking-widest">Опасно</div>
              <h2 className="text-base font-black text-tx">Точечная отмена выплаты</h2>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-sf2 rounded-xl transition active:scale-90">
              <X size={20} />
            </button>
          </div>

          {/* Тело */}
          <div className="p-5 space-y-4">
            {/* tx_id */}
            <label className="block">
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">ID транзакции</span>
              <input
                type="text"
                inputMode="numeric"
                value={txId}
                onChange={e => setTxId(e.target.value.replace(/\D/g, ''))}
                placeholder="например 12345"
                className="mt-1 w-full px-4 py-3 bg-sf2 border border-bd2 rounded-2xl
                           text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-sff"
              />
            </label>

            {/* mode */}
            <div>
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">Режим</span>
              <div className="mt-1 space-y-2">
                {MODES.map(m => (
                  <button
                    key={m.key}
                    onClick={() => setMode(m.key)}
                    className={`w-full text-left p-3 rounded-2xl border-2 transition active:scale-[0.99]
                                ${mode === m.key ? m.cls + ' ring-2 ring-offset-1 ring-blue-300' : 'bg-sff border-bd2 text-tx'}`}>
                    <div className="text-xs font-black">{m.label}</div>
                    <div className="text-[10px] text-txd mt-0.5">{m.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* comment */}
            <label className="block">
              <span className="text-[10px] font-black text-txd uppercase tracking-widest">
                Комментарий (обязательно, ≥ 3 символа)
              </span>
              <textarea
                value={comment}
                onChange={e => setComm(e.target.value)}
                rows={2}
                placeholder="за что отменяем?"
                className="mt-1 w-full px-4 py-3 bg-sf2 border border-bd2 rounded-2xl
                           text-sm font-bold resize-none focus:outline-none focus:border-blue-400 focus:bg-sff"
              />
            </label>

            {/* warn */}
            <div className="flex gap-2 p-3 bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border border-[color-mix(in_oklab,var(--warn)_40%,transparent)] rounded-2xl">
              <AlertTriangle size={16} className="text-warn shrink-0 mt-0.5" />
              <div className="text-[11px] text-warn font-bold leading-tight">
                Действие необратимо. История сохранится в журнале отмен.
              </div>
            </div>

            {err && (
              <div className="text-xs font-bold text-danger px-3 py-2 bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border border-[color-mix(in_oklab,var(--danger)_40%,transparent)] rounded-xl">
                ⚠️ {err}
              </div>
            )}
          </div>

          {/* Кнопки */}
          <div className="flex gap-2 p-5 border-t border-bd">
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
              className="flex-1 py-3 bg-red-600 text-white rounded-2xl text-xs font-black uppercase
                         tracking-widest active:scale-95 transition disabled:opacity-50 disabled:cursor-not-allowed">
              {busy ? '…' : '🚫 Отменить'}
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}
