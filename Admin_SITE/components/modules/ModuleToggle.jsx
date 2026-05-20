import { useState } from 'react';
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
 *   moduleName  — название для модалки причины
 *   modulesApi  — объект из useModules(wsId)
 *   disabled    — внешний disabled (нет прав / нет workspace)
 */
export default function ModuleToggle({ moduleId, moduleName, modulesApi, disabled = false }) {
  const m = (modulesApi.modules || []).find((x) => x.id === moduleId);
  const checked = !!m?.is_enabled;

  const [showReason, setShowReason] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleChange = async (next) => {
    if (busy || disabled) return;
    setErr(null);
    if (next) {
      setBusy(true);
      try {
        await modulesApi.enable(moduleId);
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
    </>
  );
}
