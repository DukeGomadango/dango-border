import React from "react";
import { formatVal } from "@/utils/format";

interface TableRow {
  rawDate: string;
  "+2_p10": number;
  "+2_p50": number;
  "+2_p90": number;
  "+4_p10": number;
  "+4_p50": number;
  "+4_p90": number;
  "+6_p10": number;
  "+6_p50": number;
  "+6_p90": number;
}

interface ForecastTableProps {
  chartData: TableRow[];
  modelVersion?: string;
  modelType?: string;
  blendingStatus?: string;
}

export function ForecastTable({
  chartData,
  modelVersion,
  modelType,
  blendingStatus,
}: ForecastTableProps) {
  return (
    <section className="glass-card rounded-2xl p-6">
      <h3 className="text-sm font-extrabold text-slate-900 dark:text-white mb-4">予測値データ一覧</h3>
      <div className="overflow-x-auto custom-scrollbar border border-slate-200 dark:border-white/5 rounded-xl">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-100/80 dark:bg-slate-950/80 border-b border-slate-200 dark:border-white/5 text-slate-600 dark:text-slate-400 font-extrabold uppercase">
              <th className="py-3.5 px-4">日付</th>
              <th className="py-3.5 px-4 text-center border-l border-slate-200 dark:border-white/5" colSpan={3}>
                +2 ボーダー
              </th>
              <th className="py-3.5 px-4 text-center border-l border-slate-200 dark:border-white/5" colSpan={3}>
                +4 ボーダー
              </th>
              <th className="py-3.5 px-4 text-center border-l border-slate-200 dark:border-white/5" colSpan={3}>
                +6 ボーダー
              </th>
            </tr>
            <tr className="bg-slate-50/40 dark:bg-slate-950/40 border-b border-slate-200 dark:border-white/5 text-slate-500 font-bold text-[10px]">
              <th className="py-2.5 px-4"></th>
              <th className="py-2.5 px-3 text-right border-l border-slate-200 dark:border-white/5">下振れ</th>
              <th className="py-2.5 px-3 text-right text-[#38bdf8] font-extrabold">目安</th>
              <th className="py-2.5 px-3 text-right">上振れ</th>
              <th className="py-2.5 px-3 text-right border-l border-slate-200 dark:border-white/5">下振れ</th>
              <th className="py-2.5 px-3 text-right text-[#34d399] font-extrabold">目安</th>
              <th className="py-2.5 px-3 text-right">上振れ</th>
              <th className="py-2.5 px-3 text-right border-l border-slate-200 dark:border-white/5">下振れ</th>
              <th className="py-2.5 px-3 text-right text-[#a855f7] font-extrabold">目安</th>
              <th className="py-2.5 px-3 text-right">上振れ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-white/5 font-mono text-slate-700 dark:text-slate-300">
            {chartData.map((row) => (
              <tr key={row.rawDate} className="hover:bg-slate-100/30 dark:hover:bg-white/5 transition-colors">
                <td className="py-3.5 px-4 font-sans font-extrabold text-slate-900 dark:text-white">
                  {row.rawDate}
                </td>
                <td className="py-3.5 px-3 text-right border-l border-slate-200 dark:border-white/5 text-slate-500">
                  {formatVal(row["+2_p10"])}
                </td>
                <td className="py-3.5 px-3 text-right font-black text-slate-950 dark:text-white">
                  {formatVal(row["+2_p50"])}
                </td>
                <td className="py-3.5 px-3 text-right text-slate-500">
                  {formatVal(row["+2_p90"])}
                </td>
                <td className="py-3.5 px-3 text-right border-l border-slate-200 dark:border-white/5 text-slate-500">
                  {formatVal(row["+4_p10"])}
                </td>
                <td className="py-3.5 px-3 text-right font-black text-slate-950 dark:text-white">
                  {formatVal(row["+4_p50"])}
                </td>
                <td className="py-3.5 px-3 text-right text-slate-500">
                  {formatVal(row["+4_p90"])}
                </td>
                <td className="py-3.5 px-3 text-right border-l border-slate-200 dark:border-white/5 text-slate-500">
                  {formatVal(row["+6_p10"])}
                </td>
                <td className="py-3.5 px-3 text-right font-black text-slate-950 dark:text-white">
                  {formatVal(row["+6_p50"])}
                </td>
                <td className="py-3.5 px-3 text-right text-slate-500">
                  {formatVal(row["+6_p90"])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {modelVersion && (
        <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-4 text-right">
          モデルバージョン: {modelVersion} ({modelType})
          {blendingStatus ? ` | 構成: ${blendingStatus}` : ""}
        </p>
      )}
    </section>
  );
}
