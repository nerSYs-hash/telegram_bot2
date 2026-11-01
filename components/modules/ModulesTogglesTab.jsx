import { useMemo, useState } from 'react';

import ModuleToggle from './ModuleToggle';

/**
 * Вкладка «Тумблеры модулей» — плоский список всех модулей с тумблерами
 * в 2 колонки. Источник состояния — modulesApi.modules (из useModules).
 *
 * props:
 *   modulesApi — объект из useModules(wsId)
 */
export default function ModulesTogglesTab({ modulesApi }) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();

  const rows = useMemo(() => {
    const list = modulesApi.modules || [];
    if (!q) return list;
    return list.filter(m =>
      (m.name || '').toLowerCase().includes(q) ||
      (m.description || '').toLowerCase().includes(q)
    );
  }, [modulesApi.modules, q]);

  return (
    <div className="space-y-4 pb-24">
      {/* Заголовок + краткое объяснение */}
      <div>
        <h2 className="text-xl font-black text-tx">Тумблеры модулей</h2>
        <p className="text-sm text-txd mt-1 leading-relaxed">
          Главный выключатель для каждого модуля. Один и тот же тумблер
          доступен в карточке каталога и в верхнем «паспорте» модуля —
          три точки входа, одно состояние.
        </p>
      </div>

      {/* Поиск */}
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
        placeholder="Найти модуль…"
        className="w-full max-w-sm px-4 py-2.5 rounded-2xl bg-sff border border-bd text-sm
                   focus:outline-none focus:border-cta transition-colors"
      />

      {/* Grid в 2 колонки */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {rows.map(m => (
          <div key={m.id}
               className="bg-sff border border-bd rounded-3xl shadow-sm p-4 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="font-black text-tx leading-tight">{m.name}</div>
              {m.description && (
                <div className="text-sm text-txd truncate mt-0.5">{m.description}</div>
              )}
            </div>
            <ModuleToggle
              moduleId={m.id}
              moduleName={m.name}
              modulesApi={modulesApi}
            />
          </div>
        ))}

        {/* Empty states */}
        {modulesApi.loading && rows.length === 0 && !q && (
          <div className="col-span-full text-center text-txd py-12">
            Загрузка модулей…
          </div>
        )}
        {!modulesApi.loading && rows.length === 0 && q && (
          <div className="col-span-full text-center text-txd py-12">
            Ничего не найдено по запросу «{query}».{' '}
            <button onClick={() => setQuery('')} className="underline text-cta">
              сбросить
            </button>
          </div>
        )}
        {!modulesApi.loading && rows.length === 0 && !q && (
          <div className="col-span-full text-center text-txd py-12">
            Нет модулей. Возможно, не выбран чат-сообщество.
          </div>
        )}
      </div>
    </div>
  );
}
