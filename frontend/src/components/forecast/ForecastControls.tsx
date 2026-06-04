import React from "react";
import { Sliders, RotateCcw } from "lucide-react";
import { TARGET_GROUPS } from "@/hooks/useForecast";
import { DateRangePicker } from "@/components/ui/DateRangePicker";

interface ForecastControlsProps {
  selectedGroup: string;
  onGroupChange: (group: string) => void;
  predictionMode: "hybrid" | "tft_only";
  onPredictionModeChange: (mode: "hybrid" | "tft_only") => void;
  wTft: number;
  onWTftChange: (val: number) => void;
  dateRange: { from: string; to: string };
  onDateRangeChange: (range: { from: string; to: string }) => void;
}

export function ForecastControls({
  selectedGroup,
  onGroupChange,
  predictionMode,
  onPredictionModeChange,
  wTft,
  onWTftChange,
  dateRange,
  onDateRangeChange,
}: ForecastControlsProps) {
  return (
    <div className="flex flex-col gap-8">
      {/* Rank Group Filter Settings */}
      <section className="glass-card rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex flex-col gap-1.5">
          <h2 className="text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-purple-500 dark:text-purple-400" />
            表示対象の設定
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            所属するランクグループを選択してください。対応する「+2」「+4」「+6」予測が表示されます。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-slate-500 dark:text-slate-500 font-bold uppercase tracking-wider">所属ランク</label>
            <select
              value={selectedGroup}
              onChange={(e) => onGroupChange(e.target.value)}
              className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white font-bold outline-none focus:border-purple-500 transition-colors"
            >
              {TARGET_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {g} グループ
                </option>
              ))}
            </select>
          </div>

          <DateRangePicker
            dateRange={dateRange}
            onDateRangeChange={onDateRangeChange}
          />
        </div>
      </section>

      {/* Hybrid & Blending controls */}
      <section className="glass-card rounded-2xl p-6 flex flex-col md:flex-row gap-6 items-start md:items-center">
        <div className="flex-1">
          <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">予測モデル構成</h3>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
            過去の類似パターン（曜日やイベント経過日数）を捉える長期モデルと、直近の推移に追従しやすい短期モデルの組み合わせを調整します。
          </p>
        </div>
        
        <div className="flex flex-wrap gap-4 items-center w-full md:w-auto">
          <div className="flex flex-col gap-1 w-full md:w-56">
            <label className="text-[10px] text-slate-500 dark:text-slate-500 font-bold uppercase tracking-wider">予測モード</label>
            <select
              value={predictionMode}
              onChange={(e) => onPredictionModeChange(e.target.value as "hybrid" | "tft_only")}
              className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white font-bold outline-none focus:border-purple-500 transition-colors"
            >
              <option value="hybrid">自動バランス調整 (推奨)</option>
              <option value="tft_only">長期トレンド重視</option>
            </select>
          </div>

          {predictionMode === "hybrid" && (
            <div className="flex flex-col gap-1 w-full md:w-64">
              <div className="flex justify-between items-center text-[10px] font-bold text-slate-500 dark:text-slate-500 uppercase tracking-wider">
                <span className="flex items-center gap-1.5">
                  配分バランス
                  {Math.abs(wTft - 0.6) > 0.01 && (
                    <button
                      onClick={() => onWTftChange(0.6)}
                      className="text-purple-500 hover:text-purple-600 dark:text-purple-400 dark:hover:text-purple-300 transition-colors flex items-center gap-0.5 font-bold normal-case cursor-pointer"
                      title="初期値 (60%) に戻す"
                    >
                      <RotateCcw className="w-2.5 h-2.5 animate-spin-once" />
                      リセット
                    </button>
                  )}
                </span>
                <span className="text-purple-600 dark:text-purple-400 font-mono font-black">
                  TFT: {(wTft * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={wTft}
                onChange={(e) => onWTftChange(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-200 dark:bg-slate-900 rounded-lg appearance-none cursor-pointer accent-purple-500 mt-2.5"
              />
              <div className="flex justify-between text-[9px] font-semibold text-slate-400 dark:text-slate-500 mt-1">
                <span>直近の動きを重視</span>
                <span>長期トレンド重視</span>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
