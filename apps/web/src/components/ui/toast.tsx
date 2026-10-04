"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// A tiny, dependency-free toast system: a provider that renders a bottom-right stack, plus a
// `useToast()` hook that any client component can call to surface a transient, can't-miss message
// (e.g. a failed save or run). No new dep (keeps the minimal-deps stance); styled with the app's
// tokens.

type Variant = "default" | "error";
type Toast = { id: number; message: string; variant: Variant };
type ToastContextValue = { toast: (message: string, variant?: Variant) => void };

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

// A toast that has to outlive a full page navigation (e.g. `window.location.assign` after deleting
// a workspace) can't sit in React state. Park it in sessionStorage; the next provider mount shows it
// once and clears it, so a refresh doesn't replay it.
const FLASH_KEY = "calypr:flash-toast";

export function flashToast(message: string, variant: Variant = "default") {
  try {
    sessionStorage.setItem(FLASH_KEY, JSON.stringify({ message, variant }));
  } catch {
    // Storage blocked (private mode etc.): the toast is a nicety, the navigation still happens.
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: Variant = "default") => {
    const id = Date.now() + Math.random();
    setToasts((cur) => [...cur, { id, message, variant }]);
    setTimeout(() => setToasts((cur) => cur.filter((t) => t.id !== id)), 5000);
  }, []);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(FLASH_KEY);
      if (!raw) return;
      sessionStorage.removeItem(FLASH_KEY);
      const { message, variant } = JSON.parse(raw) as { message: string; variant?: Variant };
      // Deferred a tick: showing it is an external sync (storage → UI), not render-derived state.
      if (message) setTimeout(() => toast(message, variant), 0);
    } catch {
      // Unreadable or malformed: drop it silently.
    }
  }, [toast]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
        data-testid="toast-region"
        aria-live="polite"
        role="status"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            data-testid="toast"
            className={`pointer-events-auto rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur ${
              t.variant === "error"
                ? "border-destructive/40 bg-destructive/10 text-foreground"
                : "border-border bg-popover text-popover-foreground"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
