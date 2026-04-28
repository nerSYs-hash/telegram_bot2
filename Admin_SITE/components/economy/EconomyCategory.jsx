import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import EconomySubTable from './EconomySubTable';

function groupBy(arr, key) {
  return arr.reduce((acc, item) => {
    const k = item[key] || 'base';
    (acc[k] = acc[k] || []).push(item);
    return acc;
  }, {});
}

export default function EconomyCategory({ category, isExpanded, onToggle, onOpenHistory, token, recentlyChanged }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);

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

  const grouped = settings ? groupBy(settings, 'subcategory') : {};

  return (
    <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Шапка-аккордеон */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-6 hover:bg-gray-50 transition text-left">
        <div className="flex items-center gap-4">
          <span className="text-2xl">{_categoryEmoji(category.key)}</span>
          <div>
            <div className="text-base font-black text-gray-900">{category.label}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">
              {category.rows_count} параметров
              {!category.is_enabled && <span className="ml-2 text-red-400 font-black">• ВЫКЛЮЧЕН</span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {/* Master-switch (визуальный, в Пакете 3 станет рабочим) */}
          <div className={`w-12 h-6 rounded-full relative ${category.is_enabled ? 'bg-green-500' : 'bg-gray-200'}`}>
            <div className={`w-5 h-5 bg-white rounded-full shadow absolute top-0.5 transition-all ${category.is_enabled ? 'right-0.5' : 'left-0.5'}`} />
          </div>
          <ChevronDown
            size={20}
            className={`text-gray-400 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {/* Тело */}
      {isExpanded && (
        <div className="border-t border-gray-100 p-6 space-y-5">
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
              recentlyChanged={recentlyChanged}
            />
          ))}
          {!loading && settings && settings.length === 0 && (
            <div className="text-center text-gray-400 py-6 text-sm">Нет параметров</div>
          )}
        </div>
      )}
    </div>
  );
}

function _categoryEmoji(key) {
  const map = {
    mining:       '💰',
    vip_bbs:      '💎',
    lottery:      '🎰',
    bingo:        '🎱',
    monthly_gift: '🎁',
    referral:     '👥',
    bbs_bonus:    '❤️',
  };
  return map[key] || '⚙️';
}
