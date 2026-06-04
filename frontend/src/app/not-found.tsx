import React from "react";
import Link from "next/link";
import { HelpCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6 text-center">
      <div className="glass-card rounded-2xl p-8 max-w-md w-full border border-white/10 flex flex-col items-center gap-5">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
          <HelpCircle className="text-indigo-400 w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-black text-white">404 - ページが見つかりません</h2>
          <p className="text-xs text-slate-400 leading-relaxed mt-2">
            お探しのページは削除されたか、名前が変更された可能性があります。
          </p>
        </div>
        <Link
          href="/"
          className="w-full bg-slate-900 hover:bg-slate-800 text-white border border-white/10 py-2 rounded-xl text-xs font-black flex items-center justify-center transition-colors"
        >
          ホームへ戻る
        </Link>
      </div>
    </div>
  );
}
