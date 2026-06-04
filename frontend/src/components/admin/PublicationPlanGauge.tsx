import React from "react";
import { CheckCircle2 } from "lucide-react";
import { PublicationPlan } from "@/types/api";

interface PublicationPlanGaugeProps {
  publicationPlan: PublicationPlan | null;
}

export function PublicationPlanGauge({ publicationPlan }: PublicationPlanGaugeProps) {
  if (!publicationPlan) return null;

  const percentage = Math.round((publicationPlan.published_count / publicationPlan.goal) * 100);

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="glass-card rounded-2xl p-6 flex flex-col gap-3">
        <span className="text-[10px] font-black tracking-wider text-purple-400 uppercase">
          M3 段階公開計画の進捗
        </span>
        <div className="flex justify-between items-baseline mt-1">
          <span className="text-4xl font-black text-white font-mono">
            {publicationPlan.published_count}
            <span className="text-sm text-slate-500 font-sans font-bold"> / {publicationPlan.goal} ターゲット</span>
          </span>
          <span className="text-xs text-emerald-400 font-bold bg-emerald-500/10 px-2.5 py-1 rounded-md">
            目標達成率: {percentage}%
          </span>
        </div>
        <div className="w-full bg-slate-950 rounded-full h-2 mt-2">
          <div
            className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 h-2 rounded-full"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <p className="text-[10px] text-slate-400 leading-tight mt-1">
          ready公開: {publicationPlan.ready_published} | beta公開: {publicationPlan.beta_published} | 残り枠: {publicationPlan.remaining_slots}
        </p>
      </div>

      <div className="glass-card rounded-2xl p-6 flex flex-col gap-3 justify-center">
        <span className="text-[10px] font-black tracking-wider text-indigo-400 uppercase">
          クオリティチェック結果
        </span>
        <div className="flex items-center gap-3 mt-1.5">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
          <div>
            <p className="text-sm font-extrabold text-white">データパイプライン正常稼働中</p>
            <p className="text-[10px] text-slate-400 leading-tight">品質チェックを全ターゲットがパスしています</p>
          </div>
        </div>
      </div>
    </section>
  );
}
