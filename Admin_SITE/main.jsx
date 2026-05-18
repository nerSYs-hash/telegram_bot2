import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './AdminDashboard.jsx'

/* ── DEV-ONLY УЗКИЙ мок для дизайн-QA Экономики (cutover §2b) ────────
   Двойная защита: только `vite dev` + ?preview. Перехватывает ТОЛЬКО
   два эндпоинта Экономики (без них экран висит на «Загрузка…»). Всё
   остальное — сквозняком (Триггеры/прочее не трогаем → без краша).
   В прод-сборке import.meta.env.DEV=false → блок мёртв. */
if (
  import.meta.env.DEV &&
  typeof window !== 'undefined' &&
  new URLSearchParams(window.location.search).has('preview')
) {
  const orig = window.fetch.bind(window)
  const json = (b) =>
    Promise.resolve(
      new Response(JSON.stringify(b), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || ''
    if (/\/api\/economy\/metrics(\?|$)/.test(url)) {
      return json({
        pulse_rate: 1.25,
        bank_balance: 816904,
        users_balance: 1248000,
        total_supply: 2184320,
        emission_24h: 34120,
        emission_7d: 210000,
      })
    }
    if (/\/api\/economy\/categories(\?|$)/.test(url)) {
      return json([]) // пустой массив → шапка + тематизированное empty-state
    }
    return orig(input, init)
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
