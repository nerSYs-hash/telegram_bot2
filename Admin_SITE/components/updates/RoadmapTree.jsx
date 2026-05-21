import React, { useState, useMemo } from 'react';
import { GitBranch, PartyPopper, Sparkles, Wrench } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════
//  ДРЕВО РАЗВИТИЯ ПРОЕКТА  ·  карта обновлений как вертикальная ветка
//  Раздел «Обновления» → не плоский список, а дерево: на общей
//  вертикальной ветке висят узлы-кружки, каждый = одна новость.
//  В покое пунктирное кольцо вокруг кружка медленно вращается; при
//  наведении пунктиры «сходятся» в сплошное кольцо и кружок
//  подсвечивается светом своего типа (анимации — в index.css).
//  Три категории новостей вверху можно включать/выключать.
// ═══════════════════════════════════════════════════════════════════

const TYPE_CFG = {
  new:     { label: 'Новое',      color: 'var(--ok)',   icon: PartyPopper },
  improve: { label: 'Улучшено',   color: 'var(--cta)',  icon: Sparkles },
  fix:     { label: 'Исправлено', color: 'var(--warn)', icon: Wrench },
};
const TYPE_ORDER = ['new', 'improve', 'fix'];

const TAG_CFG = {
  site:       { emoji: '🌐', label: 'Сайт',       cls: 'text-cta'    },
  statistics: { emoji: '📊', label: 'Статистика', cls: 'text-purple' },
  journal:    { emoji: '📋', label: 'Журнал',     cls: 'text-cta'    },
  triggers:   { emoji: '⚡', label: 'Триггеры',   cls: 'text-warn'   },
  bot:        { emoji: '🤖', label: 'Бот',        cls: 'text-txd'    },
};

