import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';

/**
 * Лёгкая всплывающая подсказка (V1.17.0h2c).
 *
 * Рендерится в портал document.body → не обрезается overflow-hidden
 * родителями (карточки Экономики имеют overflow-hidden / overflow-y-auto).
 * Светлая, минимально прозрачная, текст переносится в аккуратную
 * табличку — вместо «чёрной полоски» нативного title.
 *
 *   <Tooltip content="Пояснение…"><span>?</span></Tooltip>
 */
export default function Tooltip({ content, children, side = 'top', maxWidth = 260 }) {
  const [tip, setTip] = useState(null); // {x, y, place}
  const ref = useRef(null);

  const show = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    // Мало места сверху — переворачиваем подсказку вниз.
    const place = side === 'top' && r.top < 110 ? 'bottom' : side;
    setTip({
      x: r.left + r.width / 2,
      y: place === 'bottom' ? r.bottom + 8 : r.top - 8,
      place,
    });
  }, [side]);

  const hide = useCallback(() => setTip(null), []);

  return (
    <>
      <span
        ref={ref}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="inline-flex"
      >
        {children}
      </span>
      {tip && createPortal(
        <div
          role="tooltip"
          className="fixed z-[200] pointer-events-none px-3 py-2 rounded-xl border border-bd2
                     text-[11px] leading-relaxed text-txd font-medium
                     shadow-[0_10px_30px_-8px_rgba(15,23,42,0.25)]
                     animate-in fade-in duration-150"
          style={{
            left: tip.x,
            top: tip.y,
            maxWidth,
            background: 'color-mix(in oklab, var(--sff) 97%, transparent)',
            backdropFilter: 'blur(4px)',
            WebkitBackdropFilter: 'blur(4px)',
            transform: `translateX(-50%) ${tip.place === 'bottom' ? '' : 'translateY(-100%)'}`,
          }}
        >
          {content}
        </div>,
        document.body
      )}
    </>
  );
}
