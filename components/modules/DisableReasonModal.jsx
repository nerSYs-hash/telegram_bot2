import { useState } from 'react';
import Button from '../shared/Button';

/**
 * Модалка подтверждения отключения модуля с обязательной причиной.
 *
 * props:
 *   moduleName       — название модуля для заголовка
 *   onCancel()       — клик «Отмена» или клик по подложке
 *   onConfirm(reason)— клик «Подтвердить отключение», получает trimmed reason
 */
export default function DisableReasonModal({ moduleName, onCancel, onConfirm }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const tooShort = reason.trim().length < 3;

  const submit = async () => {
    if (tooShort || busy) return;
    setBusy(true);
    try {
      await onConfirm(reason.trim());
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150 p-4"
      onClick={onCancel}
    >
      <div
        className="bg-sff rounded-3xl shadow-2xl p-6 w-full max-w-md space-y-4 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <p className="font-black text-tx text-base leading-tight">
            Отключить модуль «{moduleName}»?
          </p>
          <p className="text-sm text-txd mt-1.5 leading-relaxed">
            Расскажите коротко, зачем — это попадёт в журнал.
          </p>
        </div>

        <textarea
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: не нужен в моём чате"
          className="w-full min-h-[88px] rounded-2xl border border-bd px-3 py-2 text-sm bg-sff
                     focus:outline-none focus:border-cta resize-y"
        />

        <div className="flex gap-2 pt-1">
          <Button variant="secondary" size="md" block onClick={onCancel} disabled={busy}>
            Отмена
          </Button>
          <Button variant="danger" size="md" block onClick={submit} disabled={tooShort || busy}>
            {busy ? 'Отключаю…' : 'Подтвердить'}
          </Button>
        </div>
      </div>
    </div>
  );
}
