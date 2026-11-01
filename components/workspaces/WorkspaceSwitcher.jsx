// Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx
// V1.17.0d (Подпроект #3): выбор активного сообщества в топбаре.
// V1.17.0i (P4 C8): ярлык «⭐ главное / №N доп.» в опциях и title — порядок
// «главное сверху» уже обеспечен API (`is_pulse_themed DESC`).
// V1.17.0j: <img> поверх монограммы при наличии ws.icon_url (auto-аватар
// main-чата из Telegram); 404 / load fail → useAuthImage.failed=true,
// рендерим прежнюю монограмму.
import React, { useEffect, useState } from 'react';
import { fetchWorkspaces, getActiveWs, setActiveWs } from '../shared/api';
import { useAuthImage } from '../shared/useAuthImage';

export default function WorkspaceSwitcher({ token, onSwitch }) {
  const [list, setList] = useState([]);
  const [active, setActive] = useState(getActiveWs());

  useEffect(() => {
    if (!token) return;
    fetchWorkspaces(token)
      .then((d) => {
        const ws = d.workspaces || [];
        setList(ws);
        // V1.17.0P6: если в localStorage стоит ws_id которого больше НЕТ
        // в списке доступных (например после merge/delete workspace),
        // переключаемся на первый доступный. Иначе клики на тумблеры/Права
        // молча уходят в 404.
        if (ws.length > 0) {
          const current = getActiveWs();
          const exists = ws.some((w) => w.id === current);
          if (current == null || !exists) {
            setActiveWs(ws[0].id);
            setActive(ws[0].id);
          }
        }
      })
      .catch(() => {});
  }, [token]);

  // V1.17.0j10 HOTFIX: вычисления и хук useAuthImage ОБЯЗАНЫ идти до любого
  // условного return — иначе при первом рендере (list=[]) хук не вызывается,
  // а после fetch — вызывается, и React падает с «Rendered more hooks than
  // during the previous render» → белый экран всего приложения (Switcher
  // живёт в топбаре). Хук безопасно отрабатывает с пустыми url/token.
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
  // V1.17.0j: пытаемся подгрузить аватар; при 404/error падаем на монограмму.
  const { src: iconSrc, failed: iconFailed } = useAuthImage(cur?.icon_url, token);

  if (list.length <= 1) return null;

  const change = (e) => {
    const id = parseInt(e.target.value, 10);
    setActiveWs(id);
    setActive(id);
    if (onSwitch) onSwitch(id);
  };

  // V1.17.0i C8: префикс для опции — ⭐ у главного, «№N доп.» у прочих.
  // Нумерация считается синхронно с WorkspaceList: первое доп. = №2.
  const renderLabel = (w, extraIdx) => {
    if (w.is_primary) return `⭐ ${w.name} · ${w.role}`;
    return `№${extraIdx} доп. · ${w.name} · ${w.role}`;
  };

  return (
    <div
      className="flex items-center gap-2 rounded-2xl border-2 border-bd2 bg-sff pl-1.5 pr-2 py-1"
      title={`Активное сообщество: ${cur?.name || ''}${cur?.is_primary ? ' · главное' : ' · доп.'}`}
    >
      <span
        className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-black flex-shrink-0 relative overflow-hidden ${tile}`}
        aria-hidden="true"
      >
        {iconSrc && !iconFailed ? (
          <img
            src={iconSrc}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
            draggable={false}
          />
        ) : (
          mono
        )}
      </span>
      <select
        value={active ?? ''}
        onChange={change}
        className="text-sm font-bold bg-transparent outline-none cursor-pointer pr-1 max-w-[200px]"
        aria-label="Активное сообщество"
      >
        {(() => {
          let extraIdx = 1; // первый ++ даст №2
          return list.map((w) => (
            <option key={w.id} value={w.id}>
              {renderLabel(w, w.is_primary ? null : ++extraIdx)}
            </option>
          ));
        })()}
      </select>
    </div>
  );
}
