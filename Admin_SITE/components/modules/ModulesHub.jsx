import { useState, useRef, useLayoutEffect } from 'react';
import {
  PieChart, Coins, Flame, HeartHandshake, Megaphone,
  ShieldAlert, ScrollText, Plus, ArrowRight, ArrowLeft, AlertTriangle,
  LogIn, LogOut, Image as ImageIcon, UserCog,
  MicOff, Mic, Ban, UserCheck, UserMinus, ShieldBan,
  ListChecks, UserCircle, Activity, Crown, Sparkles, ArrowUp, Gift, Trophy,
  MoonStar, ClipboardList, MoreHorizontal, Settings, BarChart3, Check,
  Rocket, Zap,
} from 'lucide-react';
import Button from '../shared/Button';

/**
 * ModulesHub — хаб «Модули» = КАТАЛОГ (IA_MODULES).
 *
 *  - Под-нав секций (бренд-линия) → грид карточек-модулей.
 *  - «Подключить» → модуль в боковой панели; «Отключить» → с причиной.
 *  - Модуль с `children` (напр. Статистика → Графики): клик открывает
 *    под-каталог графиков. Подключённые графики идут на СТРАНИЦУ
 *    «Статистика», НЕ в боковое меню (nav: null у children).
 *  - Модуль без готовой страницы (нет target/children) = «В разработке»
 *    + оранжевая точка «новый».
 *  - При подключении — тост-оповещение.
 *
 * Контролируемый: connected (Set id) / onConnect / onDisconnect / onOpen
 * из AdminDashboard (sidebar + localStorage). RBAC + энфорс — шаг #7.
 */

