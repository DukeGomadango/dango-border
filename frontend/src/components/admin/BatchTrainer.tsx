import React from "react";
import { Terminal, RefreshCw } from "lucide-react";

interface BatchTrainerProps {
  trainStatus: string | null;
  isTraining: boolean;
  onBatchTrain: () => void;
}

export function BatchTrainer({ trainStatus, isTraining, onBatchTrain }: BatchTrainerProps) {
  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
        <Terminal className="w-4 h-4 text-purple-400" />
        モデル一括学習
      </h3>
      <p className="text-xs text-slate-400">
        新しく投入したデータをもとに、すべての公開ターゲットモデルを自動再学習させます。
      </p>
      
      <button
        onClick={onBatchTrain}
        disabled={isTraining}
        className="w-full bg-slate-900 border border-white/10 hover:border-white/20 text-white disabled:opacity-40 font-black py-2.5 rounded-xl text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer"
      >
        {isTraining ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <PlayIcon className="w-3.5 h-3.5" />}
        一括再学習ジョブを起動
      </button>

      {trainStatus && (
        <div className="bg-slate-950 border border-white/5 rounded-xl p-3 text-[10px] font-mono leading-relaxed text-slate-400 max-h-40 overflow-y-auto custom-scrollbar">
          {trainStatus}
        </div>
      )}
    </section>
  );
}

// Simple Helper Component
function PlayIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}
