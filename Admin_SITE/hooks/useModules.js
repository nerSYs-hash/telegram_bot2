// Admin_SITE/hooks/useModules.js
import { useCallback, useEffect, useState } from 'react';
import { getActiveWs } from '../components/shared/api';
import catalog from '../../shared/modules_catalog.json';

function authHeaders(extra = {}) {
  const token = localStorage.getItem('auth_token');
  const h = { ...extra };
  if (token) h.Authorization = `Bearer ${token}`;
  const ws = getActiveWs();
  if (ws != null) h['X-Workspace-Id'] = String(ws);
  return h;
}

// DEV-fallback: на localhost без токена API недоступно — отдаём локальный
// каталог из shared/modules_catalog.json (16 модулей, все is_enabled=false
// по умолчанию). enable/disable мутируют только in-memory — для дизайн-QA.
function _isDevPreview() {
  if (typeof window === 'undefined') return false;
  if (!import.meta.env.DEV) return false;
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1';
}

function _catalogAsModules() {
  return catalog.modules.map((m) => ({
    id: m.id,
    name: m.name,
    section: m.section,
    description: m.description,
    is_enabled: false,
    updated_at: null,
    updated_by: null,
  }));
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
 * wsId == null → если dev-preview, грузим локальный каталог (in-memory).
 * Иначе — пустой массив (валидное состояние, workspace не выбран).
 */
export function useModules(wsId) {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const devPreview = _isDevPreview();

  const load = useCallback(async () => {
    if (wsId == null) {
      // dev-preview: показываем каталог локально для дизайн-QA
      setModules(devPreview ? _catalogAsModules() : []);
      return;
    }
    setLoading(true); setError(null);
    try {
      const r = await fetch(`/api/workspaces/${wsId}/modules`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setModules(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e);
      setModules(devPreview ? _catalogAsModules() : []);
    } finally {
      setLoading(false);
    }
  }, [wsId, devPreview]);

  useEffect(() => { load(); }, [load]);

  const enable = useCallback(async (moduleId) => {
    if (wsId == null) {
      if (devPreview) {
        setModules(prev => prev.map(m => m.id === moduleId ? { ...m, is_enabled: true } : m));
        return;
      }
      throw new Error('no active workspace');
    }
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
  }, [wsId, load, devPreview]);

  const disable = useCallback(async (moduleId, reason) => {
    if (!reason || !reason.trim()) throw new Error('reason required');
    if (wsId == null) {
      if (devPreview) {
        setModules(prev => prev.map(m => m.id === moduleId ? { ...m, is_enabled: false } : m));
        return;
      }
      throw new Error('no active workspace');
    }
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
  }, [wsId, load, devPreview]);

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
