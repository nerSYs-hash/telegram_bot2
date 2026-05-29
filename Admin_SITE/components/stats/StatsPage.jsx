import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ResponsiveContainer, ComposedChart, Area, Bar, Line, Brush,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell, LabelList,
} from 'recharts';
import {
  Users, HelpCircle, Download, Loader2, RefreshCw,
  BarChart3, Activity, Grid2x2, MessageSquare, UserPlus,
} from 'lucide-react';

// ── Палитра. Хекс, а не CSS-переменные: var() не резолвится в SVG-
//    атрибутах recharts (fill/stroke). Значения = токены index.css. ──
const C = {
  ok: '#32D74B', danger: '#FF453A', cta: '#0066CC', purple: '#BF5AF2',
  warn: '#FF9F0A', pink: '#FF375F', mint: '#66D4CF',
  grid: '#EDEFF3', axis: '#9CA3AF', axisDim: '#CBD2DA',
  tx: '#111318', txd: '#4B5563', pill: '#EAECEF', brush: '#F4F6F9',
};

// Градации — каждый виджет выбирает свою. Совпадают с бэкендом
// (/api/stats/series?granularity=…).
const GRANS = [
  { id: 'day',     label: 'День'    },
  { id: 'week',    label: 'Неделя'  },
  { id: 'month',   label: 'Месяц'   },
  { id: 'quarter', label: 'Квартал' },
  { id: 'year',    label: 'Год'     },
];

