import { useState, useEffect, useCallback } from 'react';
import EconomyHeader from './EconomyHeader';
import EconomyCategory from './EconomyCategory';
import EconomyHistoryPanel from './EconomyHistoryPanel';
import { useEconomyWS } from './useEconomyWS';

export default function EconomyPage({ token }) {
  const [categories, setCategories]     = useState([]);
  const [metrics, setMetrics]           = useState(null);
  const [expandedSections, setExpanded] = useState(new Set());
  const [historyPanel, setHistoryPanel] = useState(null); // {settingKey, label}
  const [recentlyChanged, setRecently]  = useState(new Set());
  const [liveBanner, setLiveBanner]     = useState(null);
  const [currentUser, setCurrentUser]   = useState(null);
  const [canEdit, setCanEdit]           = useState(false);

  const wsEvents = useEconomyWS(token);

  const headers = { Authorization: `Bearer ${token}` };

  const loadCategories = () =>
    fetch('/api/economy/categories', { headers })
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) setCategories(d); })
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
        setCanEdit(role === 'owner' || role === 'deputy');
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

    if (!isMine && ['setting_changed', 'rollback', 'section_toggled'].includes(ev.event)) {
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

  const toggleSection = useCallback((key) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }, []);

  return (
    <div className="space-y-4 pb-32 animate-in fade-in duration-500">
      <EconomyHeader metrics={metrics} />

      {categories.map(cat => (
        <EconomyCategory
          key={cat.key}
          category={cat}
          isExpanded={expandedSections.has(cat.key)}
          onToggle={() => toggleSection(cat.key)}
          onOpenHistory={(key, label) => setHistoryPanel({ settingKey: key, label })}
          token={token}
          recentlyChanged={recentlyChanged}
          canEdit={canEdit}
        />
      ))}

      {categories.length === 0 && (
        <div className="bg-white rounded-3xl border border-gray-100 p-12 text-center text-gray-400">
          <div className="text-4xl mb-3">💰</div>
          <div className="font-black text-gray-600">Загрузка экономики...</div>
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
                setRecently(p => { const n = new Set(p); n.delete(historyPanel.settingKey); return n; });
              }, 60_000);
              return next;
            });
          }}
        />
      )}

      {liveBanner && <LiveBanner event={liveBanner} />}
    </div>
  );
}

function LiveBanner({ event }) {
  const text = event.event === 'setting_changed'
    ? `${event.by} изменил: ${event.old_value} → ${event.new_value}`
    : event.event === 'section_toggled'
    ? `${event.by} ${event.enabled ? 'включил' : 'выключил'} раздел`
    : `${event.by} откатил к ${event.to_value}`;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm bg-amber-50 border border-amber-200 rounded-2xl shadow-lg p-4
                    animate-in slide-in-from-right duration-300">
      <div className="flex items-start gap-3">
        <span className="text-xl shrink-0">🔔</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-black text-amber-800 break-words">{text}</div>
          {event.comment && (
            <div className="text-[11px] text-amber-700 italic mt-1">💬 {event.comment}</div>
          )}
        </div>
      </div>
    </div>
  );
}
