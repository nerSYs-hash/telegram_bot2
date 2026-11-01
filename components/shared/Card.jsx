import { forwardRef } from 'react';

/**
 * Базовый компонент карточки дизайн-системы Pulse.
 *
 *   - bg-sff, rounded-2xl (16px), border-bd, shadow-sm — общий стиль секций.
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
// Токен-скин (§12.1). active = tint через color-mix (не битый Tailwind/alpha).
const ACCENTS = {
  blue: {
    glow:   '--card-glow-from:#60a5fa; --card-glow-via:#a855f7;  --card-glow-to:#60a5fa;',
    active: 'bg-[color-mix(in_oklab,var(--cta)_10%,transparent)] border-[color-mix(in_oklab,var(--cta)_45%,transparent)]',
  },
  emerald: {
    glow:   '--card-glow-from:#34d399; --card-glow-via:#32D74B;  --card-glow-to:#34d399;',
    active: 'bg-[color-mix(in_oklab,var(--ok)_10%,transparent)] border-[color-mix(in_oklab,var(--ok)_45%,transparent)]',
  },
  violet: {
    glow:   '--card-glow-from:#c084fc; --card-glow-via:#BF5AF2;  --card-glow-to:#c084fc;',
    active: 'bg-[color-mix(in_oklab,var(--purple)_10%,transparent)] border-[color-mix(in_oklab,var(--purple)_45%,transparent)]',
  },
  rose: {
    glow:   '--card-glow-from:#fb7185; --card-glow-via:#FF375F;  --card-glow-to:#fb7185;',
    active: 'bg-[color-mix(in_oklab,var(--pink)_10%,transparent)] border-[color-mix(in_oklab,var(--pink)_45%,transparent)]',
  },
  amber: {
    glow:   '--card-glow-from:#fbbf24; --card-glow-via:#FF9F0A;  --card-glow-to:#fbbf24;',
    active: 'bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border-[color-mix(in_oklab,var(--warn)_45%,transparent)]',
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
        'relative bg-sff rounded-2xl border shadow-sm transition-all',
        active ? a.active : 'border-bd',
        hoverable ? 'hover:shadow-md hover:border-bd2' : '',
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
