import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { X, Ban, FileText } from 'lucide-react';
import EconomyCancelPointwiseModal from './EconomyCancelPointwiseModal';
import EconomyCancelMassModal from './EconomyCancelMassModal';

function fmtDate(s) {
  if (!s) return '';
  try {
    return new Date(s).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return s; }
}

function fmtAmount(v) {
  if (v == null) return '—';
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

const MODE_META = {
  deduct:   { label: 'Списано',   cls: 'bg-red-50 text-red-700 border-red-200' },
  debt:     { label: 'В долг',    cls: 'bg-orange-50 text-orange-700 border-orange-200' },
  log_only: { label: 'Только лог', cls: 'bg-gray-100 text-gray-600 border-gray-200' },
};

const TYPE_META = {
  pointwise: { icon: '🎯', label: 'Точечная' },
  mass:      { icon: '📚', label: 'Массовая' },
};

export default function EconomyCancellationsPanel({ token, onClose, canCancel }) {
  const [items,    setItems]    = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [err,      setErr]      = useState(null);
  const [page,     setPage]     = useState(0);
  const [hasMore,  setHasMore]  = useState(false);
  const [pointOpen, setPointOpen] = useState(false);
  const [massOpen,  setMassOpen]  = useState(false);

  const PER_PAGE = 50;

  const load = useCallback((reset = false) => {
    setLoading(true);
    setErr(null);
    const offset = reset ? 0 : page * PER_PAGE;
    fetch(`/api/economy/cancellations?limit=${PER_PAGE}&offset=${offset}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        const arr = Array.isArray(d) ? d : [];
        setItems(prev => reset ? arr : [...prev, ...arr]);
        setHasMore(arr.length === PER_PAGE);
        setLoading(false);
      })
      .catch(e => { setErr(e.message); setLoading(false); });
  }, [token, page]);

  useEffect(() => { load(page === 0); }, [page, load]);

  const handleDone = () => {
    setPage(0);
    load(true);
  };

  return createPortal(
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/30 z-40" />
      <div className="fixed top-0 right-0 h-full w-full md:w-[480px] bg-white shadow-2xl z-50 flex flex-col overflow-hidden">

        {/* Шапка */}
        <div className="shrink-0 bg-white border-b border-gray-100 p-4 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-black text-red-500 uppercase tracking-widest">Журнал отмен</div>
            <h2 className="text-base font-black text-gray-900 leading-tight">Отмены выплат</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-xl transition active:scale-90">
            <X size={20} />
          </button>
        </div>

        {/* Действия */}
        {canCancel && (
          <div className="shrink-0 grid grid-cols-2 gap-2 p-4 border-b border-gray-100 bg-gray-50">
            <button
              onClick={() => setPointOpen(true)}
              className="flex items-center justify-center gap-2 py-3 bg-red-600 text-white rounded-2xl
                         text-xs font-black uppercase tracking-widest active:scale-95 transition
                         hover:bg-red-700">
              <Ban size={14} /> Точечная
            </button>
            <button
              onClick={() => setMassOpen(true)}
              className="flex items-center justify-center gap-2 py-3 bg-orange-600 text-white rounded-2xl
                         text-xs font-black uppercase tracking-widest active:scale-95 transition
                         hover:bg-orange-700">
              <FileText size={14} /> Массовая
            </button>
          </div>
        )}

        {/* Список */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && items.length === 0 && (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {err && !loading && (
            <div className="text-center py-12">
              <div className="text-3xl mb-3">⚠️</div>
              <div className="text-sm font-black text-gray-500">Не удалось загрузить</div>
              <div className="text-[11px] text-gray-400 mt-1">{err}</div>
              <button
                onClick={() => { setPage(0); load(true); }}
                className="mt-4 px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-black">
                Повторить
              </button>
            </div>
          )}

          {!loading && !err && items.length === 0 && (
            <div className="text-center py-12">
              <div className="text-3xl mb-3">🗂</div>
              <div className="text-sm font-black text-gray-500">Отмен пока не было</div>
            </div>
          )}

          {items.map(it => {
            const tMeta = TYPE_META[it.cancellation_type] || { icon: '•', label: it.cancellation_type };
            const mMeta = MODE_META[it.mode] || { label: it.mode, cls: 'bg-gray-100 text-gray-600 border-gray-200' };
            let filter = null;
            if (it.source_filter) {
              try { filter = typeof it.source_filter === 'string' ? JSON.parse(it.source_filter) : it.source_filter; }
              catch { filter = null; }
            }
            return (
              <div key={it.id} className="bg-white border border-gray-100 rounded-2xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{tMeta.icon}</span>
                    <span className="text-xs font-black text-gray-700">{tMeta.label}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase border ${mMeta.cls}`}>
                      {mMeta.label}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-400 font-bold">{fmtDate(it.executed_at)}</span>
                </div>

                <div className="text-sm font-black text-gray-900">
                  {fmtAmount(it.amount)} 💎
                  {it.actually_deducted > 0 && it.actually_deducted !== it.amount && (
                    <span className="text-[11px] text-gray-500 font-bold ml-2">
                      (списано {fmtAmount(it.actually_deducted)})
                    </span>
                  )}
                </div>

                {it.cancellation_type === 'pointwise' && (
                  <div className="text-[11px] text-gray-500 font-bold mt-1">
                    user_id: {it.target_user_id} · tx_id: {it.source_tx_id}
                  </div>
                )}

                {it.cancellation_type === 'mass' && (
                  <div className="text-[11px] text-gray-500 font-bold mt-1">
                    {filter?.category ? `раздел ${filter.category} · ` : ''}
                    {filter?.date_from} → {filter?.date_to}
                    {it.affected_users != null ? ` · затронуто ${it.affected_users}` : ''}
                  </div>
                )}

                {it.comment && (
                  <div className="text-xs text-gray-600 italic mt-2">💬 {it.comment}</div>
                )}

                <div className="text-[10px] text-gray-400 font-bold mt-1">
                  by {it.executed_by_role || ''} {it.executed_by ? `#${it.executed_by}` : ''}
                </div>
              </div>
            );
          })}

          {hasMore && !loading && (
            <button
              onClick={() => setPage(p => p + 1)}
              className="w-full py-3 text-[11px] font-black text-blue-500 uppercase tracking-widest
                         hover:bg-blue-50 rounded-2xl transition">
              ↓ Загрузить ещё ↓
            </button>
          )}
        </div>
      </div>

      {pointOpen && (
        <EconomyCancelPointwiseModal
          token={token}
          onClose={() => setPointOpen(false)}
          onDone={handleDone}
        />
      )}
      {massOpen && (
        <EconomyCancelMassModal
          token={token}
          onClose={() => setMassOpen(false)}
          onDone={handleDone}
        />
      )}
    </>,
    document.body
  );
}
