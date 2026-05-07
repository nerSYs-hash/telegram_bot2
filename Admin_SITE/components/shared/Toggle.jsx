/**
 * Унифицированный toggle-switch в стиле дизайн-системы Pulse.
 *
 * props:
 *   checked       — bool
 *   onChange(b)   — колбэк
 *   label         — основной текст
 *   hint          — подсказка под лейблом
 *   icon          — Lucide-компонент иконки слева от лейбла
 *   className     — доп. классы
 */
export default function Toggle({
  checked,
  onChange,
  label,
  hint,
  icon: Icon,
  className = '',
}) {
  return (
    <label className={`flex items-start gap-3 cursor-pointer py-1 select-none ${className}`}>
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange?.(e.target.checked)}
        className="hidden"
      />
      <div
        className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 mt-0.5 ${
          checked ? 'bg-blue-500' : 'bg-gray-200'
        }`}
      >
        <div
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-[18px]' : 'translate-x-0.5'
          }`}
        />
      </div>
      {(label || hint) && (
        <div className="flex-1 min-w-0">
          {label && (
            <div className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
              {Icon && <Icon size={13} className="text-gray-500" />}
              {label}
            </div>
          )}
          {hint && <div className="text-[10px] text-gray-400 mt-0.5">{hint}</div>}
        </div>
      )}
    </label>
  );
}
