import {startTransition, useEffect, useState} from 'react';
import type {BootstrapResponse} from './types';
import {API_BASE} from './api';
import HomePage from './HomePage';
import ProfilePage from './ProfilePage';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready?: () => void;
        expand?: () => void;
        initDataUnsafe?: {
          user?: {id?: number; username?: string; first_name?: string};
        };
        platform?: string;
        version?: string;
      };
    };
  }
}

type Page = 'home' | 'profile';

function resolveUserId(): number | undefined {
  const q = new URLSearchParams(window.location.search).get('tgUserId');
  if (q) {
    const n = Number(q);
    if (!Number.isNaN(n)) return n;
  }
  const tid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  return typeof tid === 'number' ? tid : undefined;
}

async function fetchBootstrap(): Promise<BootstrapResponse> {
  const url = new URL('/api/mini-app/bootstrap', API_BASE);
  const uid = resolveUserId();
  if (uid) url.searchParams.set('user_id', String(uid));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Bootstrap ${res.status}`);
  return res.json();
}

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [data, setData] = useState<BootstrapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
    fetchBootstrap()
      .then((p) => startTransition(() => { setData(p); setLoading(false); }))
      .catch((e: Error) => startTransition(() => { setError(e.message); setLoading(false); }));
  }, []);

  if (page === 'profile' && data?.user?.userId != null) {
    return <ProfilePage userId={data.user.userId} onBack={() => setPage('home')} />;
  }
  return <HomePage loading={loading} error={error} data={data} onGoProfile={() => setPage('profile')} />;
}

