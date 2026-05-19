import { useState } from 'react';
import {
  PieChart, Coins, Flame, HeartHandshake, Megaphone,
  ShieldAlert, ScrollText, Plus, ArrowRight, AlertTriangle, X,
} from 'lucide-react';
import Button from '../shared/Button';

/**
 * ModulesHub — каркас хаба «Модули» (Шаг 2 IA_MODULES).
 *
 * Контракт: docs/IA_MODULES_Puls_Chat.md
 *  - Сверху под-навигация «underline · бренд-линия» (список секций).
 *  - Клик по секции → грид карточек-модулей.
 *  - В каждой секции пунктирная кнопка «+ Подключить модуль» →
 *    инлайн-панель с доступными (ещё не подключёнными) модулями.
 *  - Единый механизм тумблеров. При ОТКЛЮЧЕНИИ — спрашиваем причину
 *    (единое правило, как в Экономике; «Функции бота» это нарушали).
 *
 * СКЕЛЕТ: статус модулей хранится локально (useState). Реальная
 * персистентность — через section_toggles (шаг #7, RBAC-aware).
 * `target` = id существующей вкладки; клик по подключённой карточке
 * проваливает в текущую страницу секции (хаб уже полезен сразу).
 *
 * monetization-пометки сюда НЕ выводим — это внутренняя оптика
 * (STATS_SPEC §Монетизация), пользователю не показываем.
 */

const SECTIONS = [
  {
    id: 'analytics',
    name: 'Аналитика',
    modules: [
      { id: 'statistics', target: 'statistics', icon: PieChart,
        name: 'Статистика и графики',
        desc: 'Лента графиков: пользователи, сообщения, вовлечённость, активность.' },
    ],
  },
  {
    id: 'economy',
    name: 'Экономика',
    modules: [
      { id: 'economy', target: 'economy', icon: Coins,
        name: 'Экономика',
        desc: 'Пульсы, банк, награды и санкции. Тонкая настройка под чат.' },
    ],
  },
  {
    id: 'engagement',
    name: 'Вовлечение',
    modules: [
      { id: 'activities', target: null, icon: Flame, soon: true,
        name: 'Активности',
        desc: 'Игры и события. Каждая активность — отдельный суб-модуль.' },
      { id: 'shipper', target: 'shipper', icon: HeartHandshake,
        name: 'Шиппер',
        desc: 'Случайные пары участников. Лёгкий ice-breaker для чата.' },
    ],
  },
  {
    id: 'content',
    name: 'Контент',
    modules: [
      { id: 'press_release', target: 'press_release', icon: Megaphone,
        name: 'Пресс-релизы',
        desc: 'Анонсы и рассылки от лица чата с медиа и расписанием.' },
      { id: 'triggers', target: 'triggers', icon: ShieldAlert,
        name: 'Триггеры',
        desc: 'Авто-реакции на слова и события. Нужен не всем чатам.' },
    ],
  },
  {
    id: 'journal',
    name: 'Журнал',
    modules: [
      { id: 'journal', target: 'journal', icon: ScrollText,
        name: 'Журнал',
        desc: 'Лог событий. Внутри владелец сам подключает суб-модули: вход/регистрация, выход, смена фото.' },
    ],
  },
];

function StatusPill({ connected, soon }) {
  if (soon) {
    return (
      <span className="text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full bg-sf2 text-lbl border border-bd">
        Скоро
      </span>
    );
  }
  return (
    <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border ${
      connected
        ? 'bg-[color-mix(in_oklab,var(--ok)_14%,transparent)] text-ok border-[color-mix(in_oklab,var(--ok)_35%,transparent)]'
        : 'bg-sf2 text-txd border-bd'
    }`}>
      {connected ? 'Подключён' : 'Не подключён'}
    </span>
  );
}

function ModuleCard({ mod, connected, onOpen, onDisconnect }) {
  const Icon = mod.icon;
  const clickable = connected && mod.target;
  return (
    <div
      onClick={clickable ? () => onOpen(mod.target) : undefined}
      className={`relative rounded-[1.75rem] border bg-sff p-5 flex flex-col gap-3 transition-all duration-200 ${
        clickable
          ? 'border-bd hover:border-[color-mix(in_oklab,var(--cta)_45%,transparent)] hover:shadow-lg cursor-pointer'
          : 'border-bd'
      } ${mod.soon ? 'opacity-60' : ''}`}
    >
      <div className="flex items-start justify-between">
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center ${
          connected ? 'bg-cta text-white' : 'bg-sf2 text-txd'
        }`}>
          <Icon size={20} />
        </div>
        <StatusPill connected={connected} soon={mod.soon} />
      </div>

      <div className="flex-1">
        <h3 className="text-base font-black text-tx leading-tight">{mod.name}</h3>
        <p className="text-[12px] text-txd mt-1.5 leading-snug">{mod.desc}</p>
      </div>

      {connected && (
        <div className="flex items-center justify-between pt-1">
          {mod.target ? (
            <span className="text-[11px] font-black uppercase tracking-wide text-cta flex items-center gap-1">
              Открыть <ArrowRight size={13} />
            </span>
          ) : <span />}
          <button
            onClick={(e) => { e.stopPropagation(); onDisconnect(mod); }}
            className="text-[11px] font-bold text-lbl hover:text-danger transition-colors"
          >
            Отключить
          </button>
        </div>
      )}
    </div>
  );
}

