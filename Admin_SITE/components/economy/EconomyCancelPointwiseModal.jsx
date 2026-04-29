import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, AlertTriangle } from 'lucide-react';

const MODES = [
  {
    key: 'deduct',
    label: 'Списать с баланса',
    desc: 'Если хватает 💎 у юзера — спишем сумму, банк +amount.',
    cls:  'bg-red-50 border-red-200 text-red-700',
  },
  {
    key: 'debt',
    label: 'Уйти в долг',
    desc: 'Списать даже в минус (баланс может стать отрицательным).',
    cls:  'bg-orange-50 border-orange-200 text-orange-700',
  },
  {
    key: 'log_only',
    label: 'Только лог',
    desc: 'Балансы не трогаем, оставляем след в истории отмен.',
    cls:  'bg-gray-50 border-gray-200 text-gray-700',
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
        <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md pointer-events-auto
                        animate-in zoom-in-95 fade-in duration-200">
          {/* Шапка */}
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <div>
              <div className="text-[10px] font-black text-red-500 uppercase tracking-widest">Опасно</div>
              <h2 className="text-base font-black text-gray-900">Точечная отмена выплаты</h2>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-xl transition active:scale-90">
              <X size={20} />
            </button>
          </div>

          {/* Тело */}
          <div className="p-5 space-y-4">
            {/* tx_id */}
            <label className="block">
              <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">ID транзакции</span>
              <input
                type="text"
                inputMode="numeric"
                value={txId}
                onChange={e => setTxId(e.target.value.replace(/\D/g, ''))}
                placeholder="например 12345"
                className="mt-1 w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl
                           text-sm font-bold focus:outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>

            {/* mode */}
            <div>
              <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Режим</span>
              <div className="mt-1 space-y-2">
                {MODES.map(m => (
                  <button
                    key={m.key}
                    onClick={() => setMode(m.key)}
                    className={`w-full text-left p-3 rounded-2xl border-2 transition active:scale-[0.99]
                                ${mode === m.key ? m.cls + ' ring-2 ring-offset-1 ring-blue-300' : 'bg-white border-gray-200 text-gray-700'}`}>
                    <div className="text-xs font-black">{m.label}</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">{m.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* comment */}
            <label className="block">
              <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">
                Комментарий (обязательно, ≥ 3 символа)
              </span>
              <textarea
                value={comment}
                onChange={e => setComm(e.target.value)}
                rows={2}
                placeholder="за что отменяем?"
                className="mt-1 w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl
                           text-sm font-bold resize-none focus:outline-none focus:border-blue-400 focus:bg-white"
              />
            </label>

            {/* warn */}
            <div className="flex gap-2 p-3 bg-amber-50 border border-amber-200 rounded-2xl">
              <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
              <div className="text-[11px] text-amber-800 font-bold leading-tight">
                Действие необратимо. История сохранится в журнале отмен.
              </div>
            </div>

            {err && (
              <div className="text-xs font-bold text-red-600 px-3 py-2 bg-red-50 border border-red-200 rounded-xl">
                ⚠️ {err}
              </div>
            )}
          </div>

          {/* Кнопки */}
          <div className="flex gap-2 p-5 border-t border-gray-100">
            <button
              onClick={onClose}
              disabled={busy}
              className="flex-1 py-3 bg-gray-100 text-gray-700 rounded-2xl text-xs font-black uppercase
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
