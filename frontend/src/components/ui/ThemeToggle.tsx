"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { motion, AnimatePresence } from "framer-motion";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="w-9 h-9 rounded-xl bg-slate-200/20 dark:bg-slate-800/20 border border-slate-200/10 dark:border-slate-800/10" />
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="relative w-9 h-9 rounded-xl border border-slate-200/50 dark:border-white/10 bg-white/40 dark:bg-slate-950/40 hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 backdrop-blur-md transition-colors duration-300 flex items-center justify-center cursor-pointer overflow-hidden outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      aria-label="テーマ切り替え"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={isDark ? "dark" : "light"}
          initial={{ y: 20, opacity: 0, rotate: -40 }}
          animate={{ y: 0, opacity: 1, rotate: 0 }}
          exit={{ y: -20, opacity: 0, rotate: 40 }}
          transition={{ duration: 0.25, ease: "easeInOut" }}
          className="flex items-center justify-center w-full h-full"
        >
          {isDark ? (
            <Sun className="h-4.5 w-4.5 text-amber-400" />
          ) : (
            <Moon className="h-4.5 w-4.5 text-indigo-600" />
          )}
        </motion.div>
      </AnimatePresence>
    </button>
  );
}
