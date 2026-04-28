import { useState } from 'react';
import { BarChart3, Edit } from 'lucide-react';
import EconomyEditModal from './EconomyEditModal';
import EconomyToggleModal from './EconomyToggleModal';

export default function EconomyRow({ row, onOpenHistory, onUpdated, recentlyChanged, token, canEdit }) {
  const [editing, setEditing]   = useState(false);
  const [toggling, setToggling] = useState(false);

  const isRecent = recentlyChanged?.has(row.key);
  const isNew = row.created_at && (Date.now() - new Date(row.created_at).getTime()) < 86_400_000;

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
    <>
      <div className={`flex items-center gap-3 p-3 bg-white rounded-xl border transition ${
        isRecent ? 'border-amber-200 bg-amber-50/30' : 'border-gray-100 hover:border-gray-200'
      }`}>

        {/* Название */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold text-gray-900 truncate">{row.label}</span>
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
            <div className="text-[10px] text-gray-400 mt-0.5 truncate">{row.description}</div>
          )}
        </div>

        {/* Значение */}
        <div className="text-base font-black text-gray-900 flex-shrink-0 whitespace-nowrap">
          {row.value} <span className="text-[10px] text-gray-500 font-normal">{row.unit}</span>
        </div>

        {/* Тумблер */}
        <button
          onClick={() => canEdit && setToggling(true)}
          disabled={!canEdit}
          title={canEdit ? (row.is_enabled ? 'Выключить' : 'Включить') : 'Нет прав'}
          className={`w-12 h-6 rounded-full flex-shrink-0 relative transition-colors ${
            row.is_enabled ? 'bg-green-500' : 'bg-gray-200'
          } ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}>
          <div className={`w-5 h-5 bg-white rounded-full shadow absolute top-0.5 transition-all ${
            row.is_enabled ? 'right-0.5' : 'left-0.5'
          }`} />
        </button>

        {/* История */}
        <button
          onClick={() => onOpenHistory(row.key, row.label)}
          className="flex items-center gap-1 p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition active:scale-90 flex-shrink-0">
          <BarChart3 size={15} />
          {row.history_count > 0 && (
            <span className="text-[9px] font-black">{row.history_count}</span>
          )}
        </button>

        {/* Редактировать */}
        <button
          onClick={() => canEdit && setEditing(true)}
          disabled={!canEdit}
          title={canEdit ? 'Изменить значение' : 'Нет прав'}
          className={`p-2 rounded-lg transition flex-shrink-0 ${
            canEdit
              ? 'text-gray-400 hover:text-blue-500 hover:bg-blue-50 active:scale-90'
              : 'text-gray-200 cursor-not-allowed'
          }`}>
          <Edit size={15} />
        </button>
      </div>

      {editing && (
        <EconomyEditModal
          row={row}
          onClose={() => setEditing(false)}
          onSave={handleSave}
        />
      )}

      {toggling && (
        <EconomyToggleModal
          label={row.label}
          currentEnabled={row.is_enabled}
          isMaster={false}
          onClose={() => setToggling(false)}
          onSave={handleToggle}
        />
      )}
    </>
  );
}
