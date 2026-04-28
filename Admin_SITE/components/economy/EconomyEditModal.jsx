import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, AlertCircle } from 'lucide-react';

export default function EconomyEditModal({ row, onClose, onSave, forceValue = null }) {
  const [value, setValue]   = useState(forceValue !== null ? String(forceValue) : String(row.value));
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
      onClose();
    } catch (e) {
      setError(e.message || 'Ошибка сохранения');
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden">

        {/* Шапка */}
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
              {isValueLocked ? 'Откат значения' : 'Изменить параметр'}
            </div>
            <h2 className="text-base font-black text-gray-900 leading-tight">{row.label}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-xl transition active:scale-90">
            <X size={20} />
          </button>
        </div>

        {/* Тело */}
        <div className="p-6 space-y-4">
          {/* Старое значение */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
            <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">
              {isValueLocked ? 'Будет восстановлено' : 'Текущее значение'}
            </span>
            <span className="text-base font-black text-gray-700">
              {isValueLocked ? forceValue : row.value} <span className="text-gray-400 font-normal text-sm">{row.unit}</span>
            </span>
          </div>

          {/* Новое значение */}
          {!isValueLocked && (
            <div>
              <label className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2 block">
                Новое значение
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={value}
                  onChange={e => setValue(e.target.value)}
                  placeholder={`${row.min_value ?? 0} — ${row.max_value ?? '∞'}`}
                  className="w-full px-4 py-3 pr-12 rounded-2xl border-2 border-gray-100
                             focus:border-blue-300 focus:outline-none text-base font-bold"
                />
                {row.unit && (
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                    {row.unit}
                  </span>
                )}
              </div>
              {!isValidValue() && value !== '' && (
                <div className="text-[10px] text-red-500 font-semibold mt-1 px-1">
                  Допустимый диапазон: {row.min_value ?? '—'} — {row.max_value ?? '—'}
                </div>
              )}
            </div>
          )}

          {/* Комментарий */}
          <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle size={13} className="text-amber-600 shrink-0" />
              <span className="text-[10px] font-black text-amber-700 uppercase tracking-widest">
                Причина (обязательно)
              </span>
            </div>
            <textarea
              value={comment}
              onChange={e => setComment(e.target.value)}
              placeholder="Опишите причину изменения (мин. 5 символов)"
              rows={3}
              maxLength={500}
              className="w-full px-3 py-2 rounded-xl border border-amber-200 focus:border-amber-400
                         focus:outline-none text-sm bg-white resize-none"
            />
            <div className={`text-[10px] mt-1 text-right ${comment.length > 450 ? 'text-orange-500' : 'text-amber-500'}`}>
              {comment.length}/500
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-3 text-xs text-red-700 font-bold">
              {error}
            </div>
          )}
        </div>

        {/* Футер */}
        <div className="p-6 pt-0 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-gray-100 text-gray-600 rounded-2xl font-black text-xs uppercase
                       hover:bg-gray-200 active:scale-95 transition">
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="flex-1 py-3 bg-blue-600 text-white rounded-2xl font-black text-xs uppercase
                       hover:bg-blue-700 active:scale-95 transition
                       disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed">
            {saving ? '⏳ Сохранение...' : isValueLocked ? '↩ Откатить' : '✅ Сохранить'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
