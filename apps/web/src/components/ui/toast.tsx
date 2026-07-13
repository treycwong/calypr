"use client";

import {
  createContext,
  useCallback,
  useContext,
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

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: Variant = "default") => {
    const id = Date.now() + Math.random();
    setToasts((cur) => [...cur, { id, message, variant }]);
    setTimeout(() => setToasts((cur) => cur.filter((t) => t.id !== id)), 5000);
  }, []);

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
