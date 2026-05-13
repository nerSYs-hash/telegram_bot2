// useWorkspaces hook (V1.17.0b12) — список сообществ + polling 30s
import { useEffect, useState, useCallback } from 'react';
import { fetchWorkspaces } from '../shared/api';

export function useWorkspaces(token) {
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWorkspaces(token);
      setWorkspaces(data.workspaces || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { reload(); }, [reload]);

  // Polling каждые 30 сек — на случай если бот добавился в новый чат через TG
  useEffect(() => {
    if (!token) return;
    const id = setInterval(reload, 30000);
    return () => clearInterval(id);
  }, [token, reload]);

  return { workspaces, loading, error, reload };
}
