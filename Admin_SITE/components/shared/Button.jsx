import { forwardRef } from 'react';
import { Loader2, Check } from 'lucide-react';

/**
 * Универсальная кнопка дизайн-системы Pulse.
 *
 *   - Радиус rounded-2xl (16px) — общий канон.
 *   - Hover: вращающийся conic-gradient бордер (Aceternity-style).
 *     Через CSS-переменные --glow-from/--glow-via/--glow-to цвета подбираются
 *     по варианту. Класс .pulse-btn-glow — в index.css.
 *   - state="loading" → спиннер слева, текст «…» (опц.)
 *   - state="done"    → галочка с pop-анимацией (1.5с показывается, потом
 *                       компонент-родитель сам должен сбросить state).
 *
 * props:
 *   variant  — 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
 *   size     — 'sm' | 'md' | 'lg'
 *   state    — 'idle'    | 'loading' | 'done'
 *   icon     — Lucide-компонент иконки слева (опц.)
 *   loadingLabel — текст в loading-состоянии (по умолчанию: текущий children)
 *   doneLabel    — текст в done-состоянии    (по умолчанию: '' — только галочка)
 *   glow         — bool, включить glow-бордер (по умолч. true для primary/danger/success)
 *   block        — занимает всю ширину
 *   className    — доп. классы
 *   ...rest      — обычные props button
 */

// Токен-скин (§12.1: API/логика те же, меняется только визуал).
// glow-строки кормят канон v2 (.pulse-btn-glow в index.css) — бренд-цвета.
const VARIANTS = {
  primary: {
    base:  'bg-cta text-white hover:brightness-110',
    glow:  '--glow-from:#3b82f6; --glow-via:#a855f7; --glow-to:#3b82f6;',
    glowDefault: true,
  },
  secondary: {
    base:  'bg-sf2 text-tx border border-bd hover:bg-ih hover:border-bd2',
    glow:  '',
    glowDefault: false,
  },
  ghost: {
    base:  'bg-transparent text-txd hover:bg-ih hover:text-tx',
    glow:  '',
    glowDefault: false,
  },
  outlined: {
    base:  'bg-transparent text-cta border-[1.5px] border-[color-mix(in_oklab,var(--cta)_40%,transparent)] hover:border-cta hover:bg-[color-mix(in_oklab,var(--cta)_10%,transparent)]',
    glow:  '',
    glowDefault: false,
  },
  danger: {
    base:  'bg-danger text-white hover:brightness-110',
    glow:  '--glow-from:#fb7185; --glow-via:#FF453A; --glow-to:#fb7185;',
    glowDefault: true,
  },
  success: {
    base:  'bg-ok text-white hover:brightness-110',
    glow:  '--glow-from:#34d399; --glow-via:#32D74B; --glow-to:#34d399;',
    glowDefault: true,
  },
  // text-only — для inline-действий, ссылок-заглушек
  link: {
    base:  'bg-transparent text-cta hover:underline px-0 py-0',
    glow:  '',
    glowDefault: false,
  },
};

// padded — обычные кнопки с текстом, iconOnly — квадратные с одной иконкой
const SIZES = {
  sm: { padded: 'px-3 py-1.5 text-xs   gap-1.5', iconOnly: 'p-1.5 text-xs',   leading: 'leading-none' },
  md: { padded: 'px-4 py-2.5 text-sm   gap-2',   iconOnly: 'p-2.5 text-sm',   leading: 'leading-none' },
  lg: { padded: 'px-6 py-3   text-base gap-2',   iconOnly: 'p-3   text-base', leading: 'leading-none' },
};

const ICON_SIZE = { sm: 14, md: 16, lg: 18 };

const Button = forwardRef(function Button({
  variant     = 'primary',
  size        = 'md',
  state       = 'idle',
  icon: Icon,
  loadingLabel,
  doneLabel,
  glow,
  block       = false,
  disabled    = false,
  className   = '',
  children,
  ...rest
}, ref) {
  const v = VARIANTS[variant] || VARIANTS.primary;
  const useGlow = glow ?? v.glowDefault;
  const isLoading = state === 'loading';
  const isDone    = state === 'done';
  const iconSize  = ICON_SIZE[size] || 16;
  const sizeCfg   = SIZES[size] || SIZES.md;

  const label = isLoading
    ? (loadingLabel ?? children)
    : isDone
      ? (doneLabel ?? '')
      : children;

  // icon-only режим: иконка есть, а контент пустой → квадратная плашка
  const isIconOnly = !!Icon && !label && !isLoading && !isDone;
  const sizeCls = isIconOnly ? sizeCfg.iconOnly : sizeCfg.padded;

  // link-вариант имеет нулевые паддинги, glow ему ни к чему
  const isLink = variant === 'link';

  return (
    <button
      ref={ref}
      disabled={disabled || isLoading}
      style={useGlow ? cssVarsFromString(v.glow) : undefined}
      className={[
        'relative inline-flex items-center justify-center font-black transition-all',
        // leading-none нужен для idеального вертикального центра — без него шрифт font-black
        // имеет подъём baseline и текст кажется смещённым вниз.
        sizeCfg.leading,
        // link не использует общий радиус; у остальных rounded-2xl
        isLink ? '' : 'rounded-2xl',
        // сжатие при клике — не для link
        isLink ? '' : 'active:scale-[0.97]',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--sff)] focus-visible:ring-[color-mix(in_oklab,var(--cta)_55%,transparent)]',
        useGlow && !isLink ? 'pulse-btn-glow' : '',
        sizeCls,
        v.base,
        block ? 'w-full' : '',
        className,
      ].filter(Boolean).join(' ')}
      {...rest}
    >
      <span className={`relative inline-flex items-center justify-center ${size === 'sm' ? 'gap-1.5' : 'gap-2'}`}>
        {isLoading && (
          <Loader2 size={iconSize} className="animate-spin" />
        )}
        {isDone && (
          <Check size={iconSize + 2} className="pulse-btn-check" strokeWidth={3} />
        )}
        {!isLoading && !isDone && Icon && (
          <Icon size={iconSize} />
        )}
        {label && <span>{label}</span>}
      </span>
    </button>
  );
});

function cssVarsFromString(s) {
  // '--a:#fff; --b:#000;' → { '--a':'#fff', '--b':'#000' }
  const out = {};
  s.split(';').forEach(pair => {
    const [k, v] = pair.split(':').map(x => x?.trim());
    if (k && v) out[k] = v;
  });
  return out;
}

export default Button;
