import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './AdminDashboard.jsx';

class GlobalErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('Puls Admin UI Error:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px', backgroundColor: '#0f172a', color: '#f8fafc', fontFamily: 'system-ui, sans-serif' }}>
          <div style={{ maxWidth: '600px', width: '100%', backgroundColor: '#1e293b', border: '1px solid #ef4444', borderRadius: '16px', padding: '32px', textAlign: 'center' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
            <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '8px' }}>Ошибка панели управления</h2>
            <p style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '20px' }}>Произошла ошибка при загрузке интерфейса.</p>
            <pre style={{ fontSize: '12px', textAlign: 'left', backgroundColor: '#0f172a', padding: '16px', borderRadius: '12px', color: '#f87171', overflowX: 'auto', marginBottom: '24px' }}>
              {this.state.error?.stack || this.state.error?.message || String(this.state.error)}
            </pre>
            <button
              onClick={() => { localStorage.clear(); window.location.reload(); }}
              style={{ backgroundColor: '#2563eb', color: '#fff', border: 'none', padding: '12px 24px', borderRadius: '12px', fontWeight: 'bold', cursor: 'pointer', fontSize: '14px' }}
            >
              Сбросить кэш и перезагрузить
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById('root');
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <GlobalErrorBoundary>
        <App />
      </GlobalErrorBoundary>
    </React.StrictMode>
  );
} else {
  console.error('Root element #root not found');
}
