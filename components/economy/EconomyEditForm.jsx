// EconomyEditForm — inline-форма редактирования значения параметра
// экономики (новое значение + обязательная причина-комментарий).

import { useState } from 'react';
import { AlertCircle } from 'lucide-react';

export default function EconomyEditForm({ row, onCancel, onSave, forceValue = null }) {
  const [value, setValue]     = useState(forceValue !== null ? String(forceValue) : String(row.value));
  const [comment, setComment] = useState('');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);

  const isValueLocked = forceValue !== null;

  const isValidValue = () => {
    if (isValueLocked) return true;
    const v = parseFloat(String(value).replace(',', '.'));
    if (isNaN(v)) return false;
    if (row.min_value != null && v < row.min_value) return false;
    if (row.max_value != null && v > row.max_value) return false;
    return true;
  };

  const isValidComment = () => comment.trim().length >= 5 && comment.trim().length <= 500;
  const canSave = isValidValue() && isValidComment() && !saving;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const v = isValueLocked ? forceValue : parseFloat(String(value).replace(',', '.'));
      await onSave(v, comment.trim());
    } catch (e) {
      setError(e.message || 'Ошибка сохранения');
      setSaving(false);
    }
  };

  return (
    <div className="p-4 grid grid-cols-1 md:grid-cols-[200px_1fr_auto] gap-3 items-start">
      {/* Новое значение */}
      {!isValueLocked ? (
        <div>
          <label className="text-[10px] font-black text-txd uppercase tracking-widest mb-1.5 flex items-center h-[14px] whitespace-nowrap">
            Новое значение
          </label>
          <div className="relative">
            <input
              type="text"
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder={`${row.min_value ?? 0} — ${row.max_value ?? '∞'}`}
              autoFocus
              className="w-full px-3 py-2.5 pr-10 rounded-xl border-2 border-[color-mix(in_oklab,var(--cta)_30%,transparent)]
                         focus:border-blue-400 focus:outline-none text-sm font-bold bg-sff"
            />
            {row.unit && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-lbl text-xs">
                {row.unit}
              </span>
            )}
          </div>
          {!isValidValue() && value !== '' && (
            <div className="text-[10px] text-danger font-semibold mt-1">
              Допустимо: {row.min_value ?? '—'} — {row.max_value ?? '—'}
            </div>
          )}
        </div>
      ) : (
        <div>
          <label className="text-[10px] font-black text-txd uppercase tracking-widest mb-1.5 block">
            Откат к значению
          </label>
          <div className="px-3 py-2.5 rounded-xl bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border-2 border-[color-mix(in_oklab,var(--warn)_30%,transparent)] text-sm font-black text-warn">
            {forceValue} {row.unit}
          </div>
        </div>
      )}

      {/* Комментарий */}
      <div>
        <label className="text-[10px] font-black text-warn uppercase tracking-widest mb-1.5 block flex items-center gap-1.5">
          <AlertCircle size={11} /> Причина (обязательно)
        </label>
        <textarea
          value={comment}
          onChange={e => setComment(e.target.value)}
          placeholder="Опишите причину (мин. 5 символов)"
          rows={2}
          maxLength={500}
          className="w-full px-3 py-2 rounded-xl border-2 border-[color-mix(in_oklab,var(--warn)_30%,transparent)] focus:border-amber-400
                     focus:outline-none text-sm bg-sff resize-none"
        />
        <div className={`text-[10px] mt-0.5 text-right ${comment.length > 450 ? 'text-warn' : 'text-warn'}`}>
          {comment.length}/500
        </div>
      </div>

      {/* Кнопки */}
      <div className="flex md:flex-col gap-2 md:pt-5">
        <button
          onClick={handleSave}
          disabled={!canSave}
          className="px-4 py-2.5 bg-blue-600 text-white rounded-xl font-black text-[11px] uppercase
                     hover:bg-blue-700 active:scale-95 transition whitespace-nowrap
                     disabled:bg-bd2 disabled:text-lbl disabled:cursor-not-allowed">
          {saving ? '⏳' : isValueLocked ? '↩ Откатить' : '✅ Сохранить'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2.5 bg-sff border border-bd2 text-txd rounded-xl
                     font-black text-[11px] uppercase hover:bg-sf2 active:scale-95 transition">
          Отмена
        </button>
      </div>

      {error && (
        <div className="md:col-span-3 bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border border-[color-mix(in_oklab,var(--danger)_40%,transparent)] rounded-xl p-2.5 text-xs text-danger font-bold">
          {error}
        </div>
      )}
    </div>
  );
}
