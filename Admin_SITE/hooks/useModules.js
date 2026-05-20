// Admin_SITE/hooks/useModules.js
import { useCallback, useEffect, useState } from 'react';
import { getActiveWs } from '../components/shared/api';

function authHeaders(extra = {}) {
  const token = localStorage.getItem('auth_token');
  const h = { ...extra };
  if (token) h.Authorization = `Bearer ${token}`;
  const ws = getActiveWs();
  if (ws != null) h['X-Workspace-Id'] = String(ws);
  return h;
}

/**
 * useModules(wsId)
 *  - modules:  массив {id, name, section, description, is_enabled, updated_at, updated_by}
 *  - loading:  true пока идёт начальная загрузка
 *  - error:    Error при последней неудачной операции (или null)
 *  - enable(moduleId)            — вкл
 *  - disable(moduleId, reason)   — выкл с обязательной причиной
 *  - history(moduleId, limit=20) — лента истории по модулю
 *  - reload()                    — перезагрузить список
 *
 * wsId == null → хук не делает запросов (modules = []). Это валидное состояние,
 * пока пользователь не выбрал workspace.
 */
export function useModules(wsId) {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const load = useCallback(async () => {
    if (wsId == null) { setModules([]); return; }
    setLoading(true); setError(null);
    try {
      const r = await fetch(`/api/workspaces/${wsId}/modules`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setModules(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e);
      setModules([]);
    } finally {
      setLoading(false);
    }
  }, [wsId]);

  useEffect(() => { load(); }, [load]);

  const enable = useCallback(async (moduleId) => {
    if (wsId == null) throw new Error('no active workspace');
    const r = await fetch(
      `/api/workspaces/${wsId}/modules/${moduleId}/enable`,
      {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: '{}',
      },
    );
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    await load();
  }, [wsId, load]);

  const disable = useCallback(async (moduleId, reason) => {
    if (wsId == null) throw new Error('no active workspace');
    if (!reason || !reason.trim()) throw new Error('reason required');
    const r = await fetch(
      `/api/workspaces/${wsId}/modules/${moduleId}/disable`,
      {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ reason }),
      },
    );
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    await load();
  }, [wsId, load]);

  const history = useCallback(async (moduleId, limit = 20) => {
    if (wsId == null) return [];
    const r = await fetch(
      `/api/workspaces/${wsId}/modules/${moduleId}/history?limit=${limit}`,
      { headers: authHeaders() },
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }, [wsId]);

  return { modules, loading, error, enable, disable, history, reload: load };
}
