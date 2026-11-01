// Хук useEconomyWS — подключение к WebSocket экономики
// (живые апдейты значений параметров и тумблеров).

import { useState, useEffect, useRef } from 'react';

export function useEconomyWS(token) {
  const [last, setLast] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  useEffect(() => {
    if (!token) return;

    function connect() {
      try {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/api/ws/economy?token=${token}`);

        ws.onmessage = (e) => {
          try { setLast(JSON.parse(e.data)); } catch {}
        };
        ws.onerror = () => {};
        ws.onclose = () => {
          reconnectTimer.current = setTimeout(connect, 3000);
        };

        wsRef.current = ws;
      } catch {}
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [token]);

  return { last };
}
