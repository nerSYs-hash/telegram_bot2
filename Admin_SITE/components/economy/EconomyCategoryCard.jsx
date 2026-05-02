import { useState } from 'react';

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

export default function EconomyCategoryCard({
  category,
  onOpenDetails,
  onMasterToggle,
  sectionEnabled,
  canEdit,
  isLoading,
}) {
  const [showToggleForm, setShowToggleForm] = useState(false);
  const [toggleComment, setToggleComment] = useState('');
  const [toggleLoading, setToggleLoading] = useState(false);

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
    <div
      className={`relative bg-white rounded-2xl border transition-all duration-300 overflow-hidden
        ${isDisabled
          ? 'border-red-200 bg-red-50/30'
          : 'border-gray-200 hover:border-blue-300 hover:shadow-md'
        }`}
    >
      {/* Основное содержимое карточки */}
      <button
        onClick={() => onOpenDetails(category.key)}
        className="w-full text-left p-4 hover:bg-gray-50/50 active:bg-gray-100 transition"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* Иконка и название */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-2xl">{emoji}</span>
              <h3 className="text-sm font-black text-gray-900 truncate">
                {category.label}
              </h3>
            </div>

            {/* Мета информация */}
            <div className="space-y-2">
              <div className="text-xs text-gray-500">
                {category.rows_count} параметров
              </div>

              {isDisabled && (
                <div className="inline-block px-2 py-1 bg-red-100 rounded-lg">
                  <span className="text-[10px] font-black text-red-600">
                    ВЫКЛЮЧЕН
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Мастер-свич */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (canEdit) setShowToggleForm(true);
            }}
            disabled={!canEdit}
            title={
              canEdit
                ? sectionEnabled
                  ? 'Выключить раздел'
                  : 'Включить раздел'
                : 'Нет прав'
            }
            className={`relative inline-flex items-center w-12 h-7 rounded-full transition-colors shrink-0 ${
              sectionEnabled ? 'bg-green-500' : 'bg-gray-300'
            } ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}
          >
            <span
              className={`inline-block w-5 h-5 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                sectionEnabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </button>

      {/* Форма подтверждения переключения */}
      {showToggleForm && (
        <div className="border-t border-amber-100 bg-amber-50 p-4 space-y-3 animate-in slide-in-from-bottom-2 duration-200">
          <div className="text-xs font-medium text-amber-900">
            {sectionEnabled ? 'Выключить' : 'Включить'} раздел "{category.label}"?
          </div>
          <textarea
            value={toggleComment}
            onChange={(e) => setToggleComment(e.target.value)}
            placeholder="Комментарий (опционально)"
            className="w-full text-xs p-2 border border-amber-200 rounded-lg bg-white placeholder-amber-400 focus:outline-none focus:border-amber-400"
            rows="2"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setShowToggleForm(false)}
              disabled={toggleLoading}
              className="flex-1 px-2 py-1.5 text-xs font-semibold bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              onClick={handleToggle}
              disabled={toggleLoading}
              className="flex-1 px-2 py-1.5 text-xs font-semibold bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition disabled:opacity-50"
            >
              {toggleLoading ? '⏳' : 'Подтвердить'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
