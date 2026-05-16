import { Check } from 'lucide-react';

/**
 * Горизонтальный stepper для отображения этапов flow.
 *
 * props:
 *   steps     — [{ id, label, icon? (Lucide), color? ('blue'|'emerald'|'violet'|'amber'|'rose') }]
 *   current   — id текущего шага (по нему определяется completed/future)
 *   completed — массив id завершённых шагов (опционально, если не передать —
 *               считаются завершёнными все шаги ДО current)
 *   onStepClick(id) — клик по шагу (опц., для интерактивных степперов)
 *   compact   — компактный режим (без подписей, только круги)
 *   className
 */

// Все классы перечисляем явно, иначе Tailwind JIT не подхватит при динамической интерполяции.
const COLOR_MAP = {
  blue:    { bg: 'bg-blue-500',    text: 'text-blue-700',    ring: 'ring-blue-100',    shadow: 'shadow-blue-300/60'    },
  emerald: { bg: 'bg-emerald-500', text: 'text-emerald-700', ring: 'ring-emerald-100', shadow: 'shadow-emerald-300/60' },
  violet:  { bg: 'bg-violet-500',  text: 'text-violet-700',  ring: 'ring-violet-100',  shadow: 'shadow-violet-300/60'  },
  amber:   { bg: 'bg-amber-500',   text: 'text-amber-700',   ring: 'ring-amber-100',   shadow: 'shadow-amber-300/60'   },
  rose:    { bg: 'bg-rose-500',    text: 'text-rose-700',    ring: 'ring-rose-100',    shadow: 'shadow-rose-300/60'    },
};

export default function Stepper({
  steps = [],
  current,
  completed,
  onStepClick,
  compact = false,
  className = '',
}) {
  const currentIdx = Math.max(0, steps.findIndex(s => s.id === current));
  const completedSet = new Set(
    completed ?? steps.slice(0, currentIdx).map(s => s.id)
  );

  return (
    <div className={`w-full flex items-center ${className}`}>
      {steps.map((step, i) => {
        const isCurrent  = step.id === current;
        const isComplete = completedSet.has(step.id);
        const state = isCurrent ? 'current' : isComplete ? 'complete' : 'future';
        const color = COLOR_MAP[step.color || 'blue'];
        const Icon  = step.icon;

        // ── Кружок ──
        const circleCls = state === 'complete'
          ? 'bg-emerald-500 text-white border-2 border-emerald-500'
          : state === 'current'
            ? `${color.bg} text-white border-2 border-white shadow-lg ${color.shadow} ring-4 ${color.ring}`
            : 'bg-white text-gray-400 border-2 border-gray-200';

        // ── Линия после кружка ──
        const isLast = i === steps.length - 1;
        const lineCls = state === 'complete'
          ? 'bg-emerald-500'
          : 'bg-gray-200';

        return (
          <div key={step.id} className={`flex items-center ${isLast ? '' : 'flex-1'}`}>
            {/* Step узел */}
            <div className="flex flex-col items-center gap-1.5 min-w-0">
              <button
                type="button"
                onClick={() => onStepClick?.(step.id)}
                disabled={!onStepClick}
                className={`relative w-9 h-9 rounded-full flex items-center justify-center transition-all ${circleCls} ${onStepClick ? 'cursor-pointer hover:scale-110 active:scale-95' : 'cursor-default'} ${state === 'current' ? 'pulse-step-current' : ''}`}
                aria-label={step.label}
              >
                {state === 'complete'
                  ? <Check size={16} strokeWidth={3} />
                  : Icon ? <Icon size={15} /> : <span className="text-xs font-black">{i + 1}</span>}
              </button>
              {!compact && (
                <span className={`text-[10px] font-black uppercase tracking-wide whitespace-nowrap ${
                  state === 'current' ? color.text :
                  state === 'complete' ? 'text-emerald-600' :
                  'text-gray-400'
                }`}>
                  {step.label}
                </span>
              )}
            </div>

            {/* Линия-коннектор */}
            {!isLast && (
              <div className="flex-1 h-0.5 mx-2 mb-5 rounded-full transition-colors duration-300 overflow-hidden">
                <div className={`h-full ${lineCls} transition-all duration-500`} style={{ width: '100%' }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
