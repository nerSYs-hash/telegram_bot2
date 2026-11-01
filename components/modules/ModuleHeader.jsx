import ModuleToggle from './ModuleToggle';

/**
 * Единый «паспорт» модуля. Используется в верху экрана каждого подключённого
 * модуля (Триггеры/Гороскоп/ПР/Шиппер, etc.) — даёт пользователю единую
 * точку контекста: что это, описание, и тумблер ON/OFF.
 *
 * props:
 *   moduleId    — id модуля из shared/modules_catalog.json
 *   icon        — Lucide-компонент иконки
 *   name        — название модуля (видимое)
 *   description — короткое описание (опционально)
 *   modulesApi  — объект из useModules(wsId)
 *   canToggle   — можно ли переключать (по умолчанию true)
 */
export default function ModuleHeader({
  moduleId,
  icon: Icon,
  name,
  description,
  modulesApi,
  canToggle = true,
}) {
  return (
    <div className="bg-sff border border-bd rounded-3xl shadow-sm p-4 flex items-center gap-4 mb-4">
      {Icon && (
        <div className="w-10 h-10 rounded-2xl bg-sf2 flex items-center justify-center flex-shrink-0">
          <Icon size={20} className="text-txd" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="font-black text-tx leading-tight">{name}</div>
        {description && (
          <div className="text-sm text-txd truncate mt-0.5">{description}</div>
        )}
      </div>
      <ModuleToggle
        moduleId={moduleId}
        moduleName={name}
        modulesApi={modulesApi}
        disabled={!canToggle}
      />
    </div>
  );
}
