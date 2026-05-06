import { useState, useEffect } from 'react';
import { ArrowRight } from 'lucide-react';

const CATEGORY_THEME = {
  mining:       { emoji: '⛏️',  gradient: 'from-amber-50 to-yellow-50',   border: 'border-amber-100',   accent: 'text-amber-600',  dot: 'bg-amber-400' },
  vip_bbs:      { emoji: '💎',  gradient: 'from-blue-50 to-indigo-50',    border: 'border-blue-100',    accent: 'text-blue-600',   dot: 'bg-blue-400' },
  lottery:      { emoji: '🎰',  gradient: 'from-purple-50 to-pink-50',    border: 'border-purple-100',  accent: 'text-purple-600', dot: 'bg-purple-400' },
  bingo:        { emoji: '🎱',  gradient: 'from-teal-50 to-cyan-50',      border: 'border-teal-100',    accent: 'text-teal-600',   dot: 'bg-teal-400' },
  monthly_gift: { emoji: '🎁',  gradient: 'from-rose-50 to-pink-50',      border: 'border-rose-100',    accent: 'text-rose-600',   dot: 'bg-rose-400' },
  referral:     { emoji: '👥',  gradient: 'from-green-50 to-emerald-50',  border: 'border-green-100',   accent: 'text-green-600',  dot: 'bg-green-400' },
  bbs_bonus:    { emoji: '❤️',  gradient: 'from-red-50 to-orange-50',     border: 'border-red-100',     accent: 'text-red-500',    dot: 'bg-red-400' },
};

const DEFAULT_THEME = { emoji: '⚙️', gradient: 'from-gray-50 to-slate-50', border: 'border-gray-100', accent: 'text-gray-600', dot: 'bg-gray-400' };

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString('ru-RU');
}

export default function EconomyCategoryCard({
  category,
  onOpenDetails,
  onMasterToggle,
  sectionEnabled,
  canEdit,
  token,
}) {
  const [topValue, setTopValue]       = useState(null);
  const [topLabel, setTopLabel]       = useState('');
  const [showToggleForm, setShowToggleForm] = useState(false);
  const [toggleComment, setToggleComment]   = useState('');
  const [toggleLoading, setToggleLoading]   = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`/api/economy/settings?category=${category.key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => {
        if (Array.isArray(d) && d.length > 0) {
          setTopLabel(d[0].label);
          setTopValue(d[0].value);
        }
      })
      .catch(() => {});
  }, [category.key, token]);

  const handleToggle = async () => {
    setToggleLoading(true);
    try {
      await onMasterToggle(toggleComment);
      setShowToggleForm(false);
      setToggleComment('');
    } finally {
      setToggleLoading(false);
    }
  };

  const theme = CATEGORY_THEME[category.key] || DEFAULT_THEME;
  const isDisabled = !sectionEnabled;

  return (
    <div className={`relative rounded-2xl border overflow-hidden transition-all duration-200
      ${isDisabled
        ? 'bg-gray-50 border-gray-200 opacity-60'
        : `bg-gradient-to-br ${theme.gradient} ${theme.border}`
      }`}>

      {/* Основной контент — кликабельная зона */}
      <button
        onClick={() => onOpenDetails(category.key)}
        className="w-full text-left p-4 block group"
      >
        {/* Шапка: эмодзи + статус */}
        <div className="flex items-start justify-between mb-3">
          <span className="text-2xl leading-none">{theme.emoji}</span>
          <div className="flex items-center gap-1.5">
            {isDisabled && (
              <span className="text-[9px] font-black uppercase tracking-wider text-red-500
                               bg-red-100 px-1.5 py-0.5 rounded-full">OFF</span>
            )}
            {/* Мастер-свич */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (canEdit) setShowToggleForm(v => !v);
              }}
              disabled={!canEdit}
              title={sectionEnabled ? 'Выключить раздел' : 'Включить раздел'}
              className={`relative inline-flex items-center w-9 h-5 rounded-full transition-colors shrink-0
                ${sectionEnabled ? 'bg-green-400' : 'bg-gray-300'}
                ${canEdit ? 'cursor-pointer hover:opacity-90' : 'cursor-not-allowed opacity-50'}`}
            >
              <span className={`inline-block w-3.5 h-3.5 bg-white rounded-full shadow-sm
                                transform transition-transform duration-150
                                ${sectionEnabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </button>
          </div>
        </div>

        {/* Название */}
        <div className="text-sm font-black text-gray-900 leading-tight mb-1">
          {category.label}
        </div>

        {/* Главный параметр */}
        {topLabel ? (
          <div className="mt-2">
            <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider truncate">
              {topLabel}
            </div>
            <div className={`text-xl font-black ${theme.accent} leading-tight`}>
              {fmt(topValue)}
            </div>
          </div>
        ) : (
          <div className="text-[10px] text-gray-400 mt-1">{category.rows_count} параметров</div>
        )}

        {/* Подсказка "открыть" */}
        <div className="mt-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-[10px] font-semibold text-gray-500">Настроить</span>
          <ArrowRight size={11} className="text-gray-400" />
        </div>
      </button>

      {/* Форма подтверждения переключения */}
      {showToggleForm && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="border-t border-amber-100 bg-amber-50/80 px-4 py-3 space-y-2 animate-in slide-in-from-bottom-1 duration-200"
        >
          <div className="text-[11px] font-bold text-amber-900">
            {sectionEnabled ? '🔴 Выключить' : '🟢 Включить'} «{category.label}»?
          </div>
          <input
            type="text"
            value={toggleComment}
            onChange={(e) => setToggleComment(e.target.value)}
            placeholder="Причина (необязательно)"
            className="w-full text-xs px-2.5 py-1.5 border border-amber-200 rounded-lg bg-white
                       placeholder-amber-300 focus:outline-none focus:border-amber-400"
          />
          <div className="flex gap-2">
            <button
              onClick={() => { setShowToggleForm(false); setToggleComment(''); }}
              disabled={toggleLoading}
              className="flex-1 py-1.5 text-xs font-bold bg-white border border-gray-200 rounded-lg
                         hover:bg-gray-50 transition disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              onClick={handleToggle}
              disabled={toggleLoading}
              className="flex-1 py-1.5 text-xs font-bold bg-amber-500 text-white rounded-lg
                         hover:bg-amber-600 transition disabled:opacity-50"
            >
              {toggleLoading ? '⏳' : 'Подтвердить'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
