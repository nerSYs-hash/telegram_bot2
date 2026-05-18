import { useState } from 'react';
import { AlertCircle, AlertTriangle } from 'lucide-react';

export default function EconomyToggleForm({ label, currentEnabled, rowCount, isMaster, onCancel, onSave }) {
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
    } catch (e) {
      setError(e.message || 'Ошибка');
      setSaving(false);
    }
  };

  return (
    <div className="p-4 space-y-3">
      {/* Предупреждение для мастер-свича */}
      {isMaster && currentEnabled && (
        <div className="bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border border-[color-mix(in_oklab,var(--warn)_40%,transparent)] rounded-xl p-3 flex gap-2.5">
          <AlertTriangle size={16} className="text-warn shrink-0 mt-0.5" />
          <div className="text-xs text-warn">
            <span className="font-black">Внимание!</span> Все {rowCount} параметров раздела перестанут начислять.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-start">
        <div>
          <label className="text-[10px] font-black text-warn uppercase tracking-widest mb-1.5 block flex items-center gap-1.5">
            <AlertCircle size={11} /> Причина — {action.toLowerCase()} «{label}»
          </label>
          <textarea
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Опишите причину (мин. 5 символов)"
            autoFocus
            rows={2}
            maxLength={500}
            className="w-full px-3 py-2 rounded-xl border-2 border-[color-mix(in_oklab,var(--warn)_30%,transparent)] focus:border-amber-400
                       focus:outline-none text-sm bg-sff resize-none"
          />
          <div className={`text-[10px] mt-0.5 text-right ${comment.length > 450 ? 'text-warn' : 'text-warn'}`}>
            {comment.length}/500
          </div>
        </div>

        <div className="flex md:flex-col gap-2 md:pt-5">
          <button
            onClick={handleSave}
            disabled={!canSave}
            className={`px-4 py-2.5 rounded-xl font-black text-[11px] uppercase active:scale-95 transition whitespace-nowrap
              disabled:bg-bd2 disabled:text-lbl disabled:cursor-not-allowed
              ${currentEnabled
                ? 'bg-red-500 text-white hover:bg-red-600'
                : 'bg-green-500 text-white hover:bg-green-600'}`}>
            {saving ? '⏳' : action}
          </button>
          <button
            onClick={onCancel}
            className="px-4 py-2.5 bg-sff border border-bd2 text-txd rounded-xl
                       font-black text-[11px] uppercase hover:bg-sf2 active:scale-95 transition">
            Отмена
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] border border-[color-mix(in_oklab,var(--danger)_40%,transparent)] rounded-xl p-2.5 text-xs text-danger font-bold">
          {error}
        </div>
      )}
    </div>
  );
}
