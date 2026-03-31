import {startTransition, useEffect, useState} from 'react';
import {useRef} from 'react';
import type {BootstrapResponse} from './types';
import {API_BASE} from './api';

import HomePage from './HomePage';
import ProfilePage from './ProfilePage';
import BbsPage from './BbsPage';
import EconomyPage from './EconomyPage';

// --- BottomNavBar ---
const NAV_ITEMS = [
  { id: 'home', label: 'Главная', icon: '🏠' },
  { id: 'profile', label: 'Профиль', icon: '👤' },
  { id: 'bbs', label: 'BBS', icon: '💬' },
  { id: 'economy', label: 'Экономика', icon: '💎' },
];

function BottomNavBar({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 mx-auto flex h-16 max-w-md items-center justify-around rounded-t-3xl border-t border-white/10 bg-black/70 shadow-[0_-8px_32px_rgba(0,0,0,0.25)] backdrop-blur-md">
      {NAV_ITEMS.map((item) => {
        const active = page === item.id;
        return (
          <button
            key={item.id}
            onClick={() => setPage(item.id as Page)}
            className={`flex flex-col items-center justify-center gap-0.5 px-2 pt-1 transition-all duration-200 ${
              active ? 'scale-110 text-cyan-300 drop-shadow-[0_2px_8px_rgba(34,211,238,0.25)]' : 'text-stone-400 hover:text-cyan-200'
            }`}
            style={{ flex: 1 }}
          >
            <span className={`text-2xl transition-all ${active ? 'drop-shadow-[0_2px_8px_rgba(34,211,238,0.25)]' : ''}`}>{item.icon}</span>
            <span className="text-[11px] font-medium tracking-wide">{item.label}</span>
            {active && <span className="mt-0.5 block h-1 w-6 rounded-full bg-cyan-400/80 transition-all" />}
          </button>
        );
      })}
    </nav>
  );
}

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

type Page = 'home' | 'profile' | 'bbs' | 'economy';

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

  const [page, setPage] = useState<Page>('home');
  const [data, setData] = useState<BootstrapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [prevPage, setPrevPage] = useState<Page>('home');
  const [animating, setAnimating] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
    fetchBootstrap()
      .then((p) => startTransition(() => { setData(p); setLoading(false); }))
      .catch((e: Error) => startTransition(() => { setError(e.message); setLoading(false); }));
  }, []);

  // Анимированная смена страницы
  function handleSetPage(newPage: Page) {
    if (newPage === page) return;
    setPrevPage(page);
    setAnimating(true);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setPage(newPage);
      setAnimating(false);
    }, 220); // длительность анимации
  }

  // Контент страниц
  function getContent(p: Page) {
    if (p === 'profile' && data?.user?.userId != null) {
      return <ProfilePage userId={data.user.userId} onBack={() => handleSetPage('home')} />;
    } else if (p === 'bbs' && data?.user?.userId != null) {
      return <BbsPage userId={data.user.userId} onBack={() => handleSetPage('home')} />;
    } else if (p === 'economy' && data?.user?.userId != null) {
      return <EconomyPage userId={data.user.userId} onBack={() => handleSetPage('home')} />;
    } else {
      return (
        <HomePage
          loading={loading}
          error={error}
          data={data}
          onGoProfile={() => handleSetPage('profile')}
          onGoBbs={() => handleSetPage('bbs')}
          onGoEconomy={() => handleSetPage('economy')}
        />
      );
    }
  }

  export default function App() {
    // ...existing code (все хуки и функции выше)
    return (
      <div className="relative min-h-screen pb-20 bg-[#090d14]">
        <div className="relative">
          {animating && (
            <div className="absolute inset-0 z-10 animate-fadeOut pointer-events-none">
              {getContent(prevPage)}
            </div>
          )}
          <div className={animating ? 'animate-fadeIn' : ''}>
            {getContent(page)}
          </div>
        </div>
        <BottomNavBar page={page} setPage={handleSetPage} />
      </div>
    );
  }
