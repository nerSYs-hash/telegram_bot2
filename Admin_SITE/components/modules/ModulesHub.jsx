import { useState, useRef } from 'react';
import {
  PieChart, Coins, Flame, HeartHandshake, Megaphone,
  ShieldAlert, ScrollText, Plus, ArrowRight, AlertTriangle,
  LogIn, LogOut, Image as ImageIcon, UserCog,
  MicOff, Mic, Ban, UserCheck, UserMinus, ShieldBan,
  ListChecks, UserCircle, Activity, Crown, Sparkles, ArrowUp,
} from 'lucide-react';
import Button from '../shared/Button';

/**
 * ModulesHub — хаб «Модули» = КАТАЛОГ (Шаг 2 IA_MODULES).
 *
 * Контракт: docs/IA_MODULES_Puls_Chat.md
 *  - Сверху под-навигация «underline · бренд-линия» (секции).
 *  - Клик по секции → грид ВСЕХ карточек-модулей (модули лежат тут,
 *    отсюда их и подключаешь — каталог).
 *  - «Подключить» на карточке → модуль появляется в боковой панели
 *    (раздел «Подключённые»). «Отключить» → исчезает, причина обязательна.
 *  - Журнал — не одна карточка, а отдельные СУБ-МОДУЛИ
 *    (вход/регистрация, выход, смена фото, …), каждый подключается сам.
 *    Все суб-модули Журнала ведут в один nav «journal»; в будущем —
 *    под-раздел внутри подключённого Журнала.
 *
 * Контролируемый: connected (Set id) / onConnect / onDisconnect / onOpen
 * приходят из AdminDashboard (он же держит sidebar + localStorage).
 * Реальная персистентность с RBAC — section_toggles, шаг #7.
 *
 * monetization-пометки сюда НЕ выводим — внутренняя оптика.
 */

export const SECTIONS = [
  {
    id: 'analytics',
    name: 'Аналитика',
    modules: [
      { id: 'statistics', nav: 'statistics', target: 'statistics', icon: PieChart,
        name: 'Статистика и графики',
        desc: 'Лента графиков: пользователи, сообщения, вовлечённость, активность.' },
    ],
  },
  {
    id: 'economy',
    name: 'Экономика',
    modules: [
      { id: 'economy', nav: 'economy', target: 'economy', icon: Coins,
        name: 'Экономика',
        desc: 'Пульсы, банк, награды и санкции. Тонкая настройка под чат.' },
    ],
  },
  {
    id: 'engagement',
    name: 'Вовлечение',
    // nav: null у активностей/донатных — без под-пунктов в боковом меню
    // (по требованию Ильи 19.05). paid: true → красная пометка «Донатный».
    modules: [
      { id: 'shipper', nav: 'shipper', target: 'shipper', icon: HeartHandshake,
        name: 'Шиппер',
        desc: 'Случайные пары участников. Лёгкий ice-breaker для чата.' },
      { id: 'vip_bbs', nav: null, target: null, icon: Sparkles, paid: true,
        name: 'VIP BBS',
        desc: 'Платная VIP-анкета в доске знакомств: эффекты и закреп.' },
      { id: 'titles', nav: null, target: null, icon: Crown, paid: true,
        name: 'Титулы',
        desc: 'Платные кастомные титулы участников. Донатная функция.' },
    ],
  },
  {
    id: 'content',
    name: 'Контент',
    modules: [
      { id: 'press_release', nav: 'press_release', target: 'press_release', icon: Megaphone,
        name: 'Пресс-релизы',
        desc: 'Анонсы и рассылки от лица чата с медиа и расписанием.' },
      { id: 'triggers', nav: 'triggers', target: 'triggers', icon: ShieldAlert,
        name: 'Триггеры',
        desc: 'Авто-реакции на слова и события. Нужен не всем чатам.' },
    ],
  },
  {
    id: 'journal',
    name: 'Журнал',
    // Суб-модули = реальные категории фильтра страницы Журнал (logTags).
    // id = journal:<log.type>; все ведут в один nav 'journal'.
    // Подключённые типы определяют, какие чипы/события видны на странице.
    modules: [
      { id: 'journal:trigger',   nav: 'journal', target: 'journal', icon: ShieldAlert,
        name: 'Триггеры',        desc: 'События срабатывания триггеров.' },
      { id: 'journal:mute',      nav: 'journal', target: 'journal', icon: MicOff,
        name: 'Муты',            desc: 'Выдачи мута участникам.' },
      { id: 'journal:unmute',    nav: 'journal', target: 'journal', icon: Mic,
        name: 'Размуты',         desc: 'Снятие мута с участников.' },
      { id: 'journal:ban',       nav: 'journal', target: 'journal', icon: Ban,
        name: 'Баны',            desc: 'Баны участников.' },
      { id: 'journal:unban',     nav: 'journal', target: 'journal', icon: UserCheck,
        name: 'Разбаны',         desc: 'Снятие бана.' },
      { id: 'journal:kick',      nav: 'journal', target: 'journal', icon: UserMinus,
        name: 'Исключения',      desc: 'Удаления (кик) из чата.' },
      { id: 'journal:warn',      nav: 'journal', target: 'journal', icon: AlertTriangle,
        name: 'Предупреждения',  desc: 'Выдачи предупреждений (варнов).' },
      { id: 'journal:join',      nav: 'journal', target: 'journal', icon: LogIn,
        name: 'Вход / Регистрация', desc: 'Входы в чат и регистрация новичков.' },
      { id: 'journal:leave',     nav: 'journal', target: 'journal', icon: LogOut,
        name: 'Выход',           desc: 'Выходы участников из чата.' },
      { id: 'journal:blacklist', nav: 'journal', target: 'journal', icon: ShieldBan,
        name: 'Блокировка',      desc: 'Чёрный список / блокировки.' },
      { id: 'journal:admin',     nav: 'journal', target: 'journal', icon: UserCog,
        name: 'Админ-действия',  desc: 'Действия администраторов.' },
      { id: 'journal:survey',    nav: 'journal', target: 'journal', icon: ListChecks,
        name: 'Опросы',          desc: 'Создание и итоги опросов.' },
      { id: 'journal:profile',   nav: 'journal', target: 'journal', icon: UserCircle,
        name: 'Профиль',         desc: 'Изменения профиля участников.' },
      { id: 'journal:activity',  nav: 'journal', target: 'journal', icon: Activity,
        name: 'Активность',      desc: 'События активности участников.' },
      { id: 'journal:photo',     nav: 'journal', target: 'journal', icon: ImageIcon,
        name: 'Смена фото',      desc: 'Смена аватара/фото профиля.' },
    ],
  },
];