export const SECTIONS = [
  {
    id: 'analytics',
    name: 'Аналитика',
    modules: [
      { id: 'statistics', nav: 'statistics', target: 'statistics', icon: PieChart,
        name: 'Статистика и графики',
        desc: 'Лента графиков. Нажми, чтобы выбрать какие графики показывать.',
        children: [
          { id: 'chart:users',       wip: true, icon: BarChart3, name: 'Статистика по пользователям', desc: 'Новые / покинувшие / удалённые + всего.' },
          { id: 'chart:messages',    wip: true, icon: BarChart3, name: 'Количество сообщений по дням', desc: 'Сообщения и уникальные авторы.' },
          { id: 'chart:engagement',  wip: true, icon: BarChart3, name: 'Коэффициент вовлечённости',    desc: 'Доля пишущих от всех участников.' },
          { id: 'chart:active_hm',   wip: true, icon: BarChart3, name: 'Активные (heatmap)',           desc: 'Тепловая карта активности.' },
          { id: 'chart:msg_hm',      wip: true, icon: BarChart3, name: 'Сообщения (heatmap)',          desc: 'Тепловая карта объёма сообщений.' },
          { id: 'chart:newcomers',   wip: true, icon: BarChart3, name: 'Сводная новых по дням',        desc: 'Новые / вернувшиеся / приглашённые.' },
          { id: 'chart:first_msg',   wip: true, icon: BarChart3, name: 'Первое сообщение',             desc: 'В 1-й день / после 1-го дня.' },
          { id: 'chart:msg_stats',   wip: true, icon: BarChart3, name: 'Статистика по сообщениям',     desc: 'Всего / ответы / отредактированные.' },
          { id: 'chart:user_act',    wip: true, icon: BarChart3, name: 'Активность пользователей',     desc: 'MAU / реплаи / упоминания / ссылки.' },
          { id: 'chart:active_sum',  wip: true, icon: BarChart3, name: 'Сводная по активным',          desc: 'Новые / постоянные / активные.' },
          { id: 'chart:kpi',         wip: true, icon: BarChart3, name: 'Ряд mini-KPI',                 desc: '4 компактных показателя активности.' },
        ] },
      { id: 'top5', nav: null, target: null, icon: Trophy,
        name: 'Топ-5',
        desc: 'Рейтинги участников: топы по активности, сообщениям и пульсам.' },
    ],
  },
  {
    id: 'economy',
    name: 'Экономика',
    modules: [
      { id: 'economy', nav: 'economy', target: 'economy', icon: Coins,
        name: 'Экономика',
        desc: 'Базовая экономика: банк, пульсы, награды и санкции. Внутри — тематические модули.',
        children: [
          { id: 'eco:sprints', icon: Rocket, name: 'Спринты',
            desc: 'Краткосрочные челленджи на активность.' },
          { id: 'eco:combo',   icon: Zap,    name: 'Комбо',
            desc: 'Серии действий с нарастающим бонусом.' },
          { id: 'shipper', nav: 'shipper', target: 'shipper', icon: HeartHandshake,
            name: 'Шиппер',
            desc: 'Случайные пары участников. Лёгкий ice-breaker для чата.' },
        ] },
    ],
  },
  {
    id: 'engagement',
    name: 'Вовлечение',
    // nav: null у активностей/донатных — без под-пунктов в боковом меню.
    // paid: true → красная пометка «Донат».
    modules: [
      { id: 'donations', nav: null, target: null, icon: Gift,
        name: 'Донаты',
        desc: 'Система донатов: переводы и поддержка между участниками.' },
      { id: 'bbs_pulse', nav: null, target: null, icon: ClipboardList,
        name: 'Пульс ББС',
        desc: 'Доска знакомств: основная лента анкет участников.' },
      { id: 'bbs_other', nav: null, target: null, icon: MoreHorizontal,
        name: 'ББС Другое',
        desc: 'Дополнительные разделы и форматы доски знакомств.' },
      { id: 'bbs_edit', nav: null, target: null, icon: Settings,
        name: 'Редактирование анкет ББС',
        desc: 'Настройка и правка анкет в доске знакомств.' },
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
      { id: 'horoscope', nav: null, target: null, icon: MoonStar,
        name: 'Гороскоп',
        desc: 'Ежедневные гороскопы для участников чата.' },
    ],
  },
  {
    id: 'journal',
    name: 'Журнал',
    // Суб-модули = реальные категории фильтра страницы Журнал (logTags).
    // id = journal:<log.type>; все ведут в один nav 'journal'.
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
export const MODULE_NAV = SECTIONS.reduce((acc, s) => {
  s.modules.forEach(m => { if (m.nav) acc[m.id] = m.nav; });
  return acc;
}, {});

// Плоская карта id → имя (для тостов; включая children).
const NAME_BY_ID = {};
SECTIONS.forEach(s => s.modules.forEach(m => {
  NAME_BY_ID[m.id] = m.name;
  (m.children || []).forEach(c => { NAME_BY_ID[c.id] = c.name; });
}));

// «В разработке» = модуля ещё нет в коде бота — ЯВНЫЙ флаг `wip`.
// (Раньше был неверный эвристик по наличию страницы; почти всё в боте
//  уже есть — реально не готовы только виджеты-графики Статистики.)
const isWip = (mod) => !!mod.wip;

function ModuleCard({ mod, connected, onOpenModule, onOpen, onConnect, onDisconnect }) {
  const Icon = mod.icon;
  const wip = isWip(mod);
  const hasChildren = !!mod.children;
  // Клик по карточке: с под-каталогом → открыть его; иначе если
  // подключён и есть страница → перейти на неё.
  const cardClick = hasChildren
    ? () => onOpenModule(mod)
    : (connected && mod.target ? () => onOpen(mod.target) : undefined);

  return (
    <div
      onClick={cardClick}
      className={`relative h-full min-h-[210px] rounded-[1.75rem] border bg-sff p-5 flex flex-col gap-3 transition-all duration-200 ${
        cardClick
          ? 'border-bd hover:border-[color-mix(in_oklab,var(--cta)_45%,transparent)] hover:shadow-lg cursor-pointer'
          : 'border-bd'
      }`}
    >
      {/* лента-закладка «донат»: монетка, конец раздвоен как язык змеи */}
      {mod.paid && (
        <div className="absolute -top-px right-5 w-7 pointer-events-none z-10" title="Донатная функция">
          <div className="bg-amber-500 text-white flex items-center justify-center pt-1.5 pb-3 shadow-md"
            style={{ clipPath: 'polygon(0 0,100% 0,100% 100%,50% 72%,0 100%)' }}>
            <Coins size={12} />
          </div>
        </div>
      )}

      <div className="flex items-start justify-between gap-2">
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0 ${
          connected ? 'bg-cta text-white' : 'bg-sf2 text-txd'
        }`}>
          <Icon size={20} />
        </div>
        {wip ? (
          <span className="whitespace-nowrap text-[9px] font-black uppercase tracking-wide px-2.5 py-1 rounded-full bg-[color-mix(in_oklab,var(--warn)_14%,transparent)] text-warn border border-[color-mix(in_oklab,var(--warn)_38%,transparent)]">
            В разработке
          </span>
        ) : connected ? (
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[9px] font-black uppercase tracking-wide px-2.5 py-1 rounded-full bg-[color-mix(in_oklab,var(--ok)_8%,var(--sff))] text-tx border border-[color-mix(in_oklab,var(--ok)_26%,transparent)]">
            <span className="w-1.5 h-1.5 rounded-full bg-ok" />
            Подключён
          </span>
        ) : null}
      </div>

      <div className="flex-1">
        <h3 className="text-base font-black text-tx leading-tight line-clamp-2 min-h-[2.5rem]">{mod.name}</h3>
        <p className="text-[12px] text-txd mt-1.5 leading-snug line-clamp-2">{mod.desc}</p>
      </div>

      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
        {hasChildren && (
          <Button size="sm" variant={connected ? 'primary' : 'secondary'} icon={ArrowRight}
            className="flex-1" onClick={() => onOpenModule(mod)}>
            Открыть
          </Button>
        )}
        {connected ? (
          <Button size="sm" variant="secondary" className="flex-1"
            onClick={() => onDisconnect(mod)}>
            Отключить
          </Button>
        ) : (
          <Button size="sm" variant="primary" icon={hasChildren ? undefined : Plus}
            className="flex-1" onClick={() => onConnect(mod.id)}>
            Подключить
          </Button>
        )}
      </div>
    </div>
  );
}

export default function ModulesHub({ onOpen, connected, onConnect, onDisconnect }) {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [openMod, setOpenMod] = useState(null);   // открытый под-каталог
  const [disc, setDisc] = useState(null);         // модуль на отключении
  const [reason, setReason] = useState('');
  const [toast, setToast] = useState(null);

  const isOn = (id) => !!connected && connected.has(id);
  const section = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0];

  // FLIP-анимация перестановки: подключённые модули — наверх,
  // переезд плавный, но быстрый; освободившиеся места аккуратно
  // занимают неподключённые.
  const cardEls = useRef(new Map());
  const prevRects = useRef(new Map());
  useLayoutEffect(() => {
    const els = cardEls.current;
    els.forEach((el, id) => {
      if (!el) return;
      const nr = el.getBoundingClientRect();
      const or = prevRects.current.get(id);
      if (or) {
        const dx = or.left - nr.left;
        const dy = or.top - nr.top;
        if (dx || dy) {
          el.style.transition = 'none';
          el.style.transform = `translate(${dx}px, ${dy}px)`;
          el.getBoundingClientRect(); // reflow
          requestAnimationFrame(() => {
            el.style.transition = 'transform 280ms cubic-bezier(.22,1,.36,1)';
            el.style.transform = '';
          });
        }
      }
      prevRects.current.set(id, nr);
    });
    prevRects.current.forEach((_, id) => {
      if (!els.has(id)) prevRects.current.delete(id);
    });
  });

  const rootRef = useRef(null);
  const scrollToTop = () => {
    let el = rootRef.current?.parentElement;
    while (el && el.scrollHeight <= el.clientHeight + 4) el = el.parentElement;
    (el || window).scrollTo({ top: 0, behavior: 'smooth' });
  };

  const flash = (msg) => {
    setToast(msg);
    window.clearTimeout(flash._t);
    flash._t = window.setTimeout(() => setToast(null), 2800);
  };
  const handleConnect = (id) => {
    onConnect?.(id);
    flash(`Модуль «${NAME_BY_ID[id] || id}» подключён — функция включена`);
  };
  const confirmDisconnect = () => {
    if (!disc || !reason.trim()) return;
    // TODO(#7): причину — в журнал изменений модулей вместе со снятием тумблера.
    onDisconnect?.(disc.id);
    flash(`Модуль «${disc.name}» отключён`);
    setDisc(null);
    setReason('');
  };

  // Что показываем: под-каталог открытого модуля или секцию.
  const view = openMod
    ? { title: openMod.name, items: openMod.children, inChild: true }
    : { title: section.name, items: section.modules, inChild: false };

  return (
    <div ref={rootRef} className="space-y-6 pb-24">
      {/* ── Под-навигация секций (бренд-линия) ── */}
      <div className="border-b border-bd">
        <div className="flex gap-1 overflow-x-auto scrollbar-hide -mb-px">
          {SECTIONS.map(s => {
            const isActive = !openMod && s.id === section.id;
            return (
              <button
                key={s.id}
                onClick={() => { setOpenMod(null); setActiveSection(s.id); }}
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

      {/* ── Хлебные крошки под-каталога ── */}
      {openMod && (
        <div className="flex items-center gap-2 text-[12px] font-bold">
          <button onClick={() => setOpenMod(null)}
            className="flex items-center gap-1 text-cta hover:underline">
            <ArrowLeft size={14} /> Назад
          </button>
          <span className="text-lbl">/</span>
          <span className="text-tx">{openMod.name}</span>
        </div>
      )}

      {/* ── Каталог: подключённые наверх, FLIP-перестановка ── */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[...view.items]
          .sort((a, b) => (isOn(b.id) ? 1 : 0) - (isOn(a.id) ? 1 : 0))
          .map(m => (
          <div
            key={m.id}
            ref={el => { const mp = cardEls.current; el ? mp.set(m.id, el) : mp.delete(m.id); }}
            className="h-full"
            style={{ willChange: 'transform' }}
          >
            <ModuleCard
              mod={m}
              connected={isOn(m.id)}
              onOpenModule={(mm) => { setOpenMod(mm); scrollToTop(); }}
              onOpen={onOpen}
              onConnect={handleConnect}
              onDisconnect={setDisc}
            />
          </div>
        ))}
      </div>

      <p className="text-[12px] text-lbl text-center">
        {view.inChild
          ? (openMod?.id === 'statistics'
              ? 'Подключённые графики появляются на странице «Статистика» — не в боковом меню.'
              : `Подключённые суб-модули работают внутри «${openMod?.name}» — не в боковом меню.`)
          : `Каталог секции «${section.name}». Подключённые модули появляются в боковой панели.`}
      </p>

      {/* ── Модал отключения: причина обязательна ── */}
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

      {/* ── Тост-оповещение ── */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-sff text-tx border border-bd shadow-xl animate-in slide-in-from-bottom-3 fade-in">
          <span className="w-6 h-6 rounded-full bg-[color-mix(in_oklab,var(--ok)_16%,var(--sff))] text-ok flex items-center justify-center flex-shrink-0">
            <Check size={14} />
          </span>
          <span className="text-[12px] font-black">{toast}</span>
        </div>
      )}

      {/* Плавающая стрелка «наверх» */}
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
