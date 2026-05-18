import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import EconomyMiniChart from './EconomyMiniChart';
import EconomyEditModal from './EconomyEditModal';

function formatDate(str) {
  if (!str) return '';
  try {
    return new Date(str).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return str; }
}

const ACTION_LABELS = {
  edit:     { label: 'Изменено',  cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  toggle:   { label: 'Тумблер',  cls: 'bg-sf2 text-txd border-bd2' },
  rollback: { label: 'Откат',    cls: 'bg-orange-50 text-orange-700 border-orange-200' },
  create:   { label: 'Создано',  cls: 'bg-green-50 text-green-700 border-green-200' },
};

export default function EconomyHistoryPanel({ settingKey, label, token, onClose, canEdit, onRolledBack }) {
  const [data, setData]           = useState(null);
  const [loadErr, setLoadErr]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [page, setPage]           = useState(0);
  const [rollbackTarget, setRollbackTarget] = useState(null); // entry
  const PER_PAGE = 20;

  const loadData = () => {
    setLoading(true);
    setLoadErr(null);
    fetch(`/api/economy/settings/${settingKey}/history?limit=${PER_PAGE}&offset=${page * PER_PAGE}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        if (!d || !Array.isArray(d.entries)) throw new Error('Неверный формат ответа');
        setData(d);
        setLoading(false);
      })
      .catch(e => { setLoadErr(e.message); setLoading(false); });
  };

  useEffect(() => { loadData(); }, [settingKey, page]);

  const handleRollback = async (entry, comment) => {
    const res = await fetch(`/api/economy/settings/${settingKey}/rollback/${entry.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ comment }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || 'Ошибка отката');
    }
    setPage(0);
    loadData();
    onRolledBack?.();
  };

  return createPortal(
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/30 z-40" />
      <div className="fixed top-0 right-0 h-full w-full md:w-[420px] bg-sff shadow-2xl z-50 flex flex-col overflow-hidden">

        {/* Шапка */}
        <div className="shrink-0 bg-sff border-b border-bd p-4 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-black text-lbl uppercase tracking-widest">История изменений</div>
            <h2 className="text-base font-black text-tx leading-tight">{label}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-sf2 rounded-xl transition active:scale-90">
            <X size={20} />
          </button>
        </div>

        {/* Тело */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && loadErr && (
            <div className="text-center py-12">
              <div className="text-3xl mb-3">⚠️</div>
              <div className="text-sm font-black text-txd">Не удалось загрузить историю</div>
              <div className="text-[11px] text-lbl mt-1">{loadErr}</div>
              <button onClick={loadData} className="mt-4 px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-black">
                Повторить
              </button>
            </div>
          )}

          {!loading && !loadErr && data && (
            <>
              {data.chart_data?.length > 1 && (
                <EconomyMiniChart data={data.chart_data} />
              )}

              {data.entries.length === 0 && (
                <div className="text-center text-lbl py-12 text-sm">Нет истории изменений</div>
              )}

              {data.entries.map(e => {
                const meta = ACTION_LABELS[e.action] || { label: e.action, cls: 'bg-sf2 text-txd border-bd2' };
                return (
                  <div key={e.id} className={`bg-sff border border-bd rounded-2xl p-4 ${e.is_rolled_back ? 'opacity-50' : ''}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase border ${meta.cls}`}>
                        {meta.label}
                      </span>
                      <span className="text-[10px] text-lbl font-bold">{formatDate(e.changed_at)}</span>
                    </div>

                    {e.action !== 'toggle' && e.old_value != null && (
                      <div className="flex items-center gap-2 text-sm font-bold mb-2">
                        <span className="line-through text-lbl">{e.old_value}</span>
                        <span className="text-lbl">→</span>
                        <span className="text-blue-600">{e.new_value}</span>
                      </div>
                    )}
                    {e.action === 'toggle' && (
                      <div className="text-sm font-bold mb-2 text-tx">
                        {e.new_enabled ? '🟢 Включено' : '⚫ Выключено'}
                      </div>
                    )}

                    <div className="text-xs text-txd italic mb-1">💬 {e.comment}</div>
                    <div className="text-[10px] text-lbl mb-2">
                      {e.changed_by?.username ? `@${e.changed_by.username}` : e.changed_by?.name || ''}
                      {' '}({e.changed_by?.role})
                    </div>

                    {e.is_rolled_back && (
                      <div className="text-[9px] font-black text-orange-500 uppercase">↩ Откатили</div>
                    )}

                    {/* Кнопка Откатить */}
                    {canEdit && e.can_rollback && !e.is_rolled_back && e.action !== 'toggle' && (
                      <button
                        onClick={() => setRollbackTarget(e)}
                        className="mt-2 px-3 py-1.5 bg-orange-50 text-orange-700 border border-orange-200
                                   rounded-xl text-[10px] font-black uppercase
                                   hover:bg-orange-100 active:scale-95 transition">
                        ↩ Откатить к {e.old_value}
                      </button>
                    )}
                  </div>
                );
              })}

              {data.entries.length === PER_PAGE && (
                <button
                  onClick={() => setPage(p => p + 1)}
                  className="w-full py-3 text-[11px] font-black text-blue-500 uppercase tracking-widest
                             hover:bg-blue-50 rounded-2xl transition">
                  ↓ Загрузить ещё ↓
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Модалка отката */}
      {rollbackTarget && (
        <EconomyEditModal
          row={{
            label: `Откат: ${label}`,
            value: rollbackTarget.new_value,
            unit: '',
            min_value: null,
            max_value: null,
          }}
          forceValue={rollbackTarget.old_value}
          onClose={() => setRollbackTarget(null)}
          onSave={(val, comment) => handleRollback(rollbackTarget, comment)}
        />
      )}
    </>,
    document.body
  );
}
