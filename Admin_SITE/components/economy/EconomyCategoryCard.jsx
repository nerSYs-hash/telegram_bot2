import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';

function _categoryEmoji(key) {
  const map = {
    mining: '💰',
    vip_bbs: '💎',
    lottery: '🎰',
    bingo: '🎱',
    monthly_gift: '🎁',
    referral: '👥',
    bbs_bonus: '❤️'
  };
  return map[key] || '⚙️';
}

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
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
  const [topValue, setTopValue] = useState(null);
  const [topLabel, setTopLabel] = useState('');
  const [showToggleForm, setShowToggleForm] = useState(false);
  const [toggleComment, setToggleComment] = useState('');
  const [toggleLoading, setToggleLoading] = useState(false);

  // Загрузить главный параметр категории
  useEffect(() => {
    if (!token) return;
    fetch(`/api/economy/settings?category=${category.key}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => {
        if (Array.isArray(d) && d.length > 0) {
          const main = d[0];
          setTopLabel(main.label);
          setTopValue(main.value);
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

  const emoji = _categoryEmoji(category.key);
  const isDisabled = !sectionEnabled;

  return (
    <button
      onClick={() => onOpenDetails(category.key)}
      className={`relative w-full text-left rounded-lg border-1.5 transition-all duration-200 overflow-hidden
        ${isDisabled
          ? 'border-red-200/50 bg-red-50/20 hover:bg-red-50/30'
          : 'border-gray-200 bg-gray-50/50 hover:bg-white hover:shadow-sm'
        }`}
    >
      {/* Содержимое */}
      <div className="p-2.5 flex items-center justify-between gap-1.5">
        {/* Левая часть */}
        <div className="flex-1 min-w-0 flex items-center gap-1.5">
          <span className="text-base shrink-0">{emoji}</span>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-bold text-gray-900 truncate">
              {category.label}
            </div>
            <div className="text-[9px] text-gray-500 truncate">
              {topLabel ? `${topLabel}: ${fmt(topValue)}` : `${category.rows_count} пар.`}
            </div>
          </div>
        </div>

        {/* Правая часть - свич + меню */}
        <div className="flex items-center gap-1 shrink-0">
          {isDisabled && (
            <div className="text-[9px] font-black text-red-500 uppercase px-1 py-0.5 bg-red-100/50 rounded">
              OFF
            </div>
          )}
          
          {/* Мастер-свич */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (canEdit) setShowToggleForm(true);
            }}
            disabled={!canEdit}
            className={`relative inline-flex items-center w-8 h-4.5 rounded-full transition-colors shrink-0 ${
              sectionEnabled ? 'bg-green-400' : 'bg-gray-300'
            } ${canEdit ? 'cursor-pointer hover:opacity-90' : 'cursor-not-allowed opacity-60'}`}
          >
            <span
              className={`inline-block w-3 h-3 bg-white rounded-full shadow transform transition-transform duration-150 ${
                sectionEnabled ? 'translate-x-3.5' : 'translate-x-0.5'
              }`}
            />
          </button>

          {/* Иконка раскрытия */}
          <ChevronDown
            size={14}
            className="text-gray-400 shrink-0"
          />
        </div>
      </div>

      {/* Форма подтверждения переключения */}
      {showToggleForm && (
        <div 
          onClick={(e) => e.stopPropagation()}
          className="border-t border-amber-100 bg-amber-50/60 p-2 space-y-1.5 animate-in slide-in-from-bottom-1 duration-200"
        >
          <div className="text-[9px] font-semibold text-amber-900">
            {sectionEnabled ? 'Выключить' : 'Включить'} "{category.label}"?
          </div>
          <input
            type="text"
            value={toggleComment}
            onChange={(e) => setToggleComment(e.target.value)}
            placeholder="Комментарий"
            className="w-full text-[9px] px-1.5 py-1 border border-amber-200 rounded bg-white placeholder-amber-300 focus:outline-none focus:border-amber-400"
          />
          <div className="flex gap-1">
            <button
              onClick={() => setShowToggleForm(false)}
              disabled={toggleLoading}
              className="flex-1 px-1 py-0.5 text-[8px] font-semibold bg-white border border-gray-200 rounded hover:bg-gray-50 transition disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              onClick={handleToggle}
              disabled={toggleLoading}
              className="flex-1 px-1 py-0.5 text-[8px] font-semibold bg-amber-500 text-white rounded hover:bg-amber-600 transition disabled:opacity-50"
            >
              {toggleLoading ? '⏳' : 'OK'}
            </button>
          </div>
        </div>
      )}
    </button>
  );
}
