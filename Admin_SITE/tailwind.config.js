/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./*.jsx",
    "./*.js",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      // DESIGN_BRIEF §2.5 — семантические токены как Tailwind-утилиты.
      // Значения живут в index.css (обе темы), здесь только имена.
      colors: {
        bg:      'var(--bg)',
        bg2:     'var(--bg2)',
        sf:      'var(--sf)',
        sff:     'var(--sff)',
        sf2:     'var(--sf2)',
        bd:      'var(--bd)',
        bd2:     'var(--bd2)',
        tx:      'var(--tx)',
        txd:     'var(--txd)',
        lbl:     'var(--lbl)',
        cta:     'var(--cta)',
        ok:      'var(--ok)',
        warn:    'var(--warn)',
        yellow:  'var(--yellow)',
        danger:  'var(--danger)',
        purple:  'var(--purple)',
        pink:    'var(--pink)',
        mint:    'var(--mint)',
        neutral: 'var(--neutral)',
      },
      borderRadius: {
        // §3 радиус-канон 16px (rounded-2xl уже = 1rem = 16px — дублируем явно)
        token:    'var(--r)',     // 16px
        'token-sm': 'var(--rsm)', // 12px
        pill:     'var(--rpill)',
      },
      transitionTimingFunction: {
        ds:    'cubic-bezier(.22,.61,.36,1)',
        spring: 'cubic-bezier(.34,1.56,.64,1)',
      },
    },
  },
  plugins: [],
}
