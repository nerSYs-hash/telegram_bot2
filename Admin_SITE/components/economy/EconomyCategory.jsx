import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import EconomySubTable from './EconomySubTable';
import EconomyToggleModal from './EconomyToggleModal';

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
  token, recentlyChanged, canEdit,
}) {
  const [settings, setSettings]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [sectionEnabled, setEnabled] = useState(category.is_enabled);
  const [masterModal, setMasterModal] = useState(false);

  useEffect(() => { setEnabled(category.is_enabled); }, [category.is_enabled]);

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
      <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden">
        {/* Шапка-аккордеон */}
        <div className="flex items-center">
          <button
            onClick={onToggle}
            className="flex-1 flex items-center gap-3 px-5 py-3.5 hover:bg-gray-50 transition text-left">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-black text-gray-900">{category.label}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">
                {category.rows_count} параметров
                {!sectionEnabled && <span className="ml-2 text-red-400 font-black">• ВЫКЛЮЧЕН</span>}
              </div>
            </div>
            <ChevronDown
              size={20}
              className={`text-gray-400 transition-transform duration-300 mr-4 ${isExpanded ? 'rotate-180' : ''}`}
            />
          </button>

          {/* Мастер-свич */}
          <button
            onClick={() => canEdit ? setMasterModal(true) : null}
            disabled={!canEdit}
            title={canEdit ? (sectionEnabled ? 'Выключить раздел' : 'Включить раздел') : 'Нет прав'}
            className={`mr-4 w-12 h-7 rounded-full relative transition-colors shrink-0 ${
              sectionEnabled ? 'bg-green-500' : 'bg-gray-200'
            } ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}>
            <div className={`w-5 h-5 bg-white rounded-full shadow absolute top-1 transition-all ${
              sectionEnabled ? 'right-1' : 'left-1'
            }`} />
          </button>
        </div>

        {/* Тело */}
        {isExpanded && (
          <div className="border-t border-gray-100 px-5 py-4 space-y-4">
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
              <div className="text-center text-gray-400 py-6 text-sm">Нет параметров</div>
            )}
          </div>
        )}
      </div>

      {masterModal && (
        <EconomyToggleModal
          label={category.label}
          currentEnabled={sectionEnabled}
          rowCount={category.rows_count}
          isMaster={true}
          onClose={() => setMasterModal(false)}
          onSave={handleMasterToggle}
        />
      )}
    </>
  );
}
