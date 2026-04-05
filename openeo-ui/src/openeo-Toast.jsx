import { useState, useEffect, useCallback, createContext, useContext } from "react";

const stylesToast = `
  :root {
    --toast-bg: #0f0f0f;
    --toast-border: rgba(255,255,255,0.08);
    --toast-text: #f0ede8;
    --toast-sub: rgba(240,237,232,0.45);
    --accent-success: #a8e6a3;
    --accent-error: #f4a9a8;
    --accent-warning: #f7d9a0;
    --accent-info: #a3c8f4;
    --glow-success: rgba(168,230,163,0.15);
    --glow-error: rgba(244,169,168,0.15);
    --glow-warning: rgba(247,217,160,0.15);
    --glow-info: rgba(163,200,244,0.15);
  }

  .toast-wrapper {
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-end;
  }

  .toast {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 18px;
    background: var(--toast-bg);
    border: 1px solid var(--toast-border);
    border-radius: 14px;
    min-width: 280px;
    max-width: 360px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.05) inset;
    animation: slideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    backdrop-filter: blur(12px);
  }

  .toast.leaving {
    animation: slideOut 0.35s cubic-bezier(0.4, 0, 1, 1) forwards;
  }

  .toast::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 14px;
    opacity: 0.6;
    pointer-events: none;
  }

  .toast.success::before { background: var(--glow-success); }
  .toast.error::before   { background: var(--glow-error); }
  .toast.warning::before { background: var(--glow-warning); }
  .toast.info::before    { background: var(--glow-info); }

  .toast-progress {
    position: absolute;
    bottom: 0;
    left: 0;
    height: 2px;
    border-radius: 0 0 14px 14px;
    animation: shrink linear forwards;
  }

  .toast.success .toast-progress { background: var(--accent-success); }
  .toast.error   .toast-progress { background: var(--accent-error); }
  .toast.warning .toast-progress { background: var(--accent-warning); }
  .toast.info    .toast-progress { background: var(--accent-info); }

  .toast-icon {
    font-size: 15px;
    flex-shrink: 0;
    margin-top: 1px;
    line-height: 1;
  }

  .toast-body {
    flex: 1;
    min-width: 0;
  }

  .toast-title {
    font-size: 14px;
    font-weight: 300;
    font-style: italic;
    color: var(--toast-text);
    line-height: 1.3;
    letter-spacing: 0.01em;
  }

  .toast.success .toast-title { color: var(--accent-success); }
  .toast.error   .toast-title { color: var(--accent-error); }
  .toast.warning .toast-title { color: var(--accent-warning); }
  .toast.info    .toast-title { color: var(--accent-info); }

  .toast-message {
    font-size: 11px;
    color: var(--toast-sub);
    margin-top: 3px;
    line-height: 1.5;
    letter-spacing: 0.02em;
  }

  .toast-close {
    background: none;
    border: none;
    color: var(--toast-sub);
    cursor: pointer;
    font-size: 13px;
    padding: 0;
    line-height: 1;
    flex-shrink: 0;
    margin-top: 1px;
    transition: color 0.2s;
  }
  .toast-close:hover { color: var(--toast-text); }

  @keyframes slideIn {
    from { opacity: 0; transform: translateX(60px) scale(0.92); }
    to   { opacity: 1; transform: translateX(0) scale(1); }
  }

  @keyframes slideOut {
    from { opacity: 1; transform: translateX(0) scale(1); }
    to   { opacity: 0; transform: translateX(60px) scale(0.92); }
  }

  @keyframes shrink {
    from { width: 100%; }
    to   { width: 0%; }
  }`;

const ICONS = { success: "✦", error: "✕", warning: "◆", info: "◈" };
const DURATION = 4000;

let toastId = 0;

// ─── Single Toast ────────────────────────────────────────────────────────────

function Toast({ id, type = "info", title, message, duration = DURATION, onRemove }) {
  const [leaving, setLeaving] = useState(false);

  const dismiss = useCallback(() => {
    setLeaving(true);
    setTimeout(() => onRemove(id), 340);
  }, [id, onRemove]);

  useEffect(() => {
    const t = setTimeout(dismiss, duration);
    return () => clearTimeout(t);
  }, [dismiss, duration]);

  return (
    <div className={`toast ${type} ${leaving ? "leaving" : ""}`}>
      <span className="toast-icon">{ICONS[type]}</span>
      <div className="toast-body">
        <div className="toast-title">{title}</div>
        {message && <div className="toast-message">{message}</div>}
      </div>
      <button className="toast-close" onClick={dismiss}>✕</button>
      <div
        className="toast-progress"
        style={{ animationDuration: `${duration}ms` }}
      />
    </div>
  );
}

// ─── Toast Container ─────────────────────────────────────────────────────────

export function ToastContainer({ toasts, onRemove }) {
  return (
    <div className="toast-wrapper">
      {toasts.map(t => (
        <Toast key={t.id} {...t} onRemove={onRemove} />
      ))}
    </div>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback(({ type = "info", title, message, duration = DURATION }) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, type, title, message, duration }]);
  }, []);

  const removeToast = useCallback(id => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return { toasts, addToast, removeToast };
}

// ─── Context ──────────────────────────────────────────────────────────────────

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const { toasts, addToast, removeToast } = useToast();
  return (
    <ToastContext.Provider value={addToast}>
      <style>{stylesToast}</style>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToastContext() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToastContext must be used inside <ToastProvider>");
  return ctx;
}