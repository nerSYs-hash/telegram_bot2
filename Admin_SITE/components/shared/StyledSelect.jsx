import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';

/**
 * Кастомный селект в общей стилистике (rounded-xl, мягкая анимация).
 * Вместо системного <select>.
 *
 * props:
 *   value          — текущее значение
 *   options        — [{ value, label, hint? }]
 *   onChange(v)    — колбэк
 *   placeholder    — текст когда нет выбранного значения
 *   className      — доп. классы для триггер-кнопки
 *   align          — 'left' | 'right' (как раскрывается меню)
 *   size           — 'sm' | 'md' (плотность)
 */
export default function StyledSelect({
  value,
  options = [],
  onChange,
  placeholder = 'Выбрать…',
  className = '',
  align = 'left',
  size = 'md',
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const current = options.find(o => o.value === value);

  // Закрытие по клику вне
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('touchstart', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('touchstart', handler);
    };
  }, [open]);

  // Закрытие по Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const padCls = size === 'sm' ? 'px-2.5 py-1.5 text-[11px]' : 'px-3 py-2 text-xs';

  return (
    <div ref={wrapRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`${padCls} bg-gray-50 border border-gray-100 rounded-xl font-bold text-gray-700 hover:border-blue-200 focus:outline-none focus:border-blue-300 flex items-center gap-1.5 transition-all ${open ? 'border-blue-300 bg-white shadow-sm' : ''} ${className}`}
      >
        <span className="truncate">
          {current ? current.label : <span className="text-gray-400 font-normal">{placeholder}</span>}
        </span>
        <ChevronDown size={12} className={`text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className={`absolute z-50 mt-1.5 min-w-full bg-white border border-gray-100 rounded-xl shadow-xl py-1 origin-top animate-in fade-in zoom-in-95 slide-in-from-top-1 duration-150 ${align === 'right' ? 'right-0' : 'left-0'}`}
          style={{ minWidth: '100%' }}
        >
          {options.map(opt => {
            const active = opt.value === value;
            return (
              <button
                key={String(opt.value)}
                type="button"
                onClick={() => { onChange?.(opt.value); setOpen(false); }}
                className={`w-full px-3 py-2 text-left text-xs font-bold flex items-center gap-2 transition-colors ${active ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'}`}
              >
                <span className="flex-1 truncate">
                  {opt.label}
                  {opt.hint && <span className="ml-1.5 text-[10px] font-normal text-gray-400">{opt.hint}</span>}
                </span>
                {active && <Check size={12} className="text-blue-500 flex-shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