// ── Общая тултип-карточка. Образец — скрины Ильи 21.05:
//    белая, скруглённая, шапка-дата + строки «● Имя: Значение». ──
function StatTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-white rounded-2xl border border-bd shadow-lg px-4 py-3 min-w-[176px]">
      <div className="text-[12px] font-bold text-tx mb-2">{label}</div>
      <div className="space-y-1.5">
        {payload.map((p) => (
          <div key={p.dataKey} className="flex items-center justify-between gap-6">
            <span className="flex items-center gap-2 text-[12px] text-txd">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ background: p.color }} />
              {p.name}
            </span>
            <span className="text-[13px] font-bold text-tx tabular-nums">
              {typeof p.value === 'number'
                ? p.value.toLocaleString('ru-RU')
                : p.value}{p.unit || ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── X-ось: активная точка в серой «плашке», едет за курсором. ──
function DateTick({ x, y, payload, index, activeIndex }) {
  const label = String(payload?.value ?? '');
  const active = index === activeIndex;
  const w = label.length * 6.6 + 18;
  return (
    <g>
      {active && (
        <rect x={x - w / 2} y={y + 2} width={w} height={20} rx={9} fill={C.pill} />
      )}
      <text x={x} y={y + 16} textAnchor="middle"
            fontSize={11} fontWeight={active ? 700 : 600}
            fill={active ? C.txd : C.axis}>
        {label}
      </text>
    </g>
  );
}

// ── Переключатель градации (сегмент-контрол внутри виджета). ──
function GranTabs({ value, onChange }) {
  return (
    <div className="inline-flex gap-0.5 bg-sf2 rounded-xl p-1">
      {GRANS.map((g) => (
        <button key={g.id} onClick={() => onChange(g.id)}
          className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all duration-200 ${
            value === g.id
              ? 'bg-sff text-cta shadow-sm'
              : 'text-lbl hover:text-txd'
          }`}>
          {g.label}
        </button>
      ))}
    </div>
  );
}

// ── Карточка-обёртка виджета: иконка, заголовок, подсказка, CSV. ──
function WidgetCard({ icon: Icon, accent, title, hint, onExport, onRefresh, children }) {
  return (
    <section className="bg-sff rounded-[20px] border border-bd shadow-sm">
      <div className="flex items-center gap-3 px-5 pt-4 pb-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
             style={{ background: `${accent}1A` }}>
          <Icon size={17} style={{ color: accent }} />
        </div>
        <h3 className="text-[14px] font-bold text-tx flex-1 leading-tight">{title}</h3>
        {hint && (
          <div className="relative group/hint flex-shrink-0">
            <HelpCircle size={16} className="text-lbl cursor-help" />
            <div className="absolute right-0 top-7 w-64 text-[11px] leading-relaxed rounded-xl p-3
                            z-50 shadow-xl bg-white border border-bd text-txd
                            opacity-0 invisible translate-y-1
                            group-hover/hint:opacity-100 group-hover/hint:visible
                            group-hover/hint:translate-y-0 transition-all duration-150">
              {hint}
            </div>
          </div>
        )}
        {onRefresh && (
          <button onClick={onRefresh} title="Обновить эту карточку"
                  className="text-lbl hover:text-cta transition-colors flex-shrink-0">
            <RefreshCw size={15} />
          </button>
        )}
        {onExport && (
          <button onClick={onExport} title="Выгрузить CSV"
                  className="text-lbl hover:text-ok transition-colors flex-shrink-0">
            <Download size={16} />
          </button>
        )}
      </div>
      <div className="px-3 pb-4">{children}</div>
    </section>
  );
}

// ── Скрытые серии графика: персист в localStorage (не сбрасывается при
//    рефреше/перезагрузке; данные всё равно считаются, прячется только показ). ──
function useHiddenSeries(storeKey) {
  const lsKey = `stats_hidden_${storeKey}`;
  const [hidden, setHidden] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(lsKey) || '[]')); }
    catch { return new Set(); }
  });
  const toggle = useCallback((k) => {
    setHidden((prev) => {
      const n = new Set(prev);
      n.has(k) ? n.delete(k) : n.add(k);
      try { localStorage.setItem(lsKey, JSON.stringify([...n])); } catch { /* ignore */ }
      return n;
    });
  }, [lsKey]);
  return [hidden, toggle];
}

// ── Подпись-легенда под графиком. Кликабельная: клик по пункту прячет/
//    показывает серию (it.k = dataKey). Без onToggle — обычная подпись. ──
function ChartLegend({ items, hidden, onToggle }) {
  return (
    <div className="flex items-center justify-center flex-wrap gap-x-5 gap-y-1 pt-3">
      {items.map((it) => {
        const off = hidden && it.k && hidden.has(it.k);
        const clickable = !!(onToggle && it.k);
        return (
          <button key={it.label} type="button"
            onClick={clickable ? () => onToggle(it.k) : undefined}
            title={clickable ? 'Скрыть / показать на графике' : undefined}
            className={`flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full border transition-all duration-150 ${
              clickable ? 'cursor-pointer active:scale-95' : 'cursor-default'
            } ${off
              ? 'bg-sf2 border-bd text-lbl'
              : 'bg-sff border-bd text-txd hover:border-[color-mix(in_oklab,var(--cta)_40%,transparent)] hover:shadow-sm'
            }`}>
            <span className="w-2.5 h-2.5 rounded-full"
                  style={{ background: off ? '#C7CDD6' : it.color }} />
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Состояния виджета: загрузка / ошибка. ──
function WidgetState({ kind }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-20">
      {kind === 'loading'
        ? <Loader2 size={28} className="animate-spin text-cta opacity-50" />
        : <span className="text-[12px] text-lbl">Не удалось загрузить данные</span>}
    </div>
  );
}

// ── CSV-выгрузка одного виджета (BOM для кириллицы в Excel). ──
function downloadCSV(filename, header, rows) {
  const lines = [header.join(';'), ...rows.map((r) => r.join(';'))];
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ═══════════ Виджет №1 — Статистика по пользователям ═══════════
function WidgetUsers({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);
  const [hidden, toggleHidden] = useHiddenSeries('users');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.users || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={Users} accent={C.cta}
      title="Статистика по пользователям"
      onRefresh={() => refresh(gran)}
      hint="Вступили — присоединились за период. Вышли — покинули чат. Всего — общее число участников нарастающим итогом."
      onExport={data.length ? () => downloadCSV(
        `users_${gran}.csv`,
        ['Период', 'Вступили', 'Вышли', 'Всего'],
        data.map((u) => [u.day, u.joined, u.left, u.total]),
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 0 }}
              onMouseMove={(s) => setActiveIndex(s?.activeTooltipIndex ?? null)}
              onMouseLeave={() => setActiveIndex(null)}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" height={30} axisLine={false} tickLine={false}
                     interval="preserveStartEnd"
                     tick={<DateTick activeIndex={activeIndex} />} />
              <YAxis yAxisId="bars" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="line" orientation="right" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Tooltip content={<StatTooltip />}
                       cursor={{ stroke: C.axisDim, strokeWidth: 1.5, strokeDasharray: '4 4' }} />
              <Bar yAxisId="bars" dataKey="joined" name="Вступили" fill={C.ok}
                   hide={hidden.has('joined')}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="left" name="Вышли" fill={C.danger}
                   hide={hidden.has('left')}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Line yAxisId="line" type="monotone" dataKey="total" name="Всего"
                    hide={hidden.has('total')}
                    stroke={C.cta} strokeWidth={2.5}
                    dot={{ r: 3, fill: C.cta, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: C.cta, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={650} />
              <Brush dataKey="day" height={24} stroke={C.cta} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend hidden={hidden} onToggle={toggleHidden} items={[
            { k: 'joined', label: 'Вступили', color: C.ok },
            { k: 'left',   label: 'Вышли',    color: C.danger },
            { k: 'total',  label: 'Всего',    color: C.cta },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №2 — Количество сообщений ═══════════
function WidgetMessages({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);
  const [hidden, toggleHidden] = useHiddenSeries('messages');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.messages || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={BarChart3} accent={C.cta}
      title="Количество сообщений"
      onRefresh={() => refresh(gran)}
      hint="Сообщения — сколько всего написано за период. Писали — сколько уникальных участников отправили хотя бы одно сообщение. У показателей разный масштаб, поэтому две оси: сообщения слева, писали справа."
      onExport={data.length ? () => downloadCSV(
        `messages_${gran}.csv`,
        ['Период', 'Сообщения', 'Писали'],
        data.map((m) => [m.day, m.messages, m.writers]),
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 0 }}
              onMouseMove={(s) => setActiveIndex(s?.activeTooltipIndex ?? null)}
              onMouseLeave={() => setActiveIndex(null)}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" height={30} axisLine={false} tickLine={false}
                     interval="preserveStartEnd"
                     tick={<DateTick activeIndex={activeIndex} />} />
              <YAxis yAxisId="msg" width={40} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="wr" orientation="right" width={30} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Tooltip content={<StatTooltip />}
                       cursor={{ stroke: C.axisDim, strokeWidth: 1.5, strokeDasharray: '4 4' }} />
              <Bar yAxisId="msg" dataKey="messages" name="Сообщения" fill={C.cta}
                   hide={hidden.has('messages')}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Bar yAxisId="wr" dataKey="writers" name="Писали" fill={C.purple}
                   hide={hidden.has('writers')}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Brush dataKey="day" height={24} stroke={C.cta} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend hidden={hidden} onToggle={toggleHidden} items={[
            { k: 'messages', label: 'Сообщения', color: C.cta },
            { k: 'writers',  label: 'Писали',    color: C.purple },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №3 — Коэффициент вовлечённости ═══════════
function WidgetEngagement({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.engagement || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={Activity} accent={C.purple}
      title="Коэффициент вовлечённости"
      onRefresh={() => refresh(gran)}
      hint="Доля участников, написавших хотя бы одно сообщение за период, от общего числа участников чата. Чем выше — тем активнее живёт чат."
      onExport={data.length ? () => downloadCSV(
        `engagement_${gran}.csv`, ['Период', 'Вовлечённость, %'],
        data.map((e) => [e.day, e.pct]),
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 0 }}
              onMouseMove={(s) => setActiveIndex(s?.activeTooltipIndex ?? null)}
              onMouseLeave={() => setActiveIndex(null)}>
              <defs>
                <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={C.purple} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={C.purple} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" height={30} axisLine={false} tickLine={false}
                     interval="preserveStartEnd"
                     tick={<DateTick activeIndex={activeIndex} />} />
              <YAxis width={40} domain={[0, 'auto']} unit="%"
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Tooltip content={<StatTooltip />}
                       cursor={{ stroke: C.axisDim, strokeWidth: 1.5, strokeDasharray: '4 4' }} />
              <Area type="monotone" dataKey="pct" name="Вовлечённость" unit="%"
                    stroke={C.purple} strokeWidth={2.5} fill="url(#engGrad)"
                    dot={{ r: 3, fill: C.purple, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: C.purple, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={650} />
              <Brush dataKey="day" height={24} stroke={C.purple} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend items={[{ label: 'Вовлечённость', color: C.purple }]} />
        </>
      )}
    </WidgetCard>
  );
}

// ── Мини-спарклайн (CSS-столбики, без recharts). ──
function Spark({ values, color }) {
  if (!values || !values.length) return <div className="h-7" />;
  const max = Math.max(...values, 1);
  return (
    <div className="flex items-end gap-[2px] h-7">
      {values.map((v, i) => (
        <div key={i} className="flex-1 rounded-[2px] min-w-[1px]"
             style={{ height: `${Math.max(7, (v / max) * 100)}%`,
                      background: color, opacity: 0.5 }} />
      ))}
    </div>
  );
}

// ═══════════ Виджет №11 — Ряд mini-KPI ═══════════
function WidgetKpi({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const kpi = series?.kpi || {};
  const msgs = series?.messages || [];

  const tiles = [
    { icon: Users,         color: C.cta,    label: 'Активные участники',
      value: kpi.activeTotal,       spark: msgs.map((m) => m.writers) },
    { icon: MessageSquare, color: C.ok,     label: 'Всего сообщений',
      value: kpi.totalMsg,          spark: msgs.map((m) => m.messages) },
    { icon: BarChart3,     color: C.purple, label: 'Сообщений в среднем',
      value: kpi.avgMsgPerPoint,    spark: msgs.map((m) => m.messages) },
    { icon: Activity,      color: C.warn,   label: 'Активных в среднем',
      value: kpi.avgActivePerPoint, spark: msgs.map((m) => m.writers) },
  ];

  return (
    <section className="bg-sff rounded-[20px] border border-bd shadow-sm p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-[13px] font-bold text-tx px-1">Сводка</h3>
        <div className="flex items-center gap-2">
          <button onClick={() => refresh(gran)} title="Обновить"
                  className="text-lbl hover:text-cta transition-colors">
            <RefreshCw size={15} />
          </button>
          <GranTabs value={gran} onChange={setGran} />
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-2xl border border-bd bg-sf2 p-3.5">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                   style={{ background: `${t.color}1A` }}>
                <t.icon size={14} style={{ color: t.color }} />
              </div>
              <span className="text-[10px] font-bold text-lbl uppercase tracking-wide leading-tight">
                {t.label}
              </span>
            </div>
            <div className="text-2xl font-black text-tx tabular-nums mb-1.5">
              {(t.value ?? 0).toLocaleString('ru-RU')}
            </div>
            <Spark values={t.spark} color={t.color} />
          </div>
        ))}
      </div>
    </section>
  );
}

// ═══════════ Виджет №7 — Первое сообщение в чате ═══════════
// Снимок «за всё время» — от градации не зависит.
function WidgetFirstMessage({ cache, ensure, refresh }) {
  useEffect(() => { ensure('day'); }, [ensure]);

  const series = cache.day;
  const fm = series?.firstMessage;
  const loading = !series;
  const error = series?.error;

  const data = fm ? [
    { name: 'В первый день', value: fm.firstDay,      fill: C.ok },
    { name: 'Позже',         value: fm.afterFirstDay, fill: C.warn },
  ] : [];
  const total = fm ? fm.firstDay + fm.afterFirstDay : 0;
  const pct = total ? Math.round((fm.firstDay / total) * 100) : 0;

  return (
    <WidgetCard
      icon={MessageSquare} accent={C.ok}
      title="Первое сообщение в чате"
      onRefresh={() => refresh('day')}
      hint="Среди участников, которые хоть раз писали: сколько отправили первое сообщение в день вступления, а сколько — позже."
      onExport={fm ? () => downloadCSV(
        'first_message.csv', ['Когда', 'Участников'],
        [['В первый день', fm.firstDay], ['Позже', fm.afterFirstDay]],
      ) : undefined}
    >
      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={data} margin={{ top: 26, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="name" axisLine={false} tickLine={false}
                     tick={{ fontSize: 11, fontWeight: 600, fill: C.txd }} />
              <YAxis width={36} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={96} animationDuration={550}>
                {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
                <LabelList dataKey="value" position="top"
                           fill={C.tx} fontSize={13} fontWeight={800} />
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
          <div className="text-center text-[12px] text-txd pt-1">
            <span className="font-black text-tx">{pct}%</span> пишут в первый же день
          </div>
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №10 — Сводная по активным ═══════════
function WidgetActiveSummary({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const as = series?.activeSummary;
  const loading = !series;
  const error = series?.error;

  const data = as ? [
    { name: 'Новые',      value: as.newcomers, fill: C.danger },
    { name: 'Активные',   value: as.active,    fill: C.ok },
    { name: 'Постоянные', value: as.regular,   fill: C.warn },
  ] : [];

  return (
    <WidgetCard
      icon={Users} accent={C.cta}
      title="Сводная по активным"
      onRefresh={() => refresh(gran)}
      hint="Среди участников, активных за выбранный период: Новые — вступили за последние 14 дней; Активные — от 14 до 30 дней назад; Постоянные — больше 30 дней в чате."
      onExport={as ? () => downloadCSV(
        `active_summary_${gran}.csv`, ['Группа', 'Участников'],
        [['Новые', as.newcomers], ['Активные', as.active], ['Постоянные', as.regular]],
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={data} margin={{ top: 26, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="name" axisLine={false} tickLine={false}
                   tick={{ fontSize: 11, fontWeight: 600, fill: C.txd }} />
            <YAxis width={36} allowDecimals={false}
                   tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={84} animationDuration={550}>
              {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
              <LabelList dataKey="value" position="top"
                         fill={C.tx} fontSize={13} fontWeight={800} />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №6 — Новые и вернувшиеся ═══════════
function WidgetNewReturning({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('month');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const nr = series?.newReturning;
  const loading = !series;
  const error = series?.error;

  const data = nr ? [
    { name: 'Новые',       value: nr.new,       fill: C.ok },
    { name: 'Вернувшиеся', value: nr.returning, fill: C.cta },
  ] : [];

  return (
    <WidgetCard
      icon={UserPlus} accent={C.ok}
      title="Новые и вернувшиеся"
      onRefresh={() => refresh(gran)}
      hint="Новые — впервые вступили за период. Вернувшиеся — уходили и снова зашли. Данные копятся с момента включения: «вернувшиеся» появятся, когда участники начнут возвращаться."
      onExport={nr ? () => downloadCSV(
        `new_returning_${gran}.csv`, ['Группа', 'Участников'],
        [['Новые', nr.new], ['Вернувшиеся', nr.returning]],
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={data} margin={{ top: 26, right: 12, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="name" axisLine={false} tickLine={false}
                   tick={{ fontSize: 11, fontWeight: 600, fill: C.txd }} />
            <YAxis width={36} allowDecimals={false}
                   tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={84} animationDuration={550}>
              {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
              <LabelList dataKey="value" position="top"
                         fill={C.tx} fontSize={13} fontWeight={800} />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №8 — Статистика по сообщениям ═══════════
function WidgetMessageStats({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);
  const [hidden, toggleHidden] = useHiddenSeries('msg_stats');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.messageStats || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={MessageSquare} accent={C.mint}
      title="Статистика по сообщениям"
      onRefresh={() => refresh(gran)}
      hint="Всего — все сообщения за период (линия). Комментарии — сообщения в ветках/темах, либо комментарии под постами канала (считается по типу чата). Ответы — реплаи на чужие сообщения. Правки — отредактированные сообщения (копятся вперёд)."
      onExport={data.length ? () => downloadCSV(
        `message_stats_${gran}.csv`,
        ['Период', 'Всего', 'Комментарии', 'Ответы', 'Правки'],
        data.map((d) => [d.day, d.total, d.comments, d.replies, d.edited]),
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 0 }}
              onMouseMove={(s) => setActiveIndex(s?.activeTooltipIndex ?? null)}
              onMouseLeave={() => setActiveIndex(null)}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" height={30} axisLine={false} tickLine={false}
                     interval="preserveStartEnd"
                     tick={<DateTick activeIndex={activeIndex} />} />
              <YAxis yAxisId="bars" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="line" orientation="right" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Tooltip content={<StatTooltip />}
                       cursor={{ stroke: C.axisDim, strokeWidth: 1.5, strokeDasharray: '4 4' }} />
              <Bar yAxisId="bars" dataKey="comments" name="Комментарии" fill={C.cta}
                   hide={hidden.has('comments')}
                   radius={[5, 5, 0, 0]} maxBarSize={18} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="replies" name="Ответы" fill={C.purple}
                   hide={hidden.has('replies')}
                   radius={[5, 5, 0, 0]} maxBarSize={18} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="edited" name="Правки" fill={C.warn}
                   hide={hidden.has('edited')}
                   radius={[5, 5, 0, 0]} maxBarSize={18} animationDuration={500} />
              <Line yAxisId="line" type="monotone" dataKey="total" name="Всего"
                    hide={hidden.has('total')}
                    stroke={C.mint} strokeWidth={2.5}
                    dot={{ r: 3, fill: C.mint, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: C.mint, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={650} />
              <Brush dataKey="day" height={24} stroke={C.mint} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend hidden={hidden} onToggle={toggleHidden} items={[
            { k: 'comments', label: 'Комментарии', color: C.cta },
            { k: 'replies',  label: 'Ответы',      color: C.purple },
            { k: 'edited',   label: 'Правки',      color: C.warn },
            { k: 'total',    label: 'Всего',       color: C.mint },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №9 — Статистика активности пользователей ═══════════
function WidgetUserActivity({ cache, ensure, refresh }) {
  const [gran, setGran] = useState('week');  // 5 баров: день слишком плотный → по умолчанию неделя
  const [activeIndex, setActiveIndex] = useState(null);
  const [hidden, toggleHidden] = useHiddenSeries('user_act');

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.userActivity || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={Activity} accent={C.pink}
      title="Статистика активности пользователей"
      onRefresh={() => refresh(gran)}
      hint="Активные (линия) — уникальные авторы за период. Бары: Комментарии (в ветках/под постами), Ответы (реплаи), Правки, со Ссылкой, с Упоминанием. Правки/ссылки копятся вперёд."
      onExport={data.length ? () => downloadCSV(
        `user_activity_${gran}.csv`,
        ['Период', 'Активные', 'Комментарии', 'Ответы', 'Правки', 'Ссылки', 'Упоминания'],
        data.map((d) => [d.day, d.active, d.comments, d.replies, d.edited, d.links, d.mentions]),
      ) : undefined}
    >
      <div className="px-2 pb-1">
        <GranTabs value={gran} onChange={setGran} />
      </div>

      {loading ? <WidgetState kind="loading" />
        : error ? <WidgetState kind="error" />
        : (
        <>
          <ResponsiveContainer width="100%" height={290}>
            <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 0 }}
              onMouseMove={(s) => setActiveIndex(s?.activeTooltipIndex ?? null)}
              onMouseLeave={() => setActiveIndex(null)}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" height={30} axisLine={false} tickLine={false}
                     interval="preserveStartEnd"
                     tick={<DateTick activeIndex={activeIndex} />} />
              <YAxis yAxisId="bars" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="line" orientation="right" width={34} allowDecimals={false}
                     tick={{ fontSize: 10, fill: C.axisDim }} axisLine={false} tickLine={false} />
              <Tooltip content={<StatTooltip />}
                       cursor={{ stroke: C.axisDim, strokeWidth: 1.5, strokeDasharray: '4 4' }} />
              <Bar yAxisId="bars" dataKey="comments" name="Комментарии" fill={C.cta}
                   hide={hidden.has('comments')}
                   radius={[4, 4, 0, 0]} maxBarSize={30} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="replies" name="Ответы" fill={C.purple}
                   hide={hidden.has('replies')}
                   radius={[4, 4, 0, 0]} maxBarSize={30} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="edited" name="Правки" fill={C.warn}
                   hide={hidden.has('edited')}
                   radius={[4, 4, 0, 0]} maxBarSize={30} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="links" name="Ссылки" fill={C.mint}
                   hide={hidden.has('links')}
                   radius={[4, 4, 0, 0]} maxBarSize={30} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="mentions" name="Упоминания" fill={C.ok}
                   hide={hidden.has('mentions')}
                   radius={[4, 4, 0, 0]} maxBarSize={30} animationDuration={500} />
              <Line yAxisId="line" type="monotone" dataKey="active" name="Активные"
                    hide={hidden.has('active')}
                    stroke={C.pink} strokeWidth={2.5}
                    dot={{ r: 3, fill: C.pink, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: C.pink, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={650} />
              <Brush dataKey="day" height={24} stroke={C.pink} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend hidden={hidden} onToggle={toggleHidden} items={[
            { k: 'active',   label: 'Активные',   color: C.pink },
            { k: 'comments', label: 'Комментарии', color: C.cta },
            { k: 'replies',  label: 'Ответы',     color: C.purple },
            { k: 'edited',   label: 'Правки',     color: C.warn },
            { k: 'links',    label: 'Ссылки',     color: C.mint },
            { k: 'mentions', label: 'Упоминания', color: C.ok },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджеты №4/№5 — Теплокарты (день недели × час) ═══════════
const _WD_NAMES = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];  // index = strftime %w
const _WD_ORDER = [1, 2, 3, 4, 5, 6, 0];                        // показываем Пн-первым

function WidgetHeatmap({ metric, title, accent, hint }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [hover, setHover] = useState(null);  // {wd, h, v, x, y}

  const load = useCallback(() => {
    const token = localStorage.getItem('jwt') || '';
    const wsId = localStorage.getItem('active_ws_id');
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (wsId) headers['X-Workspace-Id'] = String(wsId);
    setError(false); setData(null);
    fetch('/api/stats/heatmap', { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError(true));
  }, []);
  useEffect(() => { load(); }, [load]);

  const grid = data && data[metric];               // 7×24 [wd][hour]
  const max = grid ? Math.max(1, ...grid.flat()) : 1;
  const metricLabel = metric === 'active' ? 'Активных' : 'Сообщений';
  const baseBg = (v) => v
    ? `color-mix(in oklab, ${accent} ${Math.round(10 + (v / max) * 80)}%, transparent)`
    : '#F1F3F7';

  return (
    <WidgetCard icon={Grid2x2} accent={accent} title={title} hint={hint} onRefresh={load}>
      {error ? <WidgetState kind="error" />
        : !grid ? <WidgetState kind="loading" />
        : (
        <div className="px-4 pb-3" onMouseLeave={() => setHover(null)}>
          {/* подписи часов */}
          <div className="flex gap-[3px] pl-12 mb-1.5">
            {Array.from({ length: 24 }).map((_, h) => (
              <div key={h} className="flex-1 text-[9px] text-lbl text-center">{h % 2 === 0 ? h : ''}</div>
            ))}
          </div>
          {_WD_ORDER.map((wd) => (
            <div key={wd} className="flex gap-[3px] items-center mb-[3px]">
              <div className="text-[11px] font-bold text-txd w-11 flex-shrink-0">{_WD_NAMES[wd]}</div>
              {Array.from({ length: 24 }).map((_, h) => {
                const v = grid[wd] ? grid[wd][h] : 0;
                const isHover = hover && hover.wd === wd && hover.h === h;
                return (
                  <div key={h}
                       onMouseMove={(e) => setHover({ wd, h, v, x: e.clientX, y: e.clientY })}
                       className="flex-1 rounded-md transition-all duration-150 cursor-pointer"
                       style={{
                         height: '30px',
                         background: isHover ? `color-mix(in oklab, ${baseBg(v)}, white 38%)` : baseBg(v),
                         transform: isHover ? 'scale(1.18)' : 'none',
                         boxShadow: isHover ? '0 4px 14px rgba(0,0,0,.18)' : 'none',
                         zIndex: isHover ? 5 : 1,
                       }} />
                );
              })}
            </div>
          ))}
          <div className="text-[11px] text-lbl pt-3 pl-12">Темнее клетка = выше активность · данные копятся вперёд</div>

          {/* Плавающая карточка-тултип в дизайне сайта, едет за курсором */}
          {hover && (
            <div className="fixed z-[300] pointer-events-none"
                 style={{ left: hover.x + 16, top: hover.y + 16 }}>
              <div className="bg-white rounded-2xl border border-bd shadow-xl px-3.5 py-2.5 min-w-[150px]">
                <div className="text-[12px] font-black text-tx mb-1.5">
                  {_WD_NAMES[hover.wd]}, {String(hover.h).padStart(2, '0')}:00
                </div>
                <div className="flex items-center justify-between gap-5">
                  <span className="flex items-center gap-2 text-[12px] text-txd">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: accent }} />
                    {metricLabel}
                  </span>
                  <span className="text-[13px] font-bold text-tx tabular-nums">
                    {hover.v.toLocaleString('ru-RU')}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </WidgetCard>
  );
}

// ── Заглушка «Скоро» для ещё не собранных виджетов. ──
function SoonCard({ icon: Icon, title }) {
  return (
    <section className="bg-sff rounded-[20px] border border-bd border-dashed shadow-sm
                        px-5 py-8 flex flex-col items-center text-center gap-2.5">
      <div className="w-10 h-10 rounded-xl bg-sf2 flex items-center justify-center">
        <Icon size={18} className="text-lbl" />
      </div>
      <h3 className="text-[13px] font-bold text-txd">{title}</h3>
      <span className="text-[10px] font-black text-lbl uppercase tracking-wide
                       bg-sf2 px-2.5 py-1 rounded-full">Скоро</span>
    </section>
  );
}

// ═══════════════════════════ Страница ═══════════════════════════
export default function StatsPage() {
  // Кеш серий по градациям: { day: {...}, week: {...}, ... }.
  // Виджеты независимы — каждый запрашивает свою градацию, попадание в
  // кеш переиспользуется между виджетами.
  const [cache, setCache] = useState({});
  const requested = useRef(new Set());

  const ensure = useCallback((gran) => {
    if (requested.current.has(gran)) return;
    requested.current.add(gran);
    // V1.17.0k14: Authorization + X-Workspace-Id — иначе бэк берёт
    // дефолт ws=1 (Pulse) и Switcher не работает для статистики.
    const token = localStorage.getItem('jwt') || '';
    const wsId = localStorage.getItem('active_ws_id');
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (wsId) headers['X-Workspace-Id'] = String(wsId);
    fetch(`/api/stats/series?granularity=${gran}`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => setCache((c) => ({ ...c, [gran]: d })))
      .catch(() => {
        requested.current.delete(gran);
        setCache((c) => ({ ...c, [gran]: { error: true } }));
      });
  }, []);

  // ↻ Обновить одну карточку: сбросить кеш её градации и перезапросить.
  const refresh = useCallback((gran) => {
    requested.current.delete(gran);
    setCache((c) => { const n = { ...c }; delete n[gran]; return n; });
    ensure(gran);
  }, [ensure]);

  return (
    <div className="space-y-4 pb-24">
      {/* ── Шапка ── */}
      <div className="flex items-center justify-between gap-3 pt-1">
        <h2 className="text-lg font-black text-tx">Статистика</h2>
        <button onClick={() => window.open('/api/stats/export?period=month', '_blank')}
          title="Выгрузить статистику за месяц в Excel"
          className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-sff border border-bd
                     text-txd font-black text-[11px] uppercase tracking-wide
                     hover:border-ok hover:text-ok transition-all duration-200">
          <Download size={15} className="text-ok" />
          <span className="hidden sm:inline">Excel</span>
        </button>
      </div>

      {/* ── №11 — сводка-плитки сверху ── */}
      <WidgetKpi cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №1 — собран ── */}
      <WidgetUsers cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №2 — собран ── */}
      <WidgetMessages cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №3 — собран ── */}
      <WidgetEngagement cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №7 — собран ── */}
      <WidgetFirstMessage cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №10 — собран ── */}
      <WidgetActiveSummary cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №6 — собран (новые/вернувшиеся, копится вперёд) ── */}
      <WidgetNewReturning cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №8 — собран (структура сообщений) ── */}
      <WidgetMessageStats cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №9 — собран (активность пользователей) ── */}
      <WidgetUserActivity cache={cache} ensure={ensure} refresh={refresh} />

      {/* ── №4 — Активные · теплокарта ── */}
      <WidgetHeatmap metric="active" accent={C.cta}
        title="Активные · теплокарта"
        hint="Когда участники активнее всего: день недели × час. Темнее клетка — больше уникальных писавших в этот час. Почасовые данные копятся вперёд." />

      {/* ── №5 — Сообщения · теплокарта ── */}
      <WidgetHeatmap metric="messages" accent={C.purple}
        title="Сообщения · теплокарта"
        hint="Объём сообщений по дням недели и часам. Темнее клетка — больше сообщений в этот час. Почасовые данные копятся вперёд." />
    </div>
  );
}
