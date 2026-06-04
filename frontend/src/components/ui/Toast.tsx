import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

interface ToastProps {
  message: string;
  type: "success" | "error" | "info";
  onClose: () => void;
  duration?: number;
}

export function Toast({ message, type, onClose, duration = 4000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
    error: <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />,
    info: <Info className="w-4 h-4 text-indigo-400 shrink-0" />,
  };

  const borders = {
    success: "border-emerald-500/20 bg-slate-900/90 text-emerald-200",
    error: "border-red-500/20 bg-slate-900/90 text-red-200",
    info: "border-indigo-500/20 bg-slate-900/90 text-indigo-200",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md max-w-sm ${borders[type]}`}
    >
      {icons[type]}
      <span className="text-xs font-bold font-sans">{message}</span>
      <button
        onClick={onClose}
        className="rounded-lg p-0.5 hover:bg-white/5 text-slate-400 hover:text-white transition-colors ml-auto shrink-0"
        aria-label="閉じる"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

interface ToastContainerProps {
  toast: { message: string; type: "success" | "error" | "info" } | null;
  onClose: () => void;
}

export function ToastContainer({ toast, onClose }: ToastContainerProps) {
  return (
    <AnimatePresence>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={onClose}
        />
      )}
    </AnimatePresence>
  );
}
