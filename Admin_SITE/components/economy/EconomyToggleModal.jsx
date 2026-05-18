import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, AlertCircle, AlertTriangle } from 'lucide-react';

export default function EconomyToggleModal({ label, currentEnabled, rowCount, isMaster, onClose, onSave }) {
  const [comment, setComment] = useState('');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);

  const action = currentEnabled ? 'Выключить' : 'Включить';
  const isValidComment = comment.trim().length >= 5 && comment.trim().length <= 500;
  const canSave = isValidComment && !saving;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(comment.trim());
      onClose();
    } catch (e) {
      setError(e.message || 'Ошибка');
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-sff rounded-3xl w-full max-w-md shadow-2xl overflow-hidden">

        {/* Шапка */}
        <div className="p-6 border-b border-bd flex items-center justify-between">
          <div>
            <div className="text-[10px] font-black text-lbl uppercase tracking-widest">
              {isMaster ? 'Мастер-свич раздела' : 'Тумблер параметра'}
            </div>
            <h2 className="text-base font-black text-tx leading-tight">{label}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-sf2 rounded-xl transition active:scale-90">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Предупреждение для мастер-свича */}
          {isMaster && currentEnabled && (
            <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 flex gap-3">
              <AlertTriangle size={18} className="text-orange-500 shrink-0 mt-0.5" />
              <div className="text-sm text-orange-800">
                <span className="font-black">Внимание!</span> Все {rowCount} параметров раздела
                перестанут начислять. Это затронет всех участников.
              </div>
            </div>
          )}

          {/* Текущий статус */}
          <div className="flex items-center justify-between p-4 bg-sf2 rounded-2xl">
            <span className="text-[10px] font-black text-txd uppercase tracking-widest">Текущий статус</span>
            <span className={`text-sm font-black ${currentEnabled ? 'text-green-600' : 'text-lbl'}`}>
              {currentEnabled ? '🟢 Включён' : '⚫ Выключен'}
            </span>
          </div>

          <div className="flex items-center justify-center py-2">
            <span className="text-2xl">↓</span>
          </div>

          <div className="flex items-center justify-between p-4 bg-sf2 rounded-2xl">
            <span className="text-[10px] font-black text-txd uppercase tracking-widest">Станет</span>
            <span className={`text-sm font-black ${!currentEnabled ? 'text-green-600' : 'text-lbl'}`}>
              {!currentEnabled ? '🟢 Включён' : '⚫ Выключен'}
            </span>
          </div>

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
              placeholder="Опишите причину (мин. 5 символов)"
              rows={2}
              maxLength={500}
              className="w-full px-3 py-2 rounded-xl border border-amber-200 focus:border-amber-400
                         focus:outline-none text-sm bg-sff resize-none"
            />
            <div className="text-[10px] text-amber-500 mt-1 text-right">{comment.length}/500</div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-3 text-xs text-red-700 font-bold">
              {error}
            </div>
          )}
        </div>

        {/* Футер */}
        <div className="p-6 pt-0 flex gap-3">
          <button onClick={onClose}
            className="flex-1 py-3 bg-sf2 text-txd rounded-2xl font-black text-xs uppercase
                       hover:bg-gray-200 active:scale-95 transition">
            Отмена
          </button>
          <button onClick={handleSave} disabled={!canSave}
            className={`flex-1 py-3 rounded-2xl font-black text-xs uppercase active:scale-95 transition
              disabled:bg-gray-200 disabled:text-lbl disabled:cursor-not-allowed
              ${currentEnabled
                ? 'bg-red-500 text-white hover:bg-red-600'
                : 'bg-green-500 text-white hover:bg-green-600'}`}>
            {saving ? '⏳...' : action}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
