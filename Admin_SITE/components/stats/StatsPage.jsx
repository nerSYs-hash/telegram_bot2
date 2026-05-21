import { useState, useEffect, useCallback } from 'react';
import {
  ResponsiveContainer, ComposedChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import {
  Users, HelpCircle, Download, Clock, Loader2,
  BarChart3, Activity, Grid2x2, MessageSquare, UserPlus, Sparkles,
} from 'lucide-react';

// ── Палитра. Хекс, а не CSS-переменные: var() не резолвится в SVG-
//    атрибутах recharts (fill/stroke). Значения = токены index.css. ──
const C = {
  ok: '#32D74B', danger: '#FF453A', cta: '#0066CC', purple: '#BF5AF2',
  warn: '#FF9F0A', pink: '#FF375F', mint: '#66D4CF',
  grid: '#EDEFF3', axis: '#9CA3AF', axisDim: '#CBD2DA',
  tx: '#111318', txd: '#4B5563', pill: '#EAECEF',
};

const PERIODS = [
  { id: 'today',     label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера'   },
  { id: 'week',      label: 'Неделя'  },
  { id: 'month',     label: 'Месяц'   },
  { id: 'year',      label: 'Год'     },
];

// Кадэнс = как часто пересчитываются данные виджета (не диапазон графика).
const CADENCE = {
  hour:    'раз в час',
  halfday: '2 раза в день',
  day:     'раз в день',
};

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

// ── X-ось: активная дата в серой «плашке», едет за курсором. ──
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

// ── Карточка-обёртка виджета: иконка, заголовок, кадэнс, подсказка, CSV. ──
function WidgetCard({ icon: Icon, accent, title, hint, cadence = 'day', onExport, children }) {
  return (
    <section className="bg-sff rounded-[20px] border border-bd shadow-sm">
      <div className="flex items-center gap-3 px-5 pt-4 pb-2">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
             style={{ background: `${accent}1A` }}>
          <Icon size={17} style={{ color: accent }} />
        </div>
        <h3 className="text-[14px] font-bold text-tx flex-1 leading-tight">{title}</h3>
        <span className="hidden sm:flex items-center gap-1 text-[10px] font-semibold text-lbl
                          bg-sf2 px-2.5 py-1 rounded-full whitespace-nowrap">
          <Clock size={11} /> {CADENCE[cadence] || CADENCE.day}
        </span>
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

// ═══════════ Виджет №1 — Статистика по пользователям ═══════════
function WidgetUsers({ data, onExport }) {
  const [activeIndex, setActiveIndex] = useState(null);
  return (
    <WidgetCard
      icon={Users} accent={C.cta}
      title="Статистика по пользователям"
      hint="Вступили — присоединились за день. Вышли — покинули чат. Всего — общее число участников нарастающим итогом. Бейдж «раз в день» = частота пересчёта; график показывает все дни периода."
      cadence="day" onExport={onExport}
    >
      <ResponsiveContainer width="100%" height={264}>
        <ComposedChart data={data} margin={{ top: 10, right: 6, left: -14, bottom: 4 }}
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
               radius={[5, 5, 0, 0]} maxBarSize={20} animationDuration={500} />
          <Bar yAxisId="bars" dataKey="left" name="Вышли" fill={C.danger}
               radius={[5, 5, 0, 0]} maxBarSize={20} animationDuration={500} />
          <Line yAxisId="line" type="monotone" dataKey="total" name="Всего"
                stroke={C.cta} strokeWidth={2.5}
                dot={{ r: 3, fill: C.cta, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: C.cta, stroke: '#fff', strokeWidth: 2 }}
                animationDuration={650} />
        </ComposedChart>
      </ResponsiveContainer>
      <ChartLegend items={[
        { label: 'Вступили', color: C.ok },
        { label: 'Вышли',    color: C.danger },
        { label: 'Всего',    color: C.cta },
      ]} />
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

// ── CSV-выгрузка одного виджета (BOM для кириллицы в Excel). ──
function downloadCSV(filename, header, rows) {
  const lines = [header.join(';'), ...rows.map((r) => r.join(';'))];
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ═══════════════════════════ Страница ═══════════════════════════
export default function StatsPage() {
  const [period, setPeriod]   = useState('week');
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback((p) => {
    setLoading(true);
    fetch(`/api/stats/series?period=${p}`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setData(null); setLoading(false); });
  }, []);

  useEffect(() => { load('week'); }, [load]);

  const changePeriod = (p) => { setPeriod(p); load(p); };

  const users = data?.users || [];

  return (
    <div className="space-y-4 pb-24">
      {/* ── Шапка: период + Excel ── */}
      <div className="flex items-center gap-3">
        <div className="flex gap-2 overflow-x-auto flex-1 scrollbar-hide pt-1 pb-1">
          {PERIODS.map((p) => (
            <button key={p.id} onClick={() => changePeriod(p.id)}
              className={`flex-shrink-0 px-5 py-2.5 rounded-2xl font-black text-[11px]
                          uppercase tracking-wide transition-all duration-300 ${
                period === p.id
                  ? 'bg-cta text-white shadow-lg scale-105'
                  : 'bg-sff text-txd border border-bd'
              }`}>
              {p.label}
            </button>
          ))}
        </div>
        <button onClick={() => window.open(`/api/stats/export?period=${period}`, '_blank')}
          title="Выгрузить весь период в Excel"
          className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl
                     bg-sff border border-bd text-txd font-black text-[11px]
                     uppercase tracking-wide hover:border-ok hover:text-ok
                     transition-all duration-200">
          <Download size={15} className="text-ok" />
          <span className="hidden sm:inline">Excel</span>
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-28">
          <Loader2 size={40} className="animate-spin text-cta opacity-50" />
        </div>
      ) : !data ? (
        <div className="text-center py-28 text-sm text-lbl">
          Не удалось загрузить статистику. Попробуй обновить страницу.
        </div>
      ) : (
        <>
          {/* ── №1 — собран ── */}
          <WidgetUsers
            data={users}
            onExport={() => downloadCSV(
              `users_${period}.csv`,
              ['Дата', 'Вступили', 'Вышли', 'Всего'],
              users.map((u) => [u.day, u.joined, u.left, u.total]),
            )}
          />

          {/* ── №2–11 — проектируем по очереди ── */}
          <SoonCard icon={BarChart3}    title="Количество сообщений по дням"
            note="Следующий на очереди — собираем по одному." />
          <SoonCard icon={Activity}     title="Коэффициент вовлечённости"
            note="Доля пишущих от общего числа участников." />
          <SoonCard icon={Grid2x2}      title="Активные пользователи · теплокарта"
            note="Нужны почасовые данные — бэкенд этап 2." />
          <SoonCard icon={MessageSquare} title="Статистика по сообщениям"
            note="Всего / Комментариев / Ответов / Отредактированных." />
          <SoonCard icon={UserPlus}     title="Сводная новых по дням"
            note="Новые / Вернувшиеся / Приглашённые." />
          <SoonCard icon={Sparkles}     title="Ряд mini-KPI"
            note="4 компактных показателя за период." />
        </>
      )}
    </div>
  );
}