export default function ModulesHub({ onOpen }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  // СКЕЛЕТ: локальный статус подключения. TODO(#7): section_toggles + RBAC.
  const [connected, setConnected] = useState({});
  const [openCatalog, setOpenCatalog] = useState({}); // sectionId → bool
  const [disc, setDisc] = useState(null);             // модуль на отключении
  const [reason, setReason] = useState('');

  const section = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0];
  const sectionMods = section.modules;
  const connectedMods = sectionMods.filter(m => connected[m.id]);
  const availableMods = sectionMods.filter(m => !connected[m.id] && !m.soon);
  const soonMods = sectionMods.filter(m => m.soon && !connected[m.id]);
  const catalogOpen = !!openCatalog[section.id];

  const doConnect = (id) =>
    setConnected(prev => ({ ...prev, [id]: true }));

  const confirmDisconnect = () => {
    if (!disc || !reason.trim()) return;
    // TODO(#7): отправить причину в API вместе со снятием тумблера.
    setConnected(prev => ({ ...prev, [disc.id]: false }));
    setDisc(null);
    setReason('');
  };

  return (
    <div className="space-y-6 pb-24">
      {/* ── Под-навигация: underline · бренд-линия (скрин 102042) ── */}
      <div className="border-b border-bd">
        <div className="flex gap-1 overflow-x-auto scrollbar-hide -mb-px">
          {SECTIONS.map(s => {
            const isActive = s.id === section.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                className={`relative flex-shrink-0 px-5 py-3 text-sm font-black tracking-tight transition-colors ${
                  isActive ? 'text-cta' : 'text-txd hover:text-tx'
                }`}
              >
                {s.name}
                <span className={`absolute left-3 right-3 -bottom-px h-[3px] rounded-full transition-all duration-300 ${
                  isActive ? 'bg-cta opacity-100' : 'bg-transparent opacity-0'
                }`} />
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Грид карточек-модулей секции ── */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {connectedMods.map(m => (
          <ModuleCard key={m.id} mod={m} connected
            onOpen={onOpen} onDisconnect={setDisc} />
        ))}

        {soonMods.map(m => (
          <ModuleCard key={m.id} mod={m} connected={false}
            onOpen={onOpen} onDisconnect={setDisc} />
        ))}

        {/* Пунктирная плашка «+ Подключить модуль» */}
        {availableMods.length > 0 && (
          <button
            onClick={() => setOpenCatalog(p => ({ ...p, [section.id]: !p[section.id] }))}
            className="rounded-[1.75rem] border-2 border-dashed border-bd2 text-txd hover:border-cta hover:text-cta hover:bg-[color-mix(in_oklab,var(--cta)_6%,transparent)] transition-all duration-200 p-5 flex flex-col items-center justify-center gap-2 min-h-[160px]"
          >
            <Plus size={26} />
            <span className="text-sm font-black uppercase tracking-wide">Подключить модуль</span>
            <span className="text-[11px] font-bold opacity-70">
              Доступно: {availableMods.length}
            </span>
          </button>
        )}
      </div>

      {connectedMods.length === 0 && !catalogOpen && availableMods.length > 0 && (
        <p className="text-[12px] text-lbl text-center">
          В этой секции пока ничего не подключено. Нажми «Подключить модуль».
        </p>
      )}

      {/* ── Инлайн-каталог доступных модулей секции ── */}
      {catalogOpen && availableMods.length > 0 && (
        <div className="rounded-[1.75rem] border border-bd bg-sf2 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-black uppercase tracking-widest text-txd">
              Доступные модули · {section.name}
            </h4>
            <button onClick={() => setOpenCatalog(p => ({ ...p, [section.id]: false }))}
              className="text-txd hover:text-tx p-1">
              <X size={16} />
            </button>
          </div>
          {availableMods.map(m => {
            const Icon = m.icon;
            return (
              <div key={m.id}
                className="flex items-center gap-3 rounded-2xl bg-sff border border-bd p-3.5">
                <div className="w-10 h-10 rounded-xl bg-sf2 text-txd flex items-center justify-center flex-shrink-0">
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-black text-tx leading-tight">{m.name}</p>
                  <p className="text-[11px] text-txd mt-0.5 truncate">{m.desc}</p>
                </div>
                <Button size="sm" variant="primary" icon={Plus}
                  onClick={() => doConnect(m.id)}>
                  Подключить
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Модал отключения: причина обязательна (единое правило) ── */}
      {disc && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={() => { setDisc(null); setReason(''); }}>
          <div onClick={e => e.stopPropagation()}
            className="w-full max-w-md rounded-[1.75rem] bg-sff border border-bd shadow-2xl p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-2xl bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger flex items-center justify-center flex-shrink-0">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="text-base font-black text-tx">Отключить «{disc.name}»?</h3>
                <p className="text-[12px] text-txd mt-1">
                  Укажи причину — она попадёт в журнал изменений модулей.
                </p>
              </div>
            </div>
            <textarea
              value={reason}
              onChange={e => setReason(e.target.value)}
              rows={3}
              placeholder="Например: модуль не нужен этому чату"
              className="w-full rounded-2xl border border-bd bg-sf2 text-tx text-sm p-3 outline-none focus:border-cta resize-none"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm"
                onClick={() => { setDisc(null); setReason(''); }}>
                Отмена
              </Button>
              <Button variant="danger" size="sm" disabled={!reason.trim()}
                onClick={confirmDisconnect}>
                Отключить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
