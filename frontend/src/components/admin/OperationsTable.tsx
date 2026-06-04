import React from "react";
import { Activity } from "lucide-react";
import { TargetOperationRow } from "@/types/api";

interface OperationsTableProps {
  operationRows: TargetOperationRow[];
  onTogglePublish: (target: string, currentPublish: boolean) => void;
}

export function OperationsTable({ operationRows, onTogglePublish }: OperationsTableProps) {
  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
        <Activity className="w-4 h-4 text-purple-400" />
        全ターゲット台帳・公開スイッチ
      </h3>

      <div className="overflow-x-auto custom-scrollbar border border-white/5 rounded-xl max-h-[500px]">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950 border-b border-white/5 text-slate-400 font-extrabold uppercase sticky top-0">
              <th className="py-3 px-4">ターゲット</th>
              <th className="py-3 px-4">状態</th>
              <th className="py-3 px-4">公開状況</th>
              <th className="py-3 px-4">欠損率</th>
              <th className="py-3 px-4">モデル学習</th>
              <th className="py-3 px-4">CV MAE</th>
              <th className="py-3 px-4">改善率</th>
              <th className="py-3 px-4">最終学習日</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300 font-mono">
            {operationRows.map((row) => (
              <tr key={row.target} className="hover:bg-white/5 transition-colors">
                <td className="py-3.5 px-4 font-sans font-extrabold text-white">{row.target}</td>
                <td className="py-3.5 px-4 font-sans text-xs">
                  {row.status === "ready" && <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-bold">ready</span>}
                  {row.status === "beta" && <span className="text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded font-bold">beta</span>}
                  {row.status === "blocked" && <span className="text-red-400 bg-red-500/10 px-2 py-0.5 rounded font-bold">blocked</span>}
                </td>
                <td className="py-3.5 px-4 font-sans">
                  <input
                    type="checkbox"
                    checked={row.publish}
                    disabled={row.status === "blocked"}
                    onChange={() => onTogglePublish(row.target, row.publish)}
                    className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500 bg-slate-900 cursor-pointer disabled:opacity-40"
                  />
                </td>
                <td className="py-3.5 px-4">{(row.missing_rate * 100).toFixed(1)}%</td>
                <td className="py-3.5 px-4 font-sans">
                  {row.has_active_model ? (
                    <span className="text-emerald-400 font-bold">Active</span>
                  ) : (
                    <span className="text-slate-500">Unlearned</span>
                  )}
                </td>
                <td className="py-3.5 px-4">{row.cv_mae == null ? "—" : row.cv_mae.toFixed(2)}</td>
                <td className="py-3.5 px-4">
                  {row.improvement_rate == null ? "—" : `${(row.improvement_rate * 100).toFixed(1)}%`}
                </td>
                <td className="py-3.5 px-4 text-slate-500">{row.last_trained_at || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
