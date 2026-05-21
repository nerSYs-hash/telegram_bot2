import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ResponsiveContainer, ComposedChart, Bar, Line, Brush,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import {
  Users, HelpCircle, Download, Loader2,
  BarChart3, Activity, Grid2x2, MessageSquare, UserPlus, Sparkles,
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
                : p.value}
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
function WidgetCard({ icon: Icon, accent, title, hint, onExport, children }) {
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

// ── Подпись-легенда под графиком. ──
function ChartLegend({ items }) {
  return (
    <div className="flex items-center justify-center flex-wrap gap-x-5 gap-y-1 pt-3">
      {items.map((it) => (
        <span key={it.label}
              className="flex items-center gap-1.5 text-[11px] font-medium text-txd">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
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
function WidgetUsers({ cache, ensure }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.users || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={Users} accent={C.cta}
      title="Статистика по пользователям"
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
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Bar yAxisId="bars" dataKey="left" name="Вышли" fill={C.danger}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Line yAxisId="line" type="monotone" dataKey="total" name="Всего"
                    stroke={C.cta} strokeWidth={2.5}
                    dot={{ r: 3, fill: C.cta, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: C.cta, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={650} />
              <Brush dataKey="day" height={24} stroke={C.cta} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend items={[
            { label: 'Вступили', color: C.ok },
            { label: 'Вышли',    color: C.danger },
            { label: 'Всего',    color: C.cta },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ═══════════ Виджет №2 — Количество сообщений ═══════════
function WidgetMessages({ cache, ensure }) {
  const [gran, setGran] = useState('day');
  const [activeIndex, setActiveIndex] = useState(null);

  useEffect(() => { ensure(gran); }, [gran, ensure]);

  const series = cache[gran];
  const data = series?.messages || [];
  const loading = !series;
  const error = series?.error;

  return (
    <WidgetCard
      icon={BarChart3} accent={C.cta}
      title="Количество сообщений"
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
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Bar yAxisId="wr" dataKey="writers" name="Писали" fill={C.purple}
                   radius={[5, 5, 0, 0]} maxBarSize={22} animationDuration={500} />
              <Brush dataKey="day" height={24} stroke={C.cta} fill={C.brush}
                     travellerWidth={9} tickFormatter={() => ''} />
            </ComposedChart>
          </ResponsiveContainer>
          <ChartLegend items={[
            { label: 'Сообщения', color: C.cta },
            { label: 'Писали',    color: C.purple },
          ]} />
        </>
      )}
    </WidgetCard>
  );
}

// ── Заглушка «Скоро» для ещё не собранных виджетов. ──
function SoonCard({ icon: Icon, title, note }) {
  return (
    <section className="bg-sff rounded-[20px] border border-bd border-dashed shadow-sm
                        px-5 py-8 flex flex-col items-center text-center gap-2">
      <div className="w-10 h-10 rounded-xl bg-sf2 flex items-center justify-center">
        <Icon size={18} className="text-lbl" />
      </div>
      <h3 className="text-[13px] font-bold text-txd">{title}</h3>
      <span className="text-[11px] text-lbl max-w-[300px] leading-relaxed">{note}</span>
      <span className="text-[10px] font-black text-lbl uppercase tracking-wide
                       bg-sf2 px-2.5 py-1 rounded-full mt-1">Скоро</span>
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
    fetch(`/api/stats/series?granularity=${gran}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => setCache((c) => ({ ...c, [gran]: d })))
      .catch(() => {
        requested.current.delete(gran);
        setCache((c) => ({ ...c, [gran]: { error: true } }));
      });
  }, []);

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

      {/* ── №1 — собран ── */}
      <WidgetUsers cache={cache} ensure={ensure} />

      {/* ── №2 — собран ── */}
      <WidgetMessages cache={cache} ensure={ensure} />

      {/* ── №3–11 — проектируем по очереди ── */}
      <SoonCard icon={Activity} title="Коэффициент вовлечённости"
        note="Доля пишущих от общего числа участников." />
      <SoonCard icon={Grid2x2} title="Активные пользователи · теплокарта"
        note="Нужны почасовые данные — бэкенд этап 2." />
      <SoonCard icon={MessageSquare} title="Статистика по сообщениям"
        note="Всего / Комментариев / Ответов / Отредактированных." />
      <SoonCard icon={UserPlus} title="Сводная новых по дням"
        note="Новые / Вернувшиеся / Приглашённые." />
      <SoonCard icon={Sparkles} title="Ряд mini-KPI"
        note="4 компактных показателя за период." />
    </div>
  );
}
