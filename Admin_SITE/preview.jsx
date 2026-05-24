import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import DesignSystemPreview from './components/preview/DesignSystemPreview.jsx';

// Отдельный вход БЕЗ авторизации (Telegram-логин на localhost невозможен —
// «Bot domain invalid»). Это живой State Sheet для приёмки Части 2.
ReactDOM.createRoot(document.getElementById('ds-root')).render(
  <React.StrictMode>
    <DesignSystemPreview />
  </React.StrictMode>,
);
