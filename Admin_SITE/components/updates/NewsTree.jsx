import React, { useState, useMemo } from 'react';
import { Newspaper, Sparkles, Wrench, Gift, ChevronDown } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════
//  НОВОСТНОЙ РАЗДЕЛ  ·  дерево новостей по месяцам
//  На общей вертикальной ветке висят узлы-месяцы; каждый раскрывается
//  в список новостей. Узел — кружок с пунктирным кольцом: в покое
//  кольцо медленно вращается, при наведении пунктиры сходятся в
//  сплошное кольцо и кружок подсвечивается (анимации — в index.css).
//  Категории по смыслу: Новинка / Обновление / Акция — фильтр сверху.
//  Свежие новости (с прошлого визита) помечены красной меткой New.
// ═══════════════════════════════════════════════════════════════════

const CAT = {
  feature: { label: 'Новинка',    color: 'var(--ok)',     icon: Sparkles },
  update:  { label: 'Обновление', color: 'var(--cta)',    icon: Wrench },
  promo:   { label: 'Акция',      color: 'var(--purple)', icon: Gift },
};
const CAT_ORDER = ['feature', 'update', 'promo'];

const TAG = {
  site:       { emoji: '🌐', label: 'Сайт' },
  bot:        { emoji: '🤖', label: 'Бот' },
  statistics: { emoji: '📊', label: 'Статистика' },
  journal:    { emoji: '📋', label: 'Журнал' },
  triggers:   { emoji: '⚡', label: 'Триггеры' },
};

const MONTHS = {
  'января': 'Январь', 'февраля': 'Февраль', 'марта': 'Март', 'апреля': 'Апрель',
  'мая': 'Май', 'июня': 'Июнь', 'июля': 'Июль', 'августа': 'Август',
  'сентября': 'Сентябрь', 'октября': 'Октябрь', 'ноября': 'Ноябрь', 'декабря': 'Декабрь',
};

// старые записи на поле type → нормализуем в смысловую категорию
function catOf(it) {
  if (it.cat) return it.cat;
  return it.type === 'new' ? 'feature' : 'update';
}
function monthOf(date) {
  const p = String(date).trim().split(/\s+/);
  return `${MONTHS[p[1]] || p[1] || ''} ${p[2] || ''}`.trim();
}

// ── красная метка свежей новости ──
function NewBadge() {
  return (
    <span className="news-badge flex-shrink-0 text-[8px] font-black uppercase tracking-wider text-white bg-danger px-1.5 py-0.5 rounded-full">
      New
    </span>
  );
}

// ── одна новость внутри месяца ──
function NewsRow({ item }) {
  const cfg  = CAT[item.cat] || CAT.update;
  const Icon = cfg.icon;
  const tag  = TAG[item.tag];
  return (
    <div className="flex items-start gap-3 px-5 py-3.5">
      <span className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center"
            style={{ color: cfg.color, background: `color-mix(in oklab, ${cfg.color} 13%, transparent)` }}>
        <Icon size={15} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] text-tx font-medium leading-relaxed">{item.text}</p>
        <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
          <span className="text-[10px] font-black uppercase tracking-wide" style={{ color: cfg.color }}>
            {cfg.label}
          </span>
          <span className="text-[10px] text-lbl">·</span>
          <span className="text-[10px] font-mono text-lbl">{item.version}</span>
          {tag && (
            <span className="text-[10px] font-bold text-txd bg-sf2 px-1.5 py-0.5 rounded-full">
              {tag.emoji} {tag.label}
            </span>
          )}
          {item.fresh && <NewBadge />}
        </div>
      </div>
    </div>
  );
}

