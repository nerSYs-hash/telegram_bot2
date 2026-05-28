import { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { X, ChevronLeft, ChevronRight, Search, ChevronDown, Coins } from 'lucide-react';

const _SEARCH_OPEN_KEY = 'pulse_economy_search_open';

/**
 * Выдвижной поиск.
 *  - default: закрыт (виден только handle-кнопка со стрелкой).
 *  - persistence через localStorage — переживает refresh страницы.
 *  - cleanup на unmount — auto-close при уходе со вкладки.
 *  - hover-nudge через CSS-класс search-handle-nudge.
 *  - drag-to-open: pointerdown + move >= 24px вправо.
 */
function SlidingSearch({ query, setQuery }) {
  const [open, setOpen] = useState(
    () => typeof window !== 'undefined' && localStorage.getItem(_SEARCH_OPEN_KEY) === '1'
  );
  const inputRef = useRef(null);

  // Persistence + auto-focus при открытии
  useEffect(() => {
    localStorage.setItem(_SEARCH_OPEN_KEY, open ? '1' : '0');
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  // Auto-close при уходе со вкладки Экономика (unmount)
  useEffect(() => {
    return () => { localStorage.removeItem(_SEARCH_OPEN_KEY); };
  }, []);

  // Drag-to-open: pointerdown на handle + move >= 24px вправо
  const handlePointerDown = (e) => {
    if (open) return;
    const startX = e.clientX;
    const onMove = (ev) => {
      if (ev.clientX - startX >= 24) {
        setOpen(true);
        cleanup();
      }
    };
    const cleanup = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', cleanup);
      window.removeEventListener('pointercancel', cleanup);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', cleanup);
    window.addEventListener('pointercancel', cleanup);
  };

  const closeAndClear = () => { setQuery(''); setOpen(false); };

  return (
    <div className="flex items-center gap-2">
      {/* Handle-кнопка: видна всегда, при closed «дёргается» на hover */}
      <button
        type="button"
        onClick={() => (open ? closeAndClear() : setOpen(true))}
        onPointerDown={handlePointerDown}
        title={open ? 'Скрыть поиск' : 'Показать поиск'}
        className={`w-9 h-9 rounded-full bg-cta text-white flex items-center justify-center shadow-sm
                    hover:brightness-110 active:scale-95 transition cursor-pointer
                    ${open ? '' : 'search-handle-nudge'}`}
      >
        {open ? <X size={16}/> : <ChevronRight size={16}/>}
      </button>

      {/* Input — выезжает справа от handle */}
      <div
        className="overflow-hidden transition-all duration-300 ease-out"
        style={{ width: open ? 280 : 0, opacity: open ? 1 : 0 }}
      >
        <div className="relative">
          <Search size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-lbl pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') closeAndClear();
            }}
            placeholder="Поиск категорий…"
            className="w-full pl-9 pr-3 py-2 rounded-2xl bg-sff border border-bd text-sm
                       focus:outline-none focus:border-cta transition-colors"
          />
        </div>
      </div>
    </div>
  );
}
import EconomyHeader from './EconomyHeader';
import EconomyCategory from './EconomyCategory';
import EconomyCategoryCard from './EconomyCategoryCard';
import EconomyHistoryPanel from './EconomyHistoryPanel';
import EconomyEditModal from './EconomyEditModal';
import EconomyToggleModal from './EconomyToggleModal';
import { useEconomyWS } from './useEconomyWS';
import TitlesPanel from '../titles/TitlesPanel';

// DEV-fallback (V1.17.0h2a): на localhost без бэкенда API падает с
// ECONNREFUSED → подставляем mock-данные для дизайн-QA. На проде ветка
// не активируется (import.meta.env.DEV=false).
const _DEV_PREVIEW =
  typeof window !== 'undefined'
  && import.meta.env.DEV
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const _MOCK_METRICS = {
  pulse_rate: 1.42,
  bank_balance: 12_500_450,
  users_balance: 4_218_300,
  total_supply: 16_718_750,
  emission_24h: 42_300,
  emission_7d: 287_100,
};
// Системная карточка «Отмены выплат» — всегда первая, относится ко всем
// модулям Экономики. Без мастер-свича (см. economy_categories_as_modules).
const _SYSTEM_CARDS = [
  { key: 'cancellations', label: 'Отмены выплат', is_enabled: true, rows_count: 0 },
];

const _MOCK_CATS = [
  { key: 'mining',       label: 'Майнинг',          is_enabled: true,  rows_count: 6 },
  { key: 'vip_bbs',      label: 'VIP / BBS',        is_enabled: true,  rows_count: 4 },
  { key: 'titles',       label: 'Кастомные Титулы', is_enabled: true,  rows_count: 5 },
  { key: 'lottery',      label: 'Лотерея',          is_enabled: false, rows_count: 5 },
  { key: 'bingo',        label: 'Бинго',            is_enabled: true,  rows_count: 4 },
  { key: 'monthly_gift', label: 'Подарок месяца',   is_enabled: true,  rows_count: 3 },
  { key: 'referral',     label: 'Рефералы',         is_enabled: true,  rows_count: 3 },
  { key: 'bbs_bonus',    label: 'BBS-бонусы',       is_enabled: true,  rows_count: 2 },
];

export default function EconomyPage({ token, modulesApi }) {
  const [categories, setCategories]     = useState([]);
  const [metrics, setMetrics]           = useState(null);
  const [expandedSections, setExpanded] = useState(new Set());
  const [historyPanel, setHistoryPanel] = useState(null); // {settingKey, label}
  const [recentlyChanged, setRecently]  = useState(new Set());
  const [liveBanner, setLiveBanner]     = useState(null);
  const [currentUser, setCurrentUser]   = useState(null);
  const [canEdit, setCanEdit]           = useState(false);
  const [canCancel, setCanCancel]       = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null); // {key, is_enabled}
  const [query, setQuery] = useState('');
  // Шапка-метрики свёрнута в «язычок» по умолчанию (решение 21.05 —
  // занимала много места без функции). Состояние переживает refresh.
  const [metricsOpen, setMetricsOpen] = useState(
    () => typeof window !== 'undefined' && localStorage.getItem('pulse_economy_metrics_open') === '1'
  );
  // Edit/Toggle row теперь inline в карточке (по решению 21.05).

  const wsEvents = useEconomyWS(token);

  const headers = { Authorization: `Bearer ${token}` };

  const _applyMockIfDev = () => {
    if (!_DEV_PREVIEW) return false;
    setCategories([..._SYSTEM_CARDS, ..._MOCK_CATS]);
    setMetrics(_MOCK_METRICS);
    setCanEdit(true);
    setCanCancel(true);
    return true;
  };

  // Клиентский пост-процессинг:
  //  - префикс «Отмены выплат» — постоянная системная карточка (всегда
  //    первая, относится ко всем модулям Экономики).
  //  - суффикс «Кастомные Титулы» — псевдо-категория (TitlesPanel внутри).
  const _ensureSystemCards = (list) => {
    const out = [..._SYSTEM_CARDS, ...list.filter(c => c.key !== 'cancellations')];
    if (!out.some(c => c.key === 'titles')) {
      out.push({ key: 'titles', label: 'Кастомные Титулы', is_enabled: true, rows_count: 5 });
    }
    return out;
  };

  const loadCategories = () =>
    fetch('/api/economy/categories', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (Array.isArray(d) && d.length) {
          setCategories(_ensureSystemCards(d));
        } else {
          _applyMockIfDev();
        }
      })
      .catch(() => { _applyMockIfDev(); });

  useEffect(() => {
    loadCategories();
    fetch('/api/economy/metrics', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.pulse_rate != null) setMetrics(d); else if (_DEV_PREVIEW) setMetrics(_MOCK_METRICS); })
      .catch(() => { if (_DEV_PREVIEW) setMetrics(_MOCK_METRICS); });
    fetch('/api/admin/profile/me', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(profile => {
        if (profile) {
          setCurrentUser(profile);
          const role = profile?.role_raw || '';
          setCanEdit(role === 'owner' || role === 'developer' || role === 'deputy');
          setCanCancel(role === 'owner');
        } else if (_DEV_PREVIEW) {
          setCanEdit(true);
          setCanCancel(true);
        }
      })
      .catch(() => { if (_DEV_PREVIEW) { setCanEdit(true); setCanCancel(true); } });
  }, [token]);

  // Блокируем общий скрол страницы на время Экономики:
  // прокрутка остаётся только внутри карточки (если нужно).
  useEffect(() => {
    const prevBody = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevBody;
      document.documentElement.style.overflow = prevHtml;
    };
  }, []);

  // REST-фоллбэк метрик каждые 30 сек
  useEffect(() => {
    const id = setInterval(() => {
      fetch('/api/economy/metrics', { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.pulse_rate != null) setMetrics(d); })
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, [token]);

  // WS события
  useEffect(() => {
    const ev = wsEvents.last;
    if (!ev) return;

    if (ev.event === 'metrics_update') { setMetrics(ev); return; }

    const myName = currentUser?.username || currentUser?.first_name;
    const isMine = ev.by && myName && ev.by === myName;

    if (!isMine && ['setting_changed', 'rollback', 'section_toggled', 'cancellation'].includes(ev.event)) {
      setLiveBanner(ev);
      setTimeout(() => setLiveBanner(null), 8000);
    }

    if (ev.key && ['setting_changed', 'rollback'].includes(ev.event)) {
      setRecently(prev => {
        const next = new Set(prev);
        next.add(ev.key);
        setTimeout(() => {
          setRecently(p => { const n = new Set(p); n.delete(ev.key); return n; });
        }, 60_000);
        return next;
      });
    }
  }, [wsEvents.last]);

  return (
    <div className="flex flex-col gap-4 animate-in fade-in duration-500 overflow-hidden">
      {/* ── Тонкий top-bar: язычок шторки «Сводка» + поиск ── */}
      <div className="flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMetricsOpen(o => {
              const next = !o;
              try { localStorage.setItem('pulse_economy_metrics_open', next ? '1' : '0'); } catch { /* ignore */ }
              return next;
            })}
            title={metricsOpen ? 'Свернуть сводку' : 'Показать сводку экономики'}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-2xl bg-sff border border-bd shadow-sm
                       text-[11px] font-black uppercase tracking-widest text-txd
                       hover:border-cta hover:text-cta transition active:scale-95"
          >
            <Coins size={13} className="text-warn" />
            Сводка экономики
            <ChevronDown
              size={14}
              className={`transition-transform duration-300 ${metricsOpen ? 'rotate-180' : ''}`}
            />
          </button>
          <div className="flex-1" />
          <SlidingSearch query={query} setQuery={setQuery} />
        </div>

        {/* Шторка с метриками — grid 0fr→1fr для плавного выезда сверху вниз */}
        <div
          className="grid transition-all duration-300 ease-out"
          style={{ gridTemplateRows: metricsOpen ? '1fr' : '0fr' }}
        >
          <div className="overflow-hidden">
            <div className="pt-3">
              <EconomyHeader metrics={metrics} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Карусель категорий (V1.17.0h2b) ── */}
      {categories.length > 0 && (
        <CategoryCarousel
          categories={categories.filter(c =>
            !query.trim() || c.label.toLowerCase().includes(query.trim().toLowerCase())
          )}
          activeKey={selectedCategory?.key || null}
          onActivate={(cat) => setSelectedCategory(cat)}
          onClose={() => setSelectedCategory(null)}
          modulesApi={modulesApi}
          token={token}
          canEdit={canEdit}
          recentlyChanged={recentlyChanged}
          onOpenHistory={(key, label) => setHistoryPanel({ settingKey: key, label })}
          canCancel={canCancel}
        />
      )}

      {categories.length === 0 && (
        <div className="bg-sff rounded-3xl border border-bd p-12 text-center text-lbl">
          <div className="text-4xl mb-3">💰</div>
          <div className="font-black text-txd">Загрузка экономики...</div>
        </div>
      )}

      {historyPanel && (
        <EconomyHistoryPanel
          settingKey={historyPanel.settingKey}
          label={historyPanel.label}
          token={token}
          onClose={() => setHistoryPanel(null)}
          canEdit={canEdit}
          onRolledBack={() => {
            setRecently(prev => {
              const next = new Set(prev);
              next.add(historyPanel.settingKey);
              setTimeout(() => {
                setRecently(p => {
                  const n = new Set(p);
                  n.delete(historyPanel.settingKey);
                  return n;
                });
              }, 60_000);
              return next;
            });
          }}
        />
      )}

      {/* Отмены выплат — теперь встроены в карточку «Отмены выплат».
          Боковая панель осталась только для истории изменений. */}
      {liveBanner && <LiveBanner event={liveBanner} />}
    </div>
  );
}