// ── Узел-новость на ветке ──────────────────────────────────────────
function RoadmapItem({ item }) {
  const cfg = TYPE_CFG[item.type] || TYPE_CFG.improve;
  const Icon = cfg.icon;
  const tag  = TAG_CFG[item.tag];
  const [jiggle, setJiggle] = useState(false);

  return (
    <div className="roadmap-node group relative flex items-center gap-3 sm:gap-4"
         style={{ '--node-color': cfg.color }}>
      {/* кружок на вертикальной ветке */}
      <div className="w-16 flex-shrink-0 flex justify-center">
        <svg viewBox="0 0 40 40" className="roadmap-svg w-9 h-9 relative z-10">
          <g className="roadmap-ring">
            <circle className="roadmap-ring-circle" cx="20" cy="20" r="15"
                    fill="none" strokeWidth="2.2" strokeLinecap="round"
                    strokeDasharray="2.6 6.6" />
          </g>
          <circle className="roadmap-dot" cx="20" cy="20" r="5.5" />
        </svg>
      </div>

      {/* карточка новости */}
      <div className="roadmap-card flex-1 min-w-0 rounded-2xl border border-bd bg-sff p-3.5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest"
                style={{ color: cfg.color, background: `color-mix(in oklab, ${cfg.color} 12%, transparent)` }}>
            <Icon size={12} /> {cfg.label}
          </span>
          <p className="text-xs text-tx font-medium leading-relaxed flex-1 min-w-0">{item.text}</p>
          {tag && (
            <span
              onClick={() => setJiggle(true)}
              onAnimationEnd={() => setJiggle(false)}
              className={`flex-shrink-0 text-[9px] font-black px-2 py-1 rounded-full cursor-pointer select-none bg-sf2 hover:scale-110 transition-transform ${tag.cls} ${jiggle ? 'tag-jiggle' : ''}`}>
              {tag.emoji} {tag.label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Древо целиком ──────────────────────────────────────────────────
export default function RoadmapTree({ updates = [] }) {
  const [types, setTypes] = useState({ new: true, improve: true, fix: true });

  // Сколько новостей каждой категории — для бейджей-счётчиков фильтра.
  const counts = useMemo(() => {
    const c = { new: 0, improve: 0, fix: 0 };
    updates.forEach(u => u.items.forEach(it => { if (c[it.type] != null) c[it.type]++; }));
    return c;
  }, [updates]);

  // Версии с учётом фильтра; версия без видимых новостей выпадает целиком.
  const visible = useMemo(() =>
    updates
      .map(u => ({
        ...u,
        items: u.items
          .map((it, i) => ({ ...it, _i: i }))
          .filter(it => (it.type in TYPE_CFG) ? types[it.type] : true),
      }))
      .filter(u => u.items.length > 0),
    [updates, types]
  );

  const allOff = TYPE_ORDER.every(t => !types[t]);
  const toggle = (t) => setTypes(p => ({ ...p, [t]: !p[t] }));

  return (
    <div className="space-y-5 pb-24 animate-in fade-in duration-300">
      {/* шапка раздела */}
      <div className="bg-sff rounded-[2.5rem] p-6 border border-bd shadow-sm flex items-center gap-4">
        <div className="w-14 h-14 bg-cta rounded-[1.5rem] flex items-center justify-center shadow-lg flex-shrink-0">
          <GitBranch size={26} className="text-white" />
        </div>
        <div>
          <h2 className="font-black text-2xl text-tx leading-none">Древо развития проекта</h2>
          <p className="text-xs text-lbl font-bold mt-1.5">Каждый кружок на ветке — шаг в развитии бота и панели</p>
        </div>
      </div>

      {/* фильтр: три категории новостей */}
      <div className="flex flex-wrap gap-2">
        {TYPE_ORDER.map(t => {
          const cfg  = TYPE_CFG[t];
          const Icon = cfg.icon;
          const on   = types[t];
          return (
            <button key={t} onClick={() => toggle(t)}
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
                {counts[t]}
              </span>
            </button>
          );
        })}
      </div>

      {/* само дерево */}
      {allOff ? (
        <div className="bg-sff rounded-[2rem] p-10 border border-bd text-center">
          <p className="text-sm font-bold text-lbl">Выберите хотя бы одну категорию новостей</p>
        </div>
      ) : (
        <div className="relative">
          {/* общая вертикальная ветка */}
          <div className="absolute left-[31px] top-3 bottom-3 w-[2px] roadmap-branch" />

          {/* «мы здесь» — текущая точка */}
          <div className="relative flex items-center gap-3 sm:gap-4 pb-1">
            <div className="w-16 flex-shrink-0 flex justify-center">
              <span className="relative z-10 w-3.5 h-3.5 rounded-full bg-cta ring-4 ring-bg pulse-beat" />
            </div>
            <span className="text-[11px] font-black uppercase tracking-[0.15em] text-cta">Мы здесь · сегодня</span>
          </div>

          {/* версии-вехи и их новости */}
          {visible.map((upd, vi) => (
            <div key={`${upd.version}-${vi}`} className="space-y-2.5 pt-5 first:pt-3">
              {/* веха-версия */}
              <div className="relative flex items-center gap-3 sm:gap-4">
                <div className="w-16 flex-shrink-0 flex justify-center">
                  <div className="relative z-10 w-9 h-9 rounded-full bg-cta flex items-center justify-center shadow-md ring-4 ring-bg">
                    <GitBranch size={15} className="text-white" />
                  </div>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="bg-cta text-white text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full">{upd.version}</span>
                    <span className="text-[11px] text-lbl font-mono">{upd.date}</span>
                  </div>
                  <h3 className="font-black text-base text-tx mt-1 leading-snug">{upd.title}</h3>
                </div>
              </div>
              {/* новости версии */}
              <div className="space-y-2.5">
                {upd.items.map(it => (
                  <RoadmapItem key={`${upd.version}-${it._i}`} item={it} />
                ))}
              </div>
            </div>
          ))}

          {/* начало пути */}
          <div className="relative flex items-center gap-3 sm:gap-4 pt-5">
            <div className="w-16 flex-shrink-0 flex justify-center">
              <span className="relative z-10 w-2.5 h-2.5 rounded-full bg-bd2 ring-4 ring-bg" />
            </div>
            <span className="text-[11px] font-bold text-lbl">Начало пути</span>
          </div>
        </div>
      )}
    </div>
  );
}
