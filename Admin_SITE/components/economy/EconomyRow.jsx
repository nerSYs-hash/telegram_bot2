import { useState } from 'react';
import { BarChart3, Edit } from 'lucide-react';
import EconomyEditForm from './EconomyEditForm';
import EconomyToggleForm from './EconomyToggleForm';

export default function EconomyRow({ row, onOpenHistory, onUpdated, recentlyChanged, token, canEdit }) {
  const [editing, setEditing]   = useState(false);
  const [toggling, setToggling] = useState(false);

  const isRecent = recentlyChanged?.has(row.key);
  const isNew = row.created_at && (Date.now() - new Date(row.created_at).getTime()) < 86_400_000;
  const isExpanded = editing || toggling;

  const handleSave = async (newValue, comment) => {
    const res = await fetch(`/api/economy/settings/${row.key}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ value: newValue, comment }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || 'Ошибка API');
    }
    onUpdated?.(row.key, newValue, null);
  };

  const handleToggle = async (comment) => {
    const res = await fetch(`/api/economy/settings/${row.key}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ comment }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || 'Ошибка API');
    }
    onUpdated?.(row.key, null, !row.is_enabled);
  };

  return (
    <div className={`bg-sff rounded-xl border transition overflow-hidden ${
      isRecent ? 'border-amber-200 bg-amber-50/30' : isExpanded ? 'border-blue-200 shadow-sm' : 'border-bd hover:border-bd2'
    }`}>
      <div className="flex items-center gap-3 p-3">

        {/* Название */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold text-tx truncate">{row.label}</span>
            {isNew && (
              <span className="bg-orange-50 text-orange-600 border border-orange-200 rounded-full px-2 py-0.5 text-[8px] font-black uppercase">
                Новое
              </span>
            )}
            {isRecent && (
              <span className="bg-amber-50 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 text-[8px] font-black uppercase animate-pulse">
                Изменено
              </span>
            )}
          </div>
          {row.description && (
            <div className="text-[10px] text-lbl mt-0.5 truncate">{row.description}</div>
          )}
        </div>

        {/* Значение — фиксированная ширина */}
        <div className="w-24 text-right text-base font-black text-tx flex-shrink-0 whitespace-nowrap tabular-nums">
          {row.value} <span className="text-[10px] text-txd font-normal">{row.unit}</span>
        </div>

        {/* Тумблер — фиксированная ширина */}
        <div className="w-12 flex justify-center flex-shrink-0">
          <button
            onClick={() => canEdit && setToggling(v => !v)}
            disabled={!canEdit}
            title={canEdit ? (row.is_enabled ? 'Выключить' : 'Включить') : 'Нет прав'}
            className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
              row.is_enabled ? 'bg-green-500' : 'bg-gray-200'
            } ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}>
            <span className={`inline-block w-4 h-4 bg-sff rounded-full shadow transform transition-transform duration-200 ${
              row.is_enabled ? 'translate-x-6' : 'translate-x-1'
            }`} />
          </button>
        </div>

        {/* История — фиксированная ширина */}
        <div className="w-12 flex justify-center flex-shrink-0">
          <button
            onClick={() => onOpenHistory(row.key, row.label)}
            className="flex items-center justify-center gap-1 px-2 py-2 text-lbl hover:text-blue-500 hover:bg-blue-50 rounded-lg transition active:scale-90 min-w-[34px]">
            <BarChart3 size={15} />
            {row.history_count > 0 && (
              <span className="text-[9px] font-black tabular-nums">{row.history_count}</span>
            )}
          </button>
        </div>

        {/* Редактировать — фиксированная ширина */}
        <div className="w-10 flex justify-center flex-shrink-0">
          <button
            onClick={() => canEdit && setEditing(v => !v)}
            disabled={!canEdit}
            title={canEdit ? 'Изменить значение' : 'Нет прав'}
            className={`p-2 rounded-lg transition ${
              editing ? 'text-blue-600 bg-blue-50' :
              canEdit ? 'text-lbl hover:text-blue-500 hover:bg-blue-50 active:scale-90'
                      : 'text-gray-200 cursor-not-allowed'
            }`}>
            <Edit size={15} />
          </button>
        </div>
      </div>

      {/* Inline expand: редактирование */}
      {editing && (
        <div className="border-t border-blue-100 bg-blue-50/30 animate-in slide-in-from-top-2 duration-200">
          <EconomyEditForm
            row={row}
            onCancel={() => setEditing(false)}
            onSave={async (v, c) => { await handleSave(v, c); setEditing(false); }}
          />
        </div>
      )}

      {/* Inline expand: тумблер с комментарием */}
      {toggling && (
        <div className="border-t border-amber-100 bg-amber-50/30 animate-in slide-in-from-top-2 duration-200">
          <EconomyToggleForm
            label={row.label}
            currentEnabled={row.is_enabled}
            isMaster={false}
            onCancel={() => setToggling(false)}
            onSave={async (c) => { await handleToggle(c); setToggling(false); }}
          />
        </div>
      )}
    </div>
  );
}
