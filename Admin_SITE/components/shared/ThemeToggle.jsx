import { useState, useEffect } from 'react';
import { Moon, Sun } from 'lucide-react';

/**
 * Самодостаточный sun/moon-тумблер темы (DESIGN_BRIEF §5a).
 * Не требует состояния App: сам читает/пишет класс на <html> и localStorage.
 * Источник правды — класс .theme-dark / .theme-light на documentElement
 * (его же ставит pre-paint скрипт в index.html, без FOUC).
 */
export default function ThemeToggle({ className = '' }) {
  const get = () =>
    document.documentElement.classList.contains('theme-dark') ? 'dark' : 'light';
  const [theme, setTheme] = useState(get);

  useEffect(() => {
    const h = document.documentElement;
    h.classList.toggle('theme-dark', theme === 'dark');
    h.classList.toggle('theme-light', theme === 'light');
    try { localStorage.setItem('puls.theme', theme); } catch { /* ignore */ }
  }, [theme]);

  return (
    <div
      className={`relative inline-flex items-center w-[88px] h-9 rounded-full p-[3px] select-none
        bg-sf2 border border-bd ${className}`}
      role="tablist"
      aria-label="Тема оформления"
    >
      <span
        className={`absolute top-[3px] h-[calc(100%-6px)] w-[calc(50%-3px)] rounded-full
          bg-[color-mix(in_oklab,var(--cta)_22%,var(--sff))]
          border border-[color-mix(in_oklab,var(--cta)_50%,transparent)] shadow-sm
          transition-transform duration-[220ms] ease-[cubic-bezier(.34,1.56,.64,1)]
          ${theme === 'light' ? 'translate-x-full' : ''}`}
      />
      <button
        type="button"
        onClick={() => setTheme('dark')}
        aria-label="Тёмная тема"
        className={`flex-1 z-10 inline-flex justify-center transition-colors
          ${theme === 'dark' ? 'text-tx' : 'text-lbl'}`}
      >
        <Moon size={16} strokeWidth={2.4} />
      </button>
      <button
        type="button"
        onClick={() => setTheme('light')}
        aria-label="Светлая тема"
        className={`flex-1 z-10 inline-flex justify-center transition-colors
          ${theme === 'light' ? 'text-tx' : 'text-lbl'}`}
      >
        <Sun size={16} strokeWidth={2.4} />
      </button>
    </div>
  );
}
