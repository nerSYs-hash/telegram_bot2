import { useState, useEffect } from 'react';
import { Ban, X } from 'lucide-react';
import EconomyHeader from './EconomyHeader';
import EconomyCategory from './EconomyCategory';
import EconomyCategoryCard from './EconomyCategoryCard';
import EconomyHistoryPanel from './EconomyHistoryPanel';
import EconomyCancellationsPanel from './EconomyCancellationsPanel';
import { useEconomyWS } from './useEconomyWS';
import TitlesPanel from '../titles/TitlesPanel';

export default function EconomyPage({ token }) {
  const [categories, setCategories]     = useState([]);
  const [metrics, setMetrics]           = useState(null);
  const [expandedSections, setExpanded] = useState(new Set());
  const [historyPanel, setHistoryPanel] = useState(null); // {settingKey, label}
  const [cancellationsOpen, setCancellationsOpen] = useState(false);
  const [recentlyChanged, setRecently]  = useState(new Set());
  const [liveBanner, setLiveBanner]     = useState(null);
  const [currentUser, setCurrentUser]   = useState(null);
  const [canEdit, setCanEdit]           = useState(false);
  const [canCancel, setCanCancel]       = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null); // {key, is_enabled}
  const [categoryEnabledStates, setCategoryEnabledStates] = useState({});

  const wsEvents = useEconomyWS(token);

  const headers = { Authorization: `Bearer ${token}` };

  const loadCategories = () =>
    fetch('/api/economy/categories', { headers })
      .then(r => r.json())
      .then(d => { 
        if (Array.isArray(d)) {
          setCategories(d);
          const states = {};
          d.forEach(cat => { states[cat.key] = cat.is_enabled; });
          setCategoryEnabledStates(states);
        }
      })
      .catch(() => {});

  useEffect(() => {
    loadCategories();
    fetch('/api/economy/metrics', { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.pulse_rate != null) setMetrics(d); })
      .catch(() => {});
    fetch('/api/admin/profile/me', { headers })
      .then(r => r.json())
      .then(profile => {
        setCurrentUser(profile);
        const role = profile?.role_raw || '';
        setCanEdit(role === 'owner' || role === 'developer' || role === 'deputy');
        // Отмены выплат — только владелец (бэк требует economy.cancel)
        setCanCancel(role === 'owner');
      })
      .catch(() => {});
  }, [token]);

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
    <div className="space-y-4 pb-32 animate-in fade-in duration-500">
      <EconomyHeader metrics={metrics} />

      {canCancel && (
        <div className="flex justify-end">
          <button
            onClick={() => setCancellationsOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-sff border border-[color-mix(in_oklab,var(--danger)_40%,transparent)]
                       text-danger rounded-2xl text-xs font-black uppercase tracking-widest
                       hover:bg-[color-mix(in_oklab,var(--danger)_10%,transparent)] active:scale-95 transition shadow-sm">
            <Ban size={14} /> Отмены выплат
          </button>
        </div>
      )}

      {/* Сетка карточек категорий */}
      {categories.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {categories.map(cat => (
            <EconomyCategoryCard
              key={cat.key}
              category={cat}
              token={token}
              onOpenDetails={(key) => {
                setSelectedCategory(cat);
                setExpanded(prev => {
                  const next = new Set(prev);
                  next.add(key);
                  return next;
                });
              }}
              onMasterToggle={async (comment) => {
                const res = await fetch(
                  `/api/economy/categories/${cat.key}/toggle`,
                  {
                    method: 'PATCH',
                    headers: {
                      'Content-Type': 'application/json',
                      Authorization: `Bearer ${token}`,
                    },
                    body: JSON.stringify({ comment }),
                  }
                );
                if (!res.ok) {
                  const d = await res.json().catch(() => ({}));
                  throw new Error(d.detail || 'Ошибка');
                }
                setCategoryEnabledStates(prev => ({
                  ...prev,
                  [cat.key]: !prev[cat.key],
                }));
              }}
              sectionEnabled={categoryEnabledStates[cat.key] ?? cat.is_enabled}
              canEdit={canEdit}
            />
          ))}
        </div>
      )}

      {/* Модальное окно с деталями категории */}
      {selectedCategory && (
        <CategoryDetailModal
          category={selectedCategory}
          isExpanded={expandedSections.has(selectedCategory.key)}
          onClose={() => {
            setSelectedCategory(null);
            setExpanded(prev => {
              const next = new Set(prev);
              next.delete(selectedCategory.key);
              return next;
            });
          }}
          onOpenHistory={(key, label) =>
            setHistoryPanel({ settingKey: key, label })
          }
          token={token}
          recentlyChanged={recentlyChanged}
          canEdit={canEdit}
          sectionEnabled={categoryEnabledStates[selectedCategory.key] ?? selectedCategory.is_enabled}
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

      {cancellationsOpen && (
        <EconomyCancellationsPanel
          token={token}
          canCancel={canCancel}
          onClose={() => setCancellationsOpen(false)}
        />
      )}

      {liveBanner && <LiveBanner event={liveBanner} />}
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