/**
 * Карусель категорий: горизонтальная прокрутка вертикальных карточек.
 * Активная карточка разворачивается inline (130px → 450px) внутри карусели.
 * Авто-скролл к активной + точки-индикаторы снизу.
 */
function CategoryCarousel({
  categories, activeKey, onActivate, onClose,
  modulesApi,
  token, canEdit, canCancel, recentlyChanged, onOpenHistory,
}) {
  const scrollRef = useRef(null);
  const itemRefs  = useRef({});
  const prevRects = useRef(new Map());
  const [arrows, setArrows] = useState({ l: false, r: false });
  const [activeIdx, setActiveIdx] = useState(0);

  // (Откачено) FLIP-анимация была сломана — карусель ехала во все
  // стороны. Соседи теперь просто двигаются как flex-следствие
  // width-transition активной карточки (плавно само по себе, без
  // дополнительного transform).

  const checkArrows = () => {
    const el = scrollRef.current;
    if (!el) return;
    setArrows({
      l: el.scrollLeft > 8,
      r: el.scrollLeft + el.clientWidth < el.scrollWidth - 8,
    });
  };

  // Active dot — ближайшая к центру видимой области карточка.
  // Если есть активная (раскрытая) — приоритет ей.
  const updateActiveDot = () => {
    const el = scrollRef.current;
    if (!el) return;
    // Приоритет — раскрытая карточка
    if (activeKey) {
      const idx = categories.findIndex(c => c.key === activeKey);
      if (idx >= 0) { setActiveIdx(idx); return; }
    }
    const center = el.scrollLeft + el.clientWidth / 2;
    let best = 0;
    let bestDist = Infinity;
    categories.forEach((c, i) => {
      const node = itemRefs.current[c.key];
      if (!node) return;
      const mid = node.offsetLeft + node.offsetWidth / 2;
      const d = Math.abs(mid - center);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    setActiveIdx(best);
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    checkArrows();
    updateActiveDot();
    const onScroll = () => { checkArrows(); updateActiveDot(); };
    el.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      el.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories.length, activeKey]);

  // Авто-скролл к активной карточке — ОТЛОЖЕН на ~520ms (после конца
  // width-transition + FLIP), чтобы не дёргать ленту во время анимации.
  useEffect(() => {
    if (!activeKey) return;
    const t = setTimeout(() => {
      const el = scrollRef.current;
      const node = itemRefs.current[activeKey];
      if (!el || !node) return;
      const target = node.offsetLeft - Math.max(0, (el.clientWidth - 450) / 2);
      el.scrollTo({ left: Math.max(0, target), behavior: 'smooth' });
    }, 520);
    return () => clearTimeout(t);
  }, [activeKey]);

  const scrollBy = (dir) => scrollRef.current?.scrollBy({ left: dir * 260, behavior: 'smooth' });

  return (
    <div className="relative flex flex-col" style={{ height: 420 }}>
      {/* Левая/правая стрелки */}
      {arrows.l && (
        <button
          type="button"
          onClick={() => scrollBy(-1)}
          className="absolute left-1 top-1/2 -translate-y-1/2 z-30 w-9 h-9 rounded-full
                     bg-sff border border-bd2 shadow-lg flex items-center justify-center
                     text-txd hover:text-cta hover:border-cta transition"
          aria-label="Назад"
        >
          <ChevronLeft size={18} />
        </button>
      )}
      {arrows.r && (
        <button
          type="button"
          onClick={() => scrollBy(1)}
          className="absolute right-1 top-1/2 -translate-y-1/2 z-30 w-9 h-9 rounded-full
                     bg-sff border border-bd2 shadow-lg flex items-center justify-center
                     text-txd hover:text-cta hover:border-cta transition"
          aria-label="Вперёд"
        >
          <ChevronRight size={18} />
        </button>
      )}

      {/* Карусель — фикс. высота, горизонтальный скролл */}
      <div
        ref={scrollRef}
        className="flex items-stretch gap-3 overflow-x-auto scroll-smooth flex-1 min-h-0"
        style={{
          paddingLeft: arrows.l ? 44 : 0,
          paddingRight: arrows.r ? 44 : 0,
          transition: 'padding .25s ease',
        }}
      >
        {categories.map(cat => (
          <div
            key={cat.key}
            ref={el => { if (el) itemRefs.current[cat.key] = el; else delete itemRefs.current[cat.key]; }}
            className="h-full"
          >
            <EconomyCategoryCard
              category={cat}
              token={token}
              active={activeKey === cat.key}
              onActivate={() => onActivate(cat)}
              onClose={onClose}
              onOpenHistory={onOpenHistory}
              modulesApi={modulesApi}
              canEdit={canEdit}
              canCancel={canCancel}
              recentlyChanged={recentlyChanged}
            />
          </div>
        ))}
      </div>

      {/* Точки-индикаторы под каруселью */}
      {categories.length > 1 && (
        <div className="flex items-center justify-center gap-1.5 mt-3 flex-shrink-0">
          {categories.map((c, i) => (
            <button
              key={c.key}
              type="button"
              onClick={() => onActivate(c)}
              aria-label={`Перейти к ${c.label}`}
              className={`h-1.5 rounded-full transition-all duration-200
                          ${i === activeIdx ? 'w-6 bg-cta' : 'w-1.5 bg-bd2 hover:bg-lbl'}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CategoryDetailModal({
  category,
  isExpanded,
  onClose,
  onOpenHistory,
  token,
  recentlyChanged,
  canEdit,
  sectionEnabled,
}) {
  return (
    <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="fixed inset-0 overflow-y-auto">
        <div className="flex min-h-full items-start justify-end">
          <div className="w-full max-w-2xl bg-sff rounded-l-3xl shadow-2xl animate-in slide-in-from-right duration-300">
            {/* Шапка с кнопкой закрытия */}
            <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-bd bg-sff">
              <h2 className="text-lg font-black text-tx">
                {category.label}
              </h2>
              <button
                onClick={onClose}
                className="p-2 hover:bg-sf2 rounded-lg transition"
              >
                <X size={20} className="text-txd" />
              </button>
            </div>

            {/* Содержимое */}
            <div className="p-6 space-y-4">
              <EconomyCategory
                category={category}
                isExpanded={true}
                onToggle={() => {}}
                onOpenHistory={onOpenHistory}
                token={token}
                recentlyChanged={recentlyChanged}
                canEdit={canEdit}
                sectionEnabled={sectionEnabled}
              />

              {category.key === 'referral' && (
                <div className="mt-6 pt-6 border-t border-bd">
                  <div className="rounded-2xl border border-bd bg-sf2 p-4 text-sm text-tx">
                    <div className="font-bold mb-2">ℹ️ Одна система — два сообщения</div>
                    <p className="text-txd leading-relaxed">
                      Размер награды и условия квалификации (часы, сообщения, реакции)
                      одинаково применяются и к <b>большому реф-сообщению</b> (то что
                      приходит после прохождения анкеты), и к <b>маленькому сообщению</b>{' '}
                      по кнопке «🎟 Моя ссылка» / команде <code>/myref</code>.
                    </p>
                    <p className="text-txd leading-relaxed mt-2">
                      Это одна и та же реф-система. Просто работает в двух режимах:
                      с анкетой (если модуль «Регистрация» включён) — через ссылку на
                      бота; без анкеты — через TG-invite ссылку прямо в чат.
                    </p>
                  </div>
                </div>
              )}

              {category.key === 'vip_bbs' && (
                <div className="mt-6 pt-6 border-t border-bd">
                  <TitlesPanel token={token} canEdit={canEdit} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LiveBanner({ event }) {
  let text;
  if (event.event === 'setting_changed') {
    text = `${event.by} изменил: ${event.old_value} → ${event.new_value}`;
  } else if (event.event === 'section_toggled') {
    text = `${event.by} ${event.enabled ? 'включил' : 'выключил'} раздел`;
  } else if (event.event === 'cancellation') {
    text = event.type === 'pointwise'
      ? `${event.by} отменил выплату #${event.tx_id} (${event.mode})`
      : `${event.by} зафиксировал массовую отмену: ${event.affected_users} юзеров на ${event.total} 💎`;
  } else {
    text = `${event.by} откатил к ${event.to_value}`;
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] border border-[color-mix(in_oklab,var(--warn)_40%,transparent)] rounded-2xl shadow-lg p-4
                    animate-in slide-in-from-right duration-300">
      <div className="flex items-start gap-3">
        <span className="text-xl shrink-0">🔔</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-black text-warn break-words">{text}</div>
          {event.comment && (
            <div className="text-[11px] text-warn italic mt-1">💬 {event.comment}</div>
          )}
        </div>
      </div>
    </div>
  );
}
