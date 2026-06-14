import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// Top-level guard: a render-time throw anywhere in the tree should surface a
// readable message instead of a blank page (which is otherwise indistinguishable
// from "the app didn't load").
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Amagra UI crashed during render:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          fontFamily: 'system-ui, sans-serif', maxWidth: 640, margin: '64px auto',
          padding: '24px 28px', color: '#48341C',
          background: '#FAF7F2', border: '1px solid #E0D6C4', borderRadius: 12,
        }}>
          <h1 style={{ fontSize: 18, margin: '0 0 8px', color: '#9A6C00' }}>
            Amagra hit a render error
          </h1>
          <p style={{ fontSize: 13, lineHeight: 1.6, color: '#7A6A52' }}>
            The dashboard failed to render. Reload the page; if it persists, the
            details below help locate the cause.
          </p>
          <pre style={{
            fontSize: 12, background: '#F0E9DF', padding: '12px 14px',
            borderRadius: 8, overflow: 'auto', whiteSpace: 'pre-wrap',
          }}>{String(this.state.error?.stack || this.state.error)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
