"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { ToastItem } from "@/lib/types";


interface ToastContextValue {
  pushToast: (title: string, tone?: ToastItem["tone"]) => void;
}


const ToastContext = createContext<ToastContextValue | null>(null);


export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = useCallback((title: string, tone: ToastItem["tone"] = "info") => {
    const id = crypto.randomUUID();
    setToasts((current) => [...current, { id, title, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 3200);
  }, []);

  const value = useMemo(() => ({ pushToast }), [pushToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-3">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`rounded-2xl border px-4 py-3 text-sm shadow-glow ${
                toast.tone === "error"
                  ? "border-red-300 bg-red-50 text-red-900 dark:border-red-900/40 dark:bg-red-950/70 dark:text-red-100"
                  : toast.tone === "success"
                    ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/70 dark:text-emerald-100"
                    : "border-stone-200 bg-white/90 text-stone-900 dark:border-white/10 dark:bg-stone-900/90 dark:text-stone-100"
              }`}
            >
              {toast.title}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}


export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