// ── узел-месяц на ветке ──
function MonthSection({ month, isOpen, onToggle }) {
  const fresh = month.items.some(it => it.fresh);
  const mix = useMemo(() => {
    const c = { feature: 0, update: 0, promo: 0 };
    month.items.forEach(it => { c[it.cat]++; });
    return c;
  }, [month]);

  return (
    <div className="roadmap-node group relative flex items-start" style={{ '--node-color': 'var(--cta)' }}>
      {/* кружок-узел в рейке */}
      <div className="w-[58px] flex-shrink-0 flex justify-center pt-5">
        <svg viewBox="0 0 40 40" className="roadmap-svg w-9 h-9 relative z-10">
          <g className="roadmap-ring">
            <circle className="roadmap-ring-circle" cx="20" cy="20" r="15"
                    fill="none" strokeWidth="2.2" strokeLinecap="round" strokeDasharray="2.6 6.6" />
          </g>
          <circle className="roadmap-dot" cx="20" cy="20" r="5.5" />
        </svg>
      </div>

      {/* карточка месяца */}
      <div className="roadmap-card flex-1 min-w-0 mb-3 rounded-[2.5rem] border border-bd bg-sff shadow-sm overflow-hidden">
        <button onClick={onToggle}
                className="w-full flex items-center gap-3 p-5 text-left hover:bg-ih transition-colors">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-black text-lg text-tx">{month.label}</h3>
              {fresh && <NewBadge />}
            </div>
            <p className="text-[11px] text-lbl font-bold mt-0.5">{month.items.length} новостей</p>
          </div>
          {/* мини-разбивка по категориям */}
          <div className="hidden sm:flex items-center gap-2.5 mr-1">
            {CAT_ORDER.filter(k => mix[k] > 0).map(k => (
              <span key={k} className="flex items-center gap-1 text-[11px] font-black"
                    style={{ color: CAT[k].color }}>
                <span className="w-2 h-2 rounded-full" style={{ background: CAT[k].color }} />
                {mix[k]}
              </span>
            ))}
          </div>
          <ChevronDown size={20}
            className={`text-txd transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="border-t border-bd divide-y divide-bd">
            {month.items.map(it => <NewsRow key={it._key} item={it} />)}
          </div>
        )}
      </div>
    </div>
  );
}

// ── дерево целиком ──
export default function NewsTree({ updates = [], baseline = null }) {
  const [cats, setCats] = useState({ feature: true, update: true, promo: true });

  // индекс свежести: всё новее baseline-версии — свежее
  const freshIdx = useMemo(() => {
    if (!baseline) return 0;
    const i = updates.findIndex(u => u.version === baseline);
    return i >= 0 ? i : 1;
  }, [updates, baseline]);

  // плоский список новостей, сгруппированный по месяцам (новые сверху)
  const allMonths = useMemo(() => {
    const map = new Map();
    updates.forEach((u, ui) => {
      const mk = monthOf(u.date);
      if (!map.has(mk)) map.set(mk, []);
      u.items.forEach((it, ii) => {
        map.get(mk).push({
          text: it.text,
          tag: it.tag,
          cat: catOf(it),
          version: u.version,
          fresh: ui < freshIdx,
          _key: `${u.version}-${ii}`,
        });
      });
    });
    return [...map.entries()].map(([label, items]) => ({ label, items }));
  }, [updates, freshIdx]);

  // счётчики по категориям (по всем новостям)
  const counts = useMemo(() => {
    const c = { feature: 0, update: 0, promo: 0 };
    allMonths.forEach(m => m.items.forEach(it => { c[it.cat]++; }));
    return c;
  }, [allMonths]);

  // месяцы с учётом фильтра категорий
  const months = useMemo(() =>
    allMonths
      .map(m => ({ ...m, items: m.items.filter(it => cats[it.cat]) }))
      .filter(m => m.items.length > 0),
    [allMonths, cats]
  );

  // раскрыты: новейший месяц + любой месяц со свежими новостями
  const [open, setOpen] = useState(() => {
    const s = new Set();
    if (allMonths[0]) s.add(allMonths[0].label);
    allMonths.forEach(m => { if (m.items.some(it => it.fresh)) s.add(m.label); });
    return s;
  });
  const toggle = (label) => setOpen(p => {
    const n = new Set(p);
    n.has(label) ? n.delete(label) : n.add(label);
    return n;
  });

  const allOff = CAT_ORDER.every(k => !cats[k]);
  const toggleCat = (k) => setCats(p => ({ ...p, [k]: !p[k] }));

  return (
    <div className="space-y-5 pb-24 animate-in fade-in duration-300">
      {/* шапка */}
      <div className="bg-sff rounded-[2.5rem] p-6 border border-bd shadow-sm flex items-center gap-4">
        <div className="w-14 h-14 bg-cta rounded-[1.5rem] flex items-center justify-center shadow-lg flex-shrink-0">
          <Newspaper size={26} className="text-white" />
        </div>
        <div>
          <h2 className="font-black text-2xl text-tx leading-none">Новости</h2>
          <p className="text-xs text-lbl font-bold mt-1.5">Что нового в боте и панели — по месяцам, свежее помечено меткой New</p>
        </div>
      </div>

      {/* фильтр категорий по смыслу */}
      <div className="flex flex-wrap gap-2">
        {CAT_ORDER.map(k => {
          const cfg  = CAT[k];
          const Icon = cfg.icon;
          const on   = cats[k];
          return (
            <button key={k} onClick={() => toggleCat(k)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-full border text-xs font-black transition-all active:scale-95 ${on ? '' : 'opacity-45'}`}
              style={on ? {
                color: cfg.color,
                background: `color-mix(in oklab, ${cfg.color} 12%, transparent)`,
                borderColor: `color-mix(in oklab, ${cfg.color} 35%, transparent)`,
              } : { color: 'var(--lbl)', background: 'var(--sf2)', borderColor: 'var(--bd)' }}>
              <Icon size={13} />
              {cfg.label}
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full"
                    style={{ background: on ? `color-mix(in oklab, ${cfg.color} 18%, transparent)` : 'var(--bg2)' }}>
                {counts[k]}
              </span>
            </button>
          );
        })}
      </div>

      {/* дерево */}
      {allOff || months.length === 0 ? (
        <div className="bg-sff rounded-[2rem] p-10 border border-bd text-center">
          <p className="text-sm font-bold text-lbl">
            {allOff ? 'Выберите хотя бы одну категорию' : 'Новостей в этой категории пока нет'}
          </p>
        </div>
      ) : (
        <div className="relative">
          {/* общая вертикальная ветка */}
          <div className="absolute left-[28px] top-3 bottom-3 w-[2px] roadmap-branch" />

          {/* «свежие новости» — текущая точка */}
          <div className="relative flex items-center gap-3 pb-1">
            <div className="w-[58px] flex-shrink-0 flex justify-center">
              <span className="relative z-10 w-3.5 h-3.5 rounded-full bg-cta ring-4 ring-bg pulse-beat" />
            </div>
            <span className="text-[11px] font-black uppercase tracking-[0.15em] text-cta">Свежие новости</span>
          </div>

          {months.map(m => (
            <MonthSection key={m.label} month={m}
                          isOpen={open.has(m.label)} onToggle={() => toggle(m.label)} />
          ))}

          {/* начало истории */}
          <div className="relative flex items-center gap-3 pt-2">
            <div className="w-[58px] flex-shrink-0 flex justify-center">
              <span className="relative z-10 w-2.5 h-2.5 rounded-full bg-bd2 ring-4 ring-bg" />
            </div>
            <span className="text-[11px] font-bold text-lbl">Начало истории проекта</span>
          </div>
        </div>
      )}
    </div>
  );
}