// Карта: id карточки каталога → id раздела в боковой панели.
// AdminDashboard по ней решает, какие пункты показать в сайдбаре.
export const MODULE_NAV = SECTIONS.reduce((acc, s) => {
  s.modules.forEach(m => { if (m.nav) acc[m.id] = m.nav; });
  return acc;
}, {});

function StatusPill({ connected, soon }) {
  if (soon) {
    return (
      <span className="whitespace-nowrap text-[9px] font-black uppercase tracking-wide px-2.5 py-1 rounded-full bg-sf2 text-lbl border border-bd">
        Скоро
      </span>
    );
  }
  return (
    <span className={`whitespace-nowrap text-[9px] font-black uppercase tracking-wide px-2.5 py-1 rounded-full border ${
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
      } ${mod.soon ? 'opacity-60' : ''} ${
        mod.paid
          ? '!border-[color-mix(in_oklab,var(--danger)_55%,transparent)] ring-1 ring-[color-mix(in_oklab,var(--danger)_22%,transparent)]'
          : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center ${
          connected ? 'bg-cta text-white' : 'bg-sf2 text-txd'
        }`}>
          <Icon size={20} />
        </div>
        <div className="flex flex-nowrap items-center gap-1.5 flex-shrink-0">
          {mod.paid && (
            <span className="whitespace-nowrap text-[9px] font-black uppercase tracking-wide px-2.5 py-1 rounded-full bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger border border-[color-mix(in_oklab,var(--danger)_40%,transparent)]">
              Донат
            </span>
          )}
          <StatusPill connected={connected} soon={mod.soon} />
        </div>
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

export default function ModulesHub({ onOpen, connected, onConnect, onDisconnect }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [disc, setDisc] = useState(null); // модуль на отключении
  const [reason, setReason] = useState('');

  const isOn = (id) => !!connected && connected.has(id);
  const section = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0];

  // Плавающая стрелка «наверх»: плашка остаётся на месте (не sticky),
  // а быстро подняться можно этой кнопкой. Ищем ближайший
  // прокручиваемый родитель и скроллим его в 0.
  const rootRef = useRef(null);
  const scrollToTop = () => {
    let el = rootRef.current?.parentElement;
    while (el && el.scrollHeight <= el.clientHeight + 4) el = el.parentElement;
    (el || window).scrollTo({ top: 0, behavior: 'smooth' });
  };

  const confirmDisconnect = () => {
    if (!disc || !reason.trim()) return;
    // TODO(#7): причину — в API/журнал изменений модулей вместе со снятием тумблера.
    onDisconnect?.(disc.id);
    setDisc(null);
    setReason('');
  };

  return (
    <div ref={rootRef} className="space-y-6 pb-24">
      {/* ── Под-навигация: underline · бренд-линия (скрин 102042) ──
           sticky: при скролле остаётся закреплённой сверху, секции
           переключаются без подъёма наверх. ── */}
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
            connected={isOn(m.id)}
            onOpen={onOpen}
            onConnect={onConnect}
            onDisconnect={setDisc}
          />
        ))}
      </div>

      <p className="text-[12px] text-lbl text-center">
        Каталог секции «{section.name}». Подключённые модули появляются в боковой панели.
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

      {/* Плавающая стрелка «наверх» — всегда видна при скролле */}
      <button
        onClick={scrollToTop}
        title="Наверх"
        aria-label="Наверх"
        className="fixed bottom-6 right-6 z-40 w-11 h-11 rounded-full bg-cta text-white shadow-lg flex items-center justify-center hover:brightness-110 active:scale-95 transition-all"
      >
        <ArrowUp size={20} />
      </button>
    </div>
  );
}
