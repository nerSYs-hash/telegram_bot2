import { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';

/**
 * SiteUpdateToast — «тихое обновление».
 * Периодически проверяет, не вышла ли новая сборка сайта (сменился хеш
 * бандла в index.html). Если да — показывает мягкий тост «Вышло обновление»
 * с кнопкой перезагрузки. Без жёстких сбросов: пользователь сам жмёт.
 *
 * Как детектит: запоминает текущий хеш бандла (из <script src=assets/index-*.js>),
 * раз в N минут тянет свежий index.html (cache-busted) и сравнивает.
 */
const CHECK_EVERY_MS = 3 * 60 * 1000; // каждые 3 минуты

function currentBundle() {
  const el = document.querySelector('script[src*="/assets/index-"]');
  const m = el && el.getAttribute('src') && el.getAttribute('src').match(/assets\/index-[A-Za-z0-9_-]+\.js/);
  return m ? m[0] : null;
}

export default function SiteUpdateToast() {
  const [show, setShow] = useState(false);
  const baseline = useRef(currentBundle());

  useEffect(() => {
    let stop = false;
    const check = async () => {
      try {
        const r = await fetch(`/?_=${Date.now()}`, { cache: 'no-store' });
        const html = await r.text();
        const m = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
        const fresh = m ? m[0] : null;
        if (!stop && fresh && baseline.current && fresh !== baseline.current) {
          // Не торопимся: показываем тост, ТОЛЬКО когда новый бандл реально
          // доступен (деплой завершён). Иначе ждём следующей проверки —
          // чтобы не предлагать «Обновить», пока обновление ещё катится.
          try {
            const probe = await fetch(`/${fresh}`, { method: 'HEAD', cache: 'no-store' });
            if (!stop && probe.ok) setShow(true);
          } catch { /* бандл ещё не готов — подождём */ }
        }
      } catch { /* офлайн/сеть — молча пропускаем */ }
    };
    const id = setInterval(check, CHECK_EVERY_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  if (!show) return null;

  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[200] animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex items-center gap-3 rounded-2xl bg-tx text-white shadow-2xl px-4 py-3 border border-white/10">
        <RefreshCw size={16} className="text-mint" />
        <span className="text-[13px] font-semibold">Вышло обновление сайта</span>
        <button onClick={() => window.location.reload()}
                className="ml-1 text-[12px] font-black uppercase tracking-wide bg-cta hover:brightness-110
                           px-3 py-1.5 rounded-xl transition">
          Обновить
        </button>
        <button onClick={() => setShow(false)}
                className="text-white/50 hover:text-white text-[12px] px-1" title="Позже">
          ✕
        </button>
      </div>
    </div>
  );
}
