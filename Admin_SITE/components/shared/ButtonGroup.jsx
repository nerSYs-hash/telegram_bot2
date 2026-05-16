import { useRef, useLayoutEffect, useState } from 'react';

/**
 * Segmented control в стиле iOS / Material Tabs.
 * Активный сегмент подсвечивается белым с тенью и плавно «переезжает».
 *
 * props:
 *   value         — текущее значение
 *   options       — [{ value, label, icon? }]
 *   onChange(v)   — колбэк
 *   size          — 'sm' | 'md'
 *   block         — занимает всю ширину
 *   className     — доп. классы для контейнера
 */
export default function ButtonGroup({
  value,
  options = [],
  onChange,
  size = 'md',
  block = false,
  className = '',
}) {
  const wrapRef = useRef(null);
  const [pill, setPill] = useState({ x: 0, w: 0, ready: false });

  // Считаем позицию активного «пилюли»-индикатора
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const idx = options.findIndex(o => o.value === value);
    const btns = wrap.querySelectorAll('[data-bg-item]');
    const active = btns[idx];
    if (!active) { setPill(p => ({ ...p, ready: false })); return; }
    setPill({
      x: active.offsetLeft,
      w: active.offsetWidth,
      ready: true,
    });
  }, [value, options.length, options.map(o => o.value).join('|')]);

  const padCls = size === 'sm'
    ? 'p-0.5 text-[11px]'
    : 'p-1 text-xs';
  const itemPad = size === 'sm' ? 'px-2.5 py-1' : 'px-3 py-1.5';

  return (
    <div
      ref={wrapRef}
      className={`relative inline-flex items-center bg-gray-100 rounded-2xl ${padCls} ${block ? 'w-full' : ''} ${className}`}
    >
      {/* «Пилюля»-индикатор активного */}
      {pill.ready && (
        <div
          aria-hidden
          className="absolute top-1 bottom-1 bg-white rounded-xl shadow-sm transition-all duration-200 ease-out"
          style={{ left: pill.x, width: pill.w }}
        />
      )}
      {options.map(opt => {
        const active = opt.value === value;
        const Icon = opt.icon;
        return (
          <button
            key={String(opt.value)}
            data-bg-item
            type="button"
            onClick={() => onChange?.(opt.value)}
            className={`relative z-10 inline-flex items-center justify-center gap-1.5 ${itemPad} rounded-xl font-black transition-colors ${
              active ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
            } ${block ? 'flex-1' : ''}`}
          >
            {Icon && <Icon size={size === 'sm' ? 11 : 13} />}
            <span className="whitespace-nowrap">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
