import React from "react";
import { motion } from "framer-motion";
import { formatVal } from "@/utils/format";

interface ForecastCardData {
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

interface ForecastCardsProps {
  selectedGroup: string;
  latestForecast: ForecastCardData | null;
  isLoading: boolean;
}

export function ForecastCards({ selectedGroup, latestForecast, isLoading }: ForecastCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass-card rounded-2xl p-6 h-40 animate-pulse flex flex-col gap-3">
            <div className="h-4 bg-white/5 rounded-md w-24" />
            <div className="h-8 bg-white/5 rounded-md w-36" />
            <div className="h-3 bg-white/5 rounded-md w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (!latestForecast) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* +2 Card */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card rounded-2xl p-6 border-l-4 border-l-[#38bdf8] flex flex-col gap-4 relative overflow-hidden"
      >
        <div className="flex justify-between items-start">
          <span className="text-xs font-black tracking-widest text-[#38bdf8] uppercase bg-[#38bdf8]/10 px-2.5 py-1 rounded-md">
            {selectedGroup} +2 ボーダー
          </span>
          <span className="text-[10px] text-slate-500 font-mono font-bold">
            対象日: {latestForecast.rawDate}
          </span>
        </div>
        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-3xl font-black font-mono text-slate-900 dark:text-white tracking-tight">
            {formatVal(latestForecast["+2_p50"])}
          </span>
          <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+2_p10"])}
            </span>
          </div>
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+2_p90"])}
            </span>
          </div>
        </div>
      </motion.div>

      {/* +4 Card */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card rounded-2xl p-6 border-l-4 border-l-[#34d399] flex flex-col gap-4 relative overflow-hidden"
      >
        <div className="flex justify-between items-start">
          <span className="text-xs font-black tracking-widest text-[#34d399] uppercase bg-[#34d399]/10 px-2.5 py-1 rounded-md">
            {selectedGroup} +4 ボーダー
          </span>
          <span className="text-[10px] text-slate-500 font-mono font-bold">
            対象日: {latestForecast.rawDate}
          </span>
        </div>
        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-3xl font-black font-mono text-slate-900 dark:text-white tracking-tight">
            {formatVal(latestForecast["+4_p50"])}
          </span>
          <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+4_p10"])}
            </span>
          </div>
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+4_p90"])}
            </span>
          </div>
        </div>
      </motion.div>

      {/* +6 Card */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-card rounded-2xl p-6 border-l-4 border-l-[#a855f7] flex flex-col gap-4 relative overflow-hidden"
      >
        <div className="flex justify-between items-start">
          <span className="text-xs font-black tracking-widest text-[#a855f7] uppercase bg-[#a855f7]/10 px-2.5 py-1 rounded-md">
            {selectedGroup} +6 ボーダー
          </span>
          <span className="text-[10px] text-slate-500 font-mono font-bold">
            対象日: {latestForecast.rawDate}
          </span>
        </div>
        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-3xl font-black font-mono text-slate-900 dark:text-white tracking-tight">
            {formatVal(latestForecast["+6_p50"])}
          </span>
          <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+6_p10"])}
            </span>
          </div>
          <div>
            <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
            <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
              {formatVal(latestForecast["+6_p90"])}
            </span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
