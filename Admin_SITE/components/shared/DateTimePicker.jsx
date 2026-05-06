import { useState, useMemo, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, X, Calendar, Clock } from 'lucide-react';

const MONTHS = [
  'Январь', 'Февраль', 'Март',    'Апрель', 'Май',    'Июнь',
  'Июль',   'Август',  'Сентябрь','Октябрь','Ноябрь', 'Декабрь',
];
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function pad(n) { return String(n).padStart(2, '0'); }

function parseValue(v) {
  if (!v) return null;
  const d = new Date(v);
  if (isNaN(d.getTime())) return null;
  return d;
}

function buildGrid(year, month /* 0-11 */) {
  const first = new Date(year, month, 1);
  const last  = new Date(year, month + 1, 0);
  const startOffset = (first.getDay() + 6) % 7;          // Пн = 0
  const totalDays = last.getDate();
  const cells = [];
  // prev tail
  const prevLast = new Date(year, month, 0).getDate();
  for (let i = startOffset - 1; i >= 0; i--) {
    cells.push({ d: prevLast - i, prevMonth: true });
  }
  for (let d = 1; d <= totalDays; d++) cells.push({ d, current: true });
  // next head — to fill 6 rows × 7 = 42
  while (cells.length < 42) cells.push({ d: cells.length - totalDays - startOffset + 1, nextMonth: true });
  return cells;
}

/**
 * DateTimePicker — компактный календарь+время.
 * props:
 *   value     — ISO string или Date
 *   onChange  — (isoString) => void
 *   minDate   — нельзя выбрать раньше (опц)
 *   className — wrapper class
 */
export default function DateTimePicker({ value, onChange, minDate = new Date(), className = '' }) {
  const initial = parseValue(value) || new Date();
  const [year, setYear]   = useState(initial.getFullYear());
  const [month, setMonth] = useState(initial.getMonth());
  const [selected, setSelected] = useState(parseValue(value));
  const [hh, setHh] = useState(selected ? pad(selected.getHours()) : '12');
  const [mm, setMm] = useState(selected ? pad(selected.getMinutes()) : '00');

  const cells = useMemo(() => buildGrid(year, month), [year, month]);
  const minDay = minDate ? new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate()) : null;

  // Когда меняется value снаружи — синхронизируем
  useEffect(() => {
    const v = parseValue(value);
    if (v) {
      setSelected(v);
      setYear(v.getFullYear());
      setMonth(v.getMonth());
      setHh(pad(v.getHours()));
      setMm(pad(v.getMinutes()));
    }
  }, [value]);

  const emit = (date, h, m) => {
    if (!date) return;
    const out = new Date(date);
    out.setHours(parseInt(h || '0', 10));
    out.setMinutes(parseInt(m || '0', 10));
    out.setSeconds(0);
    out.setMilliseconds(0);
    onChange?.(out.toISOString());
  };

  const handleDayClick = (cell) => {
    if (!cell.current) return;
    const d = new Date(year, month, cell.d);
    if (minDay && d < minDay) return;
    setSelected(d);
    emit(d, hh, mm);
  };

  const handleHhChange = (v) => {
    let n = v.replace(/\D/g, '').slice(0, 2);
    if (n && parseInt(n, 10) > 23) n = '23';
    setHh(n);
    if (selected) emit(selected, n, mm);
  };
  const handleMmChange = (v) => {
    let n = v.replace(/\D/g, '').slice(0, 2);
    if (n && parseInt(n, 10) > 59) n = '59';
    setMm(n);
    if (selected) emit(selected, hh, n);
  };

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  const yearOptions = useMemo(() => {
    const cur = new Date().getFullYear();
    return Array.from({ length: 11 }, (_, i) => cur - 1 + i);
  }, []);

  const isSelected = (cell) => selected && cell.current
    && selected.getFullYear() === year
    && selected.getMonth() === month
    && selected.getDate() === cell.d;

  const isDisabled = (cell) => {
    if (!cell.current) return true;
    if (!minDay) return false;
    return new Date(year, month, cell.d) < minDay;
  };

  const reset = () => {
    setSelected(null);
    onChange?.(null);
  };

  return (
    <div className={`bg-white rounded-2xl border-2 border-gray-100 p-4 ${className}`}>
      {/* Header: month/year */}
      <div className="flex items-center justify-between mb-3">
        <button onClick={prevMonth} className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center">
          <ChevronLeft size={16} className="text-gray-500" />
        </button>
        <div className="flex items-center gap-2">
          <select
            value={month}
            onChange={(e) => setMonth(parseInt(e.target.value, 10))}
            className="px-2 py-1 rounded-lg bg-gray-50 border border-gray-100 text-sm font-bold text-gray-700 focus:outline-none focus:border-blue-200"
          >
            {MONTHS.map((m, i) => <option key={m} value={i}>{m}</option>)}
          </select>
          <select
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value, 10))}
            className="px-2 py-1 rounded-lg bg-gray-50 border border-gray-100 text-sm font-bold text-gray-700 focus:outline-none focus:border-blue-200"
          >
            {yearOptions.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <button onClick={nextMonth} className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center">
          <ChevronRight size={16} className="text-gray-500" />
        </button>
      </div>

      {/* Weekdays */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAYS.map((w) => (
          <div key={w} className="text-center text-[10px] font-black uppercase tracking-widest text-gray-400 py-1">
            {w}
          </div>
        ))}
      </div>

      {/* Days grid */}
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, i) => {
          const dis = isDisabled(cell);
          const sel = isSelected(cell);
          return (
            <button
              key={i}
              onClick={() => handleDayClick(cell)}
              disabled={dis}
              className={[
                'h-9 rounded-full text-sm font-bold transition-all',
                cell.current ? '' : 'text-gray-300',
                sel ? 'bg-blue-500 text-white shadow-md shadow-blue-100'
                    : (dis ? 'cursor-not-allowed text-gray-200'
                           : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'),
              ].join(' ')}
            >
              {cell.d}
            </button>
          );
        })}
      </div>

      {/* Time */}
      <div className="mt-4 pt-3 border-t border-gray-100 flex items-center gap-2">
        <Clock size={14} className="text-gray-400" />
        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">МСК</span>
        <div className="ml-auto flex items-center gap-1">
          <input
            value={hh}
            onChange={(e) => handleHhChange(e.target.value)}
            placeholder="чч"
            className="w-12 text-center px-2 py-1.5 bg-gray-50 border border-gray-100 rounded-lg text-sm font-black focus:outline-none focus:border-blue-200"
          />
          <span className="font-black text-gray-400">:</span>
          <input
            value={mm}
            onChange={(e) => handleMmChange(e.target.value)}
            placeholder="мм"
            className="w-12 text-center px-2 py-1.5 bg-gray-50 border border-gray-100 rounded-lg text-sm font-black focus:outline-none focus:border-blue-200"
          />
        </div>
      </div>

      {/* Selected display + reset */}
      {selected && (
        <div className="mt-3 flex items-center justify-between bg-blue-50 rounded-xl px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-bold text-blue-700">
            <Calendar size={14} />
            {selected.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })}
            {' · '}
            {hh}:{mm}
          </div>
          <button onClick={reset} className="text-blue-400 hover:text-blue-600">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
