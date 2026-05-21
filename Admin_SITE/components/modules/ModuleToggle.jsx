import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import Toggle from '../shared/Toggle';
import DisableReasonModal from './DisableReasonModal';

/**
 * Единый переключатель модуля. Используется в трёх местах:
 *   - на карточке в каталоге модулей,
 *   - в верхнем «паспорте» внутри экрана модуля,
 *   - в плоской вкладке «Тумблеры модулей».
 *
 * Один источник правды о состоянии — modulesApi.modules (из useModules).
 *
 * props:
 *   moduleId    — id модуля из shared/modules_catalog.json
 *   moduleName  — название для модалки причины и тоста
 *   modulesApi  — объект из useModules(wsId)
 *   disabled    — внешний disabled (нет прав / нет workspace)
 */
export default function ModuleToggle({ moduleId, moduleName, modulesApi, disabled = false }) {
  const m = (modulesApi.modules || []).find((x) => x.id === moduleId);
  const checked = !!m?.is_enabled;

  const [showReason, setShowReason] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [toast, setToast] = useState(null);

  // Авто-скрытие тоста через 2.6 с
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  const flashToast = (text, kind = 'ok') => setToast({ text, kind, id: Date.now() });

  const handleChange = async (next) => {
    if (busy || disabled) return;
    setErr(null);
    if (next) {
      setBusy(true);
      try {
        await modulesApi.enable(moduleId);
        flashToast(`Функция «${moduleName || moduleId}» включена в боте`, 'ok');
      } catch (e) {
        setErr(e.message || 'Ошибка');
      } finally {
        setBusy(false);
      }
    } else {
      setShowReason(true);
    }
  };

  const confirmDisable = async (reason) => {
    setErr(null);
    try {
      await modulesApi.disable(moduleId, reason);
      setShowReason(false);
      flashToast(`Функция «${moduleName || moduleId}» выключена в боте`, 'warn');
    } catch (e) {
      setErr(e.message || 'Ошибка');
      throw e; // не закрываем модалку при ошибке
    }
  };

  return (
    <>
      <div className="inline-flex items-center gap-2">
        <Toggle
          checked={checked}
          onChange={handleChange}
          className={busy || disabled ? 'opacity-50 pointer-events-none' : ''}
        />
        {err && (
          <span className="text-[10px] text-danger font-bold">{err}</span>
        )}
      </div>

      {showReason && (
        <DisableReasonModal
          moduleName={moduleName || moduleId}
          onCancel={() => setShowReason(false)}
          onConfirm={confirmDisable}
        />
      )}

      {toast && createPortal(
        <div
          key={toast.id}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[400]
                     flex items-center gap-2.5 px-5 py-3 rounded-2xl
                     bg-sff text-tx border border-bd shadow-xl
                     animate-in slide-in-from-bottom-3 fade-in"
        >
          <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0
                            ${toast.kind === 'warn' ? 'bg-warn' : 'bg-ok'}`} />
          <span className="text-[12px] font-bold">{toast.text}</span>
        </div>,
        document.body,
      )}
    </>
  );
}
