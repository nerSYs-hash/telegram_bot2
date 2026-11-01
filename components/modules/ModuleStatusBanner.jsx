import { useState } from 'react';

/**
 * Компактный статус-баннер сверху страницы раздела модуля.
 *
 * ON  → зелёная полоска «Функция включена в боте».
 * OFF → жёлтая с кнопкой «Включить» (мгновенно вкл, без модалки причины).
 *
 * Отключение — только из каталога «Модули» (с причиной). Здесь — индикатор
 * + быстрое включение, чтобы пользователь не ушёл искать каталог если
 * случайно зашёл в раздел выключенной функции.
 *
 * props:
 *   moduleId    — id из shared/modules_catalog.json
 *   moduleName  — название для текста
 *   modulesApi  — объект из useModules(wsId)
 */
export default function ModuleStatusBanner({ moduleId, moduleName, modulesApi }) {
  const m = (modulesApi.modules || []).find((x) => x.id === moduleId);
  const on = !!m?.is_enabled;
  const [busy, setBusy] = useState(false);

  const handleEnable = async () => {
    if (busy) return;
    setBusy(true);
    try { await modulesApi.enable(moduleId); }
    catch (e) { console.error('module.enable', e); }
    finally { setBusy(false); }
  };

  if (on) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-2 mb-4 rounded-2xl
                      bg-[color-mix(in_oklab,var(--ok)_8%,transparent)]
                      border border-[color-mix(in_oklab,var(--ok)_28%,transparent)]">
        <span className="w-2 h-2 rounded-full bg-ok flex-shrink-0" />
        <span className="text-[12px] font-bold text-tx">
          Функция «{moduleName}» включена в боте
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 mb-4 rounded-2xl
                    bg-[color-mix(in_oklab,var(--warn)_8%,transparent)]
                    border border-[color-mix(in_oklab,var(--warn)_30%,transparent)]">
      <span className="w-2 h-2 rounded-full bg-warn flex-shrink-0" />
      <span className="text-[12px] font-bold text-tx flex-1">
        Функция «{moduleName}» выключена в боте. Настройки можно править,
        но в чате ничего не сработает.
      </span>
      <button
        onClick={handleEnable}
        disabled={busy}
        className="px-3 py-1.5 rounded-xl bg-cta text-white text-[11px] font-black
                   uppercase tracking-wider hover:brightness-110 active:scale-95
                   transition disabled:opacity-50"
      >
        {busy ? '…' : 'Включить'}
      </button>
    </div>
  );
}
