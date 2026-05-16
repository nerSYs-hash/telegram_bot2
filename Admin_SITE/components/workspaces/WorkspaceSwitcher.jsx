// Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx
// V1.17.0d (Подпроект #3): выбор активного сообщества в топбаре.
import React, { useEffect, useState } from 'react';
import { fetchWorkspaces, getActiveWs, setActiveWs } from '../shared/api';

export default function WorkspaceSwitcher({ token, onSwitch }) {
  const [list, setList] = useState([]);
  const [active, setActive] = useState(getActiveWs());

  useEffect(() => {
    if (!token) return;
    fetchWorkspaces(token)
      .then((d) => {
        const ws = d.workspaces || [];
        setList(ws);
        if (getActiveWs() == null && ws.length) {
          setActiveWs(ws[0].id);
          setActive(ws[0].id);
        }
      })
      .catch(() => {});
  }, [token]);

  if (list.length <= 1) return null;

  const change = (e) => {
    const id = parseInt(e.target.value, 10);
    setActiveWs(id);
    setActive(id);
    if (onSwitch) onSwitch(id);
  };

  return (
    <select
      value={active ?? ''}
      onChange={change}
      className="text-sm font-bold rounded-2xl border-2 border-gray-200 px-3 py-1.5 bg-white"
      title="Активное сообщество"
    >
      {list.map((w) => (
        <option key={w.id} value={w.id}>
          {w.name} · {w.role}
        </option>
      ))}
    </select>
  );
}
