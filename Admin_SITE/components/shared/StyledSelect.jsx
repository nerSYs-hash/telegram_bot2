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
        className={`${padCls} bg-sf2 border border-bd rounded-xl font-bold text-tx hover:border-bd2 focus:outline-none focus:border-cta flex items-center gap-1.5 transition-all ${open ? 'border-cta bg-sff shadow-sm' : ''} ${className}`}
      >
        <span className="truncate">
          {current ? current.label : <span className="text-lbl font-normal">{placeholder}</span>}
        </span>
        <ChevronDown size={12} className={`text-txd transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className={`absolute z-50 mt-1.5 min-w-full bg-sff border border-bd rounded-xl shadow-xl py-1 origin-top animate-in fade-in zoom-in-95 slide-in-from-top-1 duration-150 ${align === 'right' ? 'right-0' : 'left-0'}`}
          style={{ minWidth: '100%' }}
        >
          {options.map(opt => {
            const active = opt.value === value;
            return (
              <button
                key={String(opt.value)}
                type="button"
                onClick={() => { onChange?.(opt.value); setOpen(false); }}
                className={`w-full px-3 py-2 text-left text-xs font-bold flex items-center gap-2 transition-colors ${active ? 'bg-[color-mix(in_oklab,var(--cta)_14%,transparent)] text-cta' : 'text-tx hover:bg-ih'}`}
              >
                <span className="flex-1 truncate">
                  {opt.label}
                  {opt.hint && <span className="ml-1.5 text-[10px] font-normal text-lbl">{opt.hint}</span>}
                </span>
                {active && <Check size={12} className="text-cta flex-shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
