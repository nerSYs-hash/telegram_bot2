import { forwardRef } from 'react';

/**
 * Базовый компонент карточки дизайн-системы Pulse.
 *
 *   - bg-white, rounded-2xl (16px), border-gray-100, shadow-sm — общий стиль секций.
 *   - hoverable: subtle lift (тень + цвет рамки) при наведении. Опц.
 *   - glow: вращающийся conic-gradient бордер на hover (Aceternity-style).
 *     Цвета через accent. Опц.
 *   - active: «выбранное» состояние — статичный бордер акцентного цвета +
 *     лёгкая заливка. Используется например для выделенного элемента списка.
 *
 * props:
 *   padding   — 'none' | 'sm' | 'md' | 'lg'    (по умолчанию 'md' = p-5)
 *   accent    — 'blue' | 'emerald' | 'violet' | 'rose' | 'amber'
 *   hoverable — bool
 *   glow      — bool   (Aceternity glow на hover)
 *   active    — bool   (статическая подсветка «выбран»)
 *   as        — кастомный тег (по умолчанию 'div')
 *   ...rest   — пропсы корневого элемента (включая onClick)
 */

const PADDING = {
  none: '',
  sm:   'p-3',
  md:   'p-5',
  lg:   'p-7',
};

// Тщательно перечисляем классы, чтобы Tailwind JIT их подхватил.
const ACCENTS = {
  blue: {
    glow:   '--card-glow-from:#60a5fa; --card-glow-via:#a855f7;  --card-glow-to:#60a5fa;',
    active: 'bg-blue-50/60 border-blue-200',
  },
  emerald: {
    glow:   '--card-glow-from:#34d399; --card-glow-via:#10b981;  --card-glow-to:#34d399;',
    active: 'bg-emerald-50/60 border-emerald-200',
  },
  violet: {
    glow:   '--card-glow-from:#a78bfa; --card-glow-via:#7c3aed;  --card-glow-to:#a78bfa;',
    active: 'bg-violet-50/60 border-violet-200',
  },
  rose: {
    glow:   '--card-glow-from:#fb7185; --card-glow-via:#f43f5e;  --card-glow-to:#fb7185;',
    active: 'bg-rose-50/60 border-rose-200',
  },
  amber: {
    glow:   '--card-glow-from:#fbbf24; --card-glow-via:#f59e0b;  --card-glow-to:#fbbf24;',
    active: 'bg-amber-50/60 border-amber-200',
  },
};

const Card = forwardRef(function Card({
  padding   = 'md',
  accent    = 'blue',
  hoverable = false,
  glow      = false,
  active    = false,
  as: Tag   = 'div',
  className = '',
  style     = {},
  children,
  ...rest
}, ref) {
  const a = ACCENTS[accent] || ACCENTS.blue;
  const accentVars = glow ? cssVarsFromString(a.glow) : {};

  return (
    <Tag
      ref={ref}
      style={{ ...accentVars, ...style }}
      className={[
        'relative bg-white rounded-2xl border shadow-sm transition-all',
        active ? a.active : 'border-gray-100',
        hoverable ? 'hover:shadow-md hover:border-gray-200' : '',
        glow ? 'pulse-card-glow' : '',
        PADDING[padding],
        className,
      ].filter(Boolean).join(' ')}
      {...rest}
    >
      {children}
    </Tag>
  );
});

function cssVarsFromString(s) {
  const out = {};
  s.split(';').forEach(pair => {
    const [k, v] = pair.split(':').map(x => x?.trim());
    if (k && v) out[k] = v;
  });
  return out;
}

export default Card;
