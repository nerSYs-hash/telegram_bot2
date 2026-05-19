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

  // Иконка сообщества: поля аватара в API нет → детерминированная
  // цветная плитка-монограмма (паттерн как в WorkspaceList), цвет по id —
  // чтобы сообщество узнавалось по иконке, а не только по названию.
  const TILES = [
    'bg-[color-mix(in_oklab,var(--cta)_18%,transparent)] text-cta',
    'bg-[color-mix(in_oklab,var(--purple)_18%,transparent)] text-purple',
    'bg-[color-mix(in_oklab,var(--ok)_18%,transparent)] text-ok',
    'bg-[color-mix(in_oklab,var(--warn)_18%,transparent)] text-warn',
    'bg-[color-mix(in_oklab,var(--pink)_18%,transparent)] text-pink',
    'bg-[color-mix(in_oklab,var(--mint)_18%,transparent)] text-mint',
  ];
  const cur = list.find((w) => w.id === active) || list[0];
  const tile = TILES[Math.abs(Number(cur?.id) || 0) % TILES.length];
  const mono = (cur?.name || '?').trim().charAt(0).toUpperCase();

  return (
    <div
      className="flex items-center gap-2 rounded-2xl border-2 border-bd2 bg-sff pl-1.5 pr-2 py-1"
      title={`Активное сообщество: ${cur?.name || ''}`}
    >
      <span
        className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-black flex-shrink-0 ${tile}`}
        aria-hidden="true"
      >
        {mono}
      </span>
      <select
        value={active ?? ''}
        onChange={change}
        className="text-sm font-bold bg-transparent outline-none cursor-pointer pr-1 max-w-[180px]"
        aria-label="Активное сообщество"
      >
        {list.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name} · {w.role}
          </option>
        ))}
      </select>
    </div>
  );
}
