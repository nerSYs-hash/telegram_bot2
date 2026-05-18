import { Info, AlertTriangle } from 'lucide-react';
import Button from './Button';

/**
 * Унифицированный модал подтверждения в стиле триггеров.
 *
 * props:
 *   open           — показывать ли
 *   title          — заголовок (по умолчанию «Внимание»)
 *   message        — текст / JSX
 *   confirmLabel   — лейбл подтверждения (по умолчанию «Продолжить настройку»)
 *   cancelLabel    — лейбл отмены       (по умолчанию «Выйти»)
 *   variant        — 'info' (амбер) | 'danger' (красный)
 *   onConfirm()    — клик «Продолжить»
 *   onCancel()     — клик «Выйти»
 *
 * Раскладка совпадает с триггерами: левая «Выйти» (gray) + правая
 * «Продолжить настройку» (blue/red), модалка центрирована, blur-фон.
 */
export default function ConfirmDialog({
  open,
  title = 'Внимание',
  message,
  confirmLabel = 'Продолжить настройку',
  cancelLabel = 'Выйти',
  variant = 'info',
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  const Icon = variant === 'danger' ? AlertTriangle : Info;
  const iconBg = variant === 'danger' ? 'bg-[color-mix(in_oklab,var(--danger)_16%,transparent)]'    : 'bg-[color-mix(in_oklab,var(--warn)_16%,transparent)]';
  const iconFg = variant === 'danger' ? 'text-danger'  : 'text-warn';

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150"
         onClick={onCancel}>
      <div className="bg-sff rounded-3xl shadow-2xl p-6 w-80 max-w-[90vw] space-y-4 animate-in zoom-in-95 duration-200"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-full ${iconBg} flex items-center justify-center flex-shrink-0 mt-0.5`}>
            <Icon size={20} className={iconFg}/>
          </div>
          <div>
            <p className="font-black text-tx text-base leading-tight">{title}</p>
            <div className="text-sm text-txd mt-1.5 leading-relaxed">
              {message}
            </div>
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" size="md" block onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={variant === 'danger' ? 'danger' : 'primary'} size="md" block onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
