import React from "react";
import { CheckCircle2 } from "lucide-react";
import { PublicationCandidate } from "@/types/api";

interface CandidatesTableProps {
  candidates: PublicationCandidate[];
  onPromoteBeta: (target: string) => void;
}

export function CandidatesTable({ candidates, onPromoteBeta }: CandidatesTableProps) {
  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        beta 公開候補ターゲット（一括公開可能）
      </h3>
      
      <div className="overflow-x-auto custom-scrollbar border border-white/5 rounded-xl">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950 border-b border-white/5 text-slate-400 font-extrabold uppercase">
              <th className="py-3 px-4">ターゲット</th>
              <th className="py-3 px-4">品質合格</th>
              <th className="py-3 px-4">改善率</th>
              <th className="py-3 px-4">CV MAE</th>
              <th className="py-3 px-4">理由</th>
              <th className="py-3 px-4 text-right">公開操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300 font-mono">
            {candidates.length > 0 ? (
              candidates.map((cand) => (
                <tr key={cand.target} className="hover:bg-white/5 transition-colors">
                  <td className="py-3.5 px-4 font-sans font-extrabold text-white">{cand.target}</td>
                  <td className="py-3.5 px-4 font-sans">
                    {cand.eligible ? (
                      <span className="text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded">Eligible</span>
                    ) : (
                      <span className="text-slate-500 bg-slate-800 px-2 py-0.5 rounded">Not Eligible</span>
                    )}
                  </td>
                  <td className="py-3.5 px-4">
                    {cand.improvement_rate == null ? "—" : `${(cand.improvement_rate * 100).toFixed(1)}%`}
                  </td>
                  <td className="py-3.5 px-4">{cand.cv_mae == null ? "—" : cand.cv_mae.toFixed(2)}</td>
                  <td className="py-3.5 px-4 font-sans text-slate-400">{(cand.reasons || []).join("; ") || "—"}</td>
                  <td className="py-3.5 px-4 text-right font-sans">
                    <button
                      onClick={() => onPromoteBeta(cand.target)}
                      disabled={!cand.eligible}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-30 px-3 py-1 rounded font-bold transition-colors cursor-pointer"
                    >
                      正式公開
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-500 font-sans">
                  公開可能な候補ターゲットはありません。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
