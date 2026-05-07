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

const VARIANTS = {
  primary: {
    base:  'bg-blue-500 text-white hover:bg-blue-600',
    glow:  '--glow-from:#60a5fa; --glow-via:#a855f7; --glow-to:#60a5fa;',
    glowDefault: true,
  },
  secondary: {
    base:  'bg-gray-100 text-gray-700 hover:bg-gray-200',
    glow:  '--glow-from:#9ca3af; --glow-via:#6b7280; --glow-to:#9ca3af;',
    glowDefault: false,
  },
  ghost: {
    base:  'bg-transparent text-gray-600 hover:bg-gray-100',
    glow:  '--glow-from:#9ca3af; --glow-via:#6b7280; --glow-to:#9ca3af;',
    glowDefault: false,
  },
  danger: {
    base:  'bg-red-500 text-white hover:bg-red-600',
    glow:  '--glow-from:#fb7185; --glow-via:#ef4444; --glow-to:#fb7185;',
    glowDefault: true,
  },
  success: {
    base:  'bg-emerald-500 text-white hover:bg-emerald-600',
    glow:  '--glow-from:#34d399; --glow-via:#10b981; --glow-to:#34d399;',
    glowDefault: true,
  },
};

const SIZES = {
  sm: 'px-3   py-1.5 text-xs   gap-1.5',
  md: 'px-4   py-2.5 text-sm   gap-2',
  lg: 'px-6   py-3   text-base gap-2',
};

const ICON_SIZE = { sm: 12, md: 14, lg: 16 };

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
  const iconSize  = ICON_SIZE[size] || 14;

  const label = isLoading
    ? (loadingLabel ?? children)
    : isDone
      ? (doneLabel ?? '')
      : children;

  return (
    <button
      ref={ref}
      disabled={disabled || isLoading}
      style={useGlow ? cssVarsFromString(v.glow) : undefined}
      className={[
        'relative inline-flex items-center justify-center font-black rounded-2xl transition-all',
        'active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-300',
        useGlow ? 'pulse-btn-glow' : '',
        SIZES[size],
        v.base,
        block ? 'w-full' : '',
        className,
      ].filter(Boolean).join(' ')}
      {...rest}
    >
      {/* Анимация смены контента — fade-зона */}
      <span className="relative inline-flex items-center gap-[inherit]">
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
