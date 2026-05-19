import { useState } from 'react';
import {
  PieChart, Coins, Flame, HeartHandshake, Megaphone,
  ShieldAlert, ScrollText, Plus, ArrowRight, AlertTriangle,
} from 'lucide-react';
import Button from '../shared/Button';

/**
 * ModulesHub — хаб «Модули» = КАТАЛОГ (Шаг 2 IA_MODULES).
 *
 * Контракт: docs/IA_MODULES_Puls_Chat.md
 *  - Сверху под-навигация «underline · бренд-линия» (список секций).
 *  - Клик по секции → грид ВСЕХ карточек-модулей секции (каталог:
 *    модули тут лежат, отсюда их и подключаешь — не наоборот).
 *  - На каждой карточке прямо: «Подключить» / статус / «Отключить».
 *  - При ОТКЛЮЧЕНИИ — обязательна причина (единое правило, как в
 *    Экономике; «Функции бота» это нарушали).
 *
 * СКЕЛЕТ: статус подключения локальный (useState). Реальная
 * персистентность — section_toggles + RBAC (шаг #7).
 * `target` = id существующей вкладки; подключённая карточка
 * проваливает в текущую страницу секции (хаб полезен сразу).
 *
 * monetization-пометки сюда НЕ выводим — внутренняя оптика.
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

function ModuleCard({ mod, connected, onOpen, onConnect, onDisconnect }) {
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

      <div className="flex items-center justify-between pt-1" onClick={e => e.stopPropagation()}>
        {connected && mod.target ? (
          <span className="text-[11px] font-black uppercase tracking-wide text-cta flex items-center gap-1">
            Открыть <ArrowRight size={13} />
          </span>
        ) : <span />}

        {mod.soon ? (
          <span className="text-[11px] font-bold text-lbl">В разработке</span>
        ) : connected ? (
          <button
            onClick={() => onDisconnect(mod)}
            className="text-[11px] font-bold text-lbl hover:text-danger transition-colors"
          >
            Отключить
          </button>
        ) : (
          <Button size="sm" variant="primary" icon={Plus}
            onClick={() => onConnect(mod.id)}>
            Подключить
          </Button>
        )}
      </div>
    </div>
  );
}

export default function ModulesHub({ onOpen }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  // СКЕЛЕТ: локальный статус подключения. TODO(#7): section_toggles + RBAC.
  const [connected, setConnected] = useState({});
  const [disc, setDisc] = useState(null); // модуль на отключении
  const [reason, setReason] = useState('');

  const section = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0];

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

      {/* ── Каталог: все модули секции карточками, подключаешь отсюда ── */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {section.modules.map(m => (
          <ModuleCard
            key={m.id}
            mod={m}
            connected={!!connected[m.id]}
            onOpen={onOpen}
            onConnect={doConnect}
            onDisconnect={setDisc}
          />
        ))}
      </div>

      <p className="text-[12px] text-lbl text-center">
        Это каталог секции «{section.name}». Подключай модули прямо здесь — включённые появятся в работе.
      </p>

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
