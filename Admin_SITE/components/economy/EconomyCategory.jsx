import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import EconomySubTable from './EconomySubTable';
import EconomyToggleForm from './EconomyToggleForm';

function groupBy(arr, key) {
  return arr.reduce((acc, item) => {
    const k = item[key] || 'base';
    (acc[k] = acc[k] || []).push(item);
    return acc;
  }, {});
}

function _categoryEmoji(key) {
  const map = { mining:'💰', vip_bbs:'💎', lottery:'🎰', bingo:'🎱', monthly_gift:'🎁', referral:'👥', bbs_bonus:'❤️' };
  return map[key] || '⚙️';
}

export default function EconomyCategory({
  category, isExpanded, onToggle, onOpenHistory,
  token, recentlyChanged, canEdit, sectionEnabled,
}) {
  const [settings, setSettings]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [enabled, setEnabled]       = useState(sectionEnabled ?? category.is_enabled);
  const [masterModal, setMasterModal] = useState(false);

  useEffect(() => {
    setEnabled(sectionEnabled ?? category.is_enabled);
  }, [sectionEnabled, category.is_enabled]);

  useEffect(() => {
    if (!isExpanded || settings) return;
    setLoading(true);
    fetch(`/api/economy/settings?category=${category.key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => { setSettings(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isExpanded]);

  // Обновить строку после изменения
  const handleRowUpdated = (key, newValue, newEnabled) => {
    setSettings(prev => prev?.map(s => {
      if (s.key !== key) return s;
      return {
        ...s,
        ...(newValue != null  ? { value: newValue } : {}),
        ...(newEnabled != null ? { is_enabled: newEnabled } : {}),
        history_count: (s.history_count || 0) + 1,
      };
    }));
  };

  const handleMasterToggle = async (comment) => {
    const res = await fetch(`/api/economy/categories/${category.key}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ comment }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || 'Ошибка');
    }
    setEnabled(v => !v);
  };

  const grouped = settings ? groupBy(settings, 'subcategory') : {};

  return (
    <>
      <div className="bg-sff rounded-3xl border border-bd shadow-sm overflow-hidden">
        {/* Шапка-аккордеон */}
        <div className="flex items-center">
          <button
            onClick={onToggle}
            className="flex-1 flex items-center gap-3 px-5 py-3.5 hover:bg-sf2 transition text-left">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-black text-tx">{category.label}</div>
              <div className="text-[10px] text-lbl mt-0.5">
                {category.rows_count} параметров
                {!enabled && <span className="ml-2 text-red-400 font-black">• ВЫКЛЮЧЕН</span>}
              </div>
            </div>
            <ChevronDown
              size={20}
              className={`text-lbl transition-transform duration-300 mr-4 ${isExpanded ? 'rotate-180' : ''}`}
            />
          </button>

          {/* Мастер-свич — единый стиль с строками */}
          <button
            onClick={() => canEdit ? setMasterModal(v => !v) : null}
            disabled={!canEdit}
            title={canEdit ? (enabled ? 'Выключить раздел' : 'Включить раздел') : 'Нет прав'}
            className={`mr-4 relative inline-flex items-center w-11 h-6 rounded-full transition-colors shrink-0 ${
              enabled ? 'bg-green-500' : 'bg-gray-200'
            } ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}>
            <span className={`inline-block w-4 h-4 bg-sff rounded-full shadow transform transition-transform duration-200 ${
              enabled ? 'translate-x-6' : 'translate-x-1'
            }`} />
          </button>
        </div>

        {/* Inline форма мастер-тумблера */}
        {masterModal && (
          <div className="border-t border-amber-100 bg-amber-50/30 animate-in slide-in-from-top-2 duration-200">
            <EconomyToggleForm
              label={category.label}
              currentEnabled={enabled}
              rowCount={category.rows_count}
              isMaster={true}
              onCancel={() => setMasterModal(false)}
              onSave={async (c) => { await handleMasterToggle(c); setMasterModal(false); }}
            />
          </div>
        )}

        {/* Тело */}
        {isExpanded && (
          <div className="border-t border-bd px-5 py-4 space-y-4">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            {!loading && settings && Object.entries(grouped).map(([subKey, rows]) => (
              <EconomySubTable
                key={subKey}
                subcategory={subKey}
                rows={rows}
                onOpenHistory={onOpenHistory}
                onRowUpdated={handleRowUpdated}
                recentlyChanged={recentlyChanged}
                token={token}
                canEdit={canEdit}
              />
            ))}
            {!loading && settings?.length === 0 && (
              <div className="text-center text-lbl py-6 text-sm">Нет параметров</div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
