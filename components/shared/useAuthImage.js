// Admin_SITE/components/shared/useAuthImage.js
// V1.17.0j: загрузка картинки с Bearer JWT через fetch → blob URL.
//
// Зачем не <img src={url}>? Потому что /api/workspaces/{id}/icon.jpg
// требует Authorization-заголовок (как и весь /api/workspaces/*),
// а <img> заголовки не отправляет. Query-param с токеном размывал бы
// auth-flow и попадал бы в логи прокси.
//
// Использование:
//   const { src, failed } = useAuthImage(ws.icon_url, token);
//   {src && !failed ? <img src={src}/> : <Fallback/>}
//
// failed=true при HTTP-ошибке (404 = иконка ещё не закеширована, или
// флаг WORKSPACE_ICONS=OFF на бэке) — компонент рисует fallback (монограмму).
import { useEffect, useState } from 'react';

export function useAuthImage(url, token) {
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!url || !token) {
      setSrc(null);
      setFailed(false);
      return;
    }
    let cancelled = false;
    let objectUrl = null;
    setFailed(false);
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);

  return { src, failed };
}
