import React, { useState } from 'react';
import { Newspaper, X, ChevronRight } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════
//  ОПОВЕЩЕНИЕ ОБ ОБНОВЛЕНИИ  ·  выплывающая плашка
//  Появляется, когда вышла новая версия с прошлого визита: версия +
//  дата + короткий заголовок. Тап по плашке → проваливает в раздел
//  «Новости». Крестик — отметить прочитанным. Часть единой концепции
//  Новостного раздела (красный акцент «Новое», стиль карточек панели).
// ═══════════════════════════════════════════════════════════════════

export default function UpdateToast({ latest, onOpen, onDismiss }) {
  const [leaving, setLeaving] = useState(false);
  if (!latest) return null;

  const close = (cb) => { setLeaving(true); setTimeout(cb, 220); };

  return (
    <div className={`fixed z-[60] bottom-5 right-5 left-5 sm:left-auto sm:w-[360px] ${leaving ? 'news-toast-out' : 'news-toast-in'}`}>
      <div onClick={() => close(onOpen)}
           className="relative cursor-pointer bg-sff border border-bd rounded-[2rem] shadow-xl p-4 pr-9 flex items-center gap-3.5 hover:border-bd2 transition-colors">
        {/* иконка с красной точкой «новое» */}
        <div className="relative w-12 h-12 rounded-2xl bg-cta flex items-center justify-center flex-shrink-0 shadow-md">
          <Newspaper size={22} className="text-white" />
          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-danger ring-2 ring-sff animate-pulse" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-black uppercase tracking-widest text-danger">Новое</span>
            <span className="text-[10px] font-mono text-lbl truncate">{latest.version} · {latest.date}</span>
          </div>
          <p className="text-sm font-black text-tx leading-snug mt-0.5 line-clamp-2">{latest.title}</p>
          <p className="text-[11px] font-bold text-cta mt-1 flex items-center gap-0.5">
            Открыть Новости <ChevronRight size={12} />
          </p>
        </div>

        <button onClick={(e) => { e.stopPropagation(); close(onDismiss); }}
                aria-label="Закрыть"
                className="absolute top-3 right-3 p-1 rounded-lg text-lbl hover:bg-ih hover:text-tx transition-colors">
          <X size={15} />
        </button>
      </div>
    </div>
  );
}
