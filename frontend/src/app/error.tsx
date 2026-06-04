"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error boundary:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6 text-center">
      <div className="glass-card rounded-2xl p-8 max-w-md w-full border border-white/10 flex flex-col items-center gap-5">
        <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center border border-red-500/20">
          <AlertTriangle className="text-red-400 w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-black text-white">エラーが発生しました</h2>
          <p className="text-xs text-slate-400 leading-relaxed mt-2">
            システムエラーが発生しました。しばらく時間をおいてもう一度お試しください。
          </p>
        </div>
        <button
          onClick={reset}
          className="w-full bg-slate-900 hover:bg-slate-800 text-white border border-white/10 py-2 rounded-xl text-xs font-black flex items-center justify-center gap-2 cursor-pointer transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          再試行
        </button>
      </div>
    </div>
  );
}
