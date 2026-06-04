import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sun, Cloud, CloudRain, CloudLightning, RefreshCw, Calendar, Layers } from "lucide-react";
import { formatVal } from "@/utils/format";
import { DeepPredictionResponse, PredictionStep } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
const TARGET_GROUPS = ["S3", "S2", "S1", "A3", "A2", "A1", "B3", "B2", "B1", "C5", "C4", "C3"];

interface WeatherForecastProps {
  selectedGroup: string;
  predictionData: DeepPredictionResponse | null;
  isLoading: boolean;
  dateRange: { from: string; to: string };
  predictionMode: "hybrid" | "tft_only";
  wTft: number;
  selectedDate?: string | null;
  onDateChange?: (date: string) => void;
  onGroupChange?: (group: string) => void;
}

// Weather threshold categorizer
const getWeatherInfo = (deviation: number) => {
  if (deviation < -0.15) {
    return {
      icon: Sun,
      label: "快晴",
      colorClass: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
      glowClass: "from-emerald-500/20 to-transparent",
      desc: "穏やか。＋6ボーダーは過去平均より低く、目標を突破しやすい状態です。",
    };
  } else if (deviation <= 0.10) {
    return {
      icon: Cloud,
      label: "薄曇",
      colorClass: "text-slate-600 dark:text-slate-400 bg-slate-500/10 border-slate-500/20",
      glowClass: "from-slate-500/10 to-transparent",
      desc: "平常通り。＋6ボーダーは平年並みです。着実なポイント積み上げを。",
    };
  } else if (deviation <= 0.25) {
    return {
      icon: CloudRain,
      label: "雨模様",
      colorClass: "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20",
      glowClass: "from-amber-500/20 to-transparent",
      desc: "高め。＋6ボーダーが普段より高騰し始めています。配信時間を長めにとるなどの対策を。",
    };
  } else {
    return {
      icon: CloudLightning,
      label: "雷雨警報",
      colorClass: "text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20",
      glowClass: "from-rose-500/25 to-transparent",
      desc: "警戒。＋6ボーダーが普段より大幅に上昇しています。目標突破には十分な備えと団結が必要です。",
    };
  }
};

interface AllRanksWeatherData {
  group: string;
  weather: ReturnType<typeof getWeatherInfo>;
  deviation: number;
  p50: number;
  historicalMean: number;
}

export function WeatherForecast({
  selectedGroup,
  predictionData,
  isLoading,
  dateRange,
  predictionMode,
  wTft,
  selectedDate,
  onDateChange,
  onGroupChange,
}: WeatherForecastProps) {
  const [activeTab, setActiveTab] = useState<"weekly" | "all-ranks">("weekly");
  const [allRanksData, setAllRanksData] = useState<AllRanksWeatherData[]>([]);
  const [isAllRanksLoading, setIsAllRanksLoading] = useState(false);

  // Helper: Calculate deviation for a given step and group (+6 tier)
  const getStepDeviation = (step: PredictionStep, group: string) => {
    const tKey = `${group} +6`;
    const pred = step.predictions[tKey];

    if (pred && pred.historical_mean) {
      const deviation = (pred.p50 - pred.historical_mean) / pred.historical_mean;
      return {
        deviation,
        p50: pred.p50,
        historicalMean: pred.historical_mean,
      };
    }

    return {
      deviation: 0,
      p50: 0,
      historicalMean: 0,
    };
  };

  // Fetch all ranks today's weather data
  const fetchAllRanksToday = useCallback(async () => {
    if (dateRange.from === "" || dateRange.to === "") return;
    setIsAllRanksLoading(true);
    try {
      const promises = TARGET_GROUPS.map(async (group) => {
        const url = `${API_BASE}/deep/predictions?target_group=${encodeURIComponent(group)}&from_date=${encodeURIComponent(dateRange.from)}&to_date=${encodeURIComponent(dateRange.to)}&use_hybrid=${predictionMode === "hybrid"}&w_tft=${wTft}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Failed to fetch for ${group}`);
        const data = (await response.json()) as DeepPredictionResponse;
        
        if (data.steps && data.steps.length > 0) {
          const todayStep = data.steps[0]; // First day represents today
          const stats = getStepDeviation(todayStep, group);
          return {
            group,
            weather: getWeatherInfo(stats.deviation),
            deviation: stats.deviation,
            p50: stats.p50,
            historicalMean: stats.historicalMean,
          };
        }
        return null;
      });

      const results = await Promise.all(promises);
      const filtered = results.filter((r): r is AllRanksWeatherData => r !== null);
      setAllRanksData(filtered);
    } catch (e) {
      console.error("Error loading all ranks weather:", e);
    } finally {
      setIsAllRanksLoading(false);
    }
  }, [dateRange, predictionMode, wTft]);

  useEffect(() => {
    if (activeTab === "all-ranks") {
      const timer = setTimeout(() => {
        fetchAllRanksToday();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [activeTab, fetchAllRanksToday]);

  const renderWeatherIcon = (IconComponent: typeof Sun, colorClass: string) => {
    return (
      <div className={`p-3 rounded-xl border ${colorClass} flex items-center justify-center shadow-lg`}>
        <IconComponent className="w-6 h-6 animate-pulse" />
      </div>
    );
  };

  return (
    <section className="glass-card rounded-2xl p-6 relative overflow-hidden flex flex-col gap-6">
      {/* Background soft light */}
      <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-purple-500/10 blur-[60px] pointer-events-none" />

      {/* Header controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4 z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md">
            <Sun className="text-white w-4.5 h-4.5" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">＋6 ボーダー気象台</h3>
            <p className="text-[10px] text-slate-600 dark:text-slate-400">過去実績との比較に基づく戦略的難易度予報</p>
          </div>
        </div>

        {/* Tab switchers */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-200/60 dark:bg-slate-950/60 border border-slate-300/30 dark:border-white/5 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab("weekly")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
              activeTab === "weekly"
                ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            {selectedGroup}の週間予報
          </button>
          <button
            onClick={() => setActiveTab("all-ranks")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
              activeTab === "all-ranks"
                ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            全ランクの本日予報
          </button>
        </div>
      </div>

      {/* Main content tabpanel */}
      <div className="z-10">
        <AnimatePresence mode="wait">
          {activeTab === "weekly" ? (
            <motion.div
              key="weekly"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex flex-col gap-6"
            >
              {isLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-7 gap-4 animate-pulse">
                  {[...Array(7)].map((_, i) => (
                    <div key={i} className="bg-white/5 rounded-xl p-4 h-32 flex flex-col gap-2" />
                  ))}
                </div>
              ) : predictionData && predictionData.steps && predictionData.steps.length > 0 ? (
                <div>
                  {/* Current Day Focus Summary Banner */}
                  {(() => {
                    const activeStep = predictionData.steps.find((s) => s.date === selectedDate) || predictionData.steps[0];
                    const stats = getStepDeviation(activeStep, selectedGroup);
                    const weather = getWeatherInfo(stats.deviation);
                    return (
                      <div className={`mb-6 p-4 rounded-xl border bg-gradient-to-r ${weather.glowClass} border-white/5 flex flex-col md:flex-row items-center justify-between gap-4`}>
                        <div className="flex items-center gap-4">
                          {renderWeatherIcon(weather.icon, weather.colorClass)}
                          <div>
                            <span className="text-[10px] text-purple-600 dark:text-purple-400 uppercase font-black tracking-wider">選択日の＋6気候状況 ({activeStep.date})</span>
                            <h4 className="text-base font-black text-slate-900 dark:text-white flex items-center gap-2 mt-0.5">
                              {selectedGroup}グループ: <span className={weather.colorClass.split(" ")[0]}>{weather.label}</span>
                              <span className="text-xs font-bold text-slate-500 dark:text-slate-400 font-mono">({stats.deviation >= 0 ? "+" : ""}{(stats.deviation * 100).toFixed(1)}%)</span>
                            </h4>
                            <p className="text-xs text-slate-700 dark:text-slate-300 mt-1 leading-relaxed">{weather.desc}</p>
                          </div>
                        </div>
                        <div className="text-right flex flex-col items-end border-t md:border-t-0 md:border-l border-white/5 pt-3 md:pt-0 md:pl-6 w-full md:w-auto">
                          <span className="text-[10px] text-slate-500 font-bold">＋6 予測値 / 過去平均</span>
                          <span className="text-lg font-black font-mono text-slate-950 dark:text-white mt-1">
                            {formatVal(stats.p50)} <span className="text-xs font-normal text-slate-500">/ {formatVal(stats.historicalMean)}</span>
                          </span>
                        </div>
                      </div>
                    );
                  })()}

                  {/* 7-Day Forecast Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-4">
                    {predictionData.steps.map((step) => {
                      const stats = getStepDeviation(step, selectedGroup);
                      const weather = getWeatherInfo(stats.deviation);
                      const Icon = weather.icon;
                      const isSelected = step.date === selectedDate;
                      
                      // Format date to MM/DD (Day of week)
                      const dateObj = new Date(step.date);
                      const daysJp = ["日", "月", "火", "水", "木", "金", "土"];
                      const formattedDate = `${dateObj.getMonth() + 1}/${dateObj.getDate()} (${daysJp[dateObj.getDay()]})`;

                      return (
                        <div
                          key={step.date}
                          onClick={() => onDateChange?.(step.date)}
                          className={`border rounded-xl p-4 flex flex-col items-center text-center transition-all duration-300 group cursor-pointer ${
                            isSelected
                              ? "bg-indigo-50/80 dark:bg-indigo-950/25 border-indigo-500/50 dark:border-indigo-500/50 ring-2 ring-indigo-500/20 shadow-md scale-[1.02]"
                              : "bg-slate-100/50 dark:bg-slate-950/40 border-slate-200 dark:border-white/5 hover:border-slate-300 dark:hover:border-white/10 hover:bg-slate-200/50 dark:hover:bg-slate-950/60"
                          }`}
                        >
                          <span className="text-[10px] font-extrabold text-slate-500 dark:text-slate-400 mb-2">{formattedDate}</span>
                          <div className={`p-2.5 rounded-lg border ${weather.colorClass} mb-2.5 group-hover:scale-110 transition-transform duration-300 shadow`}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <span className={`text-xs font-black ${weather.colorClass.split(" ")[0]} mb-1`}>{weather.label}</span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {stats.deviation >= 0 ? "+" : ""}{(stats.deviation * 100).toFixed(0)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-xs text-slate-500">予測データが存在しません。</div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="all-ranks"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex flex-col gap-6"
            >
              {isAllRanksLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-400">
                  <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
                  <span className="text-xs font-bold">全ランクのデータを集計中...</span>
                </div>
              ) : allRanksData.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                  {allRanksData.map((data) => {
                    const Icon = data.weather.icon;
                    return (
                      <div
                        key={data.group}
                        onClick={() => {
                          onGroupChange?.(data.group);
                          setActiveTab("weekly");
                        }}
                        className={`border rounded-xl p-4 flex flex-col items-center text-center transition-all duration-300 bg-slate-100/50 dark:bg-slate-950/40 border-slate-200 dark:border-white/5 hover:bg-slate-200/50 dark:hover:bg-slate-950/60 cursor-pointer hover:border-indigo-500/50 hover:scale-[1.02] active:scale-[0.98]`}
                      >
                        <span className="text-xs font-black text-slate-900 dark:text-white mb-2">{data.group} グループ</span>
                        <div className={`p-2.5 rounded-lg border ${data.weather.colorClass} mb-2.5 shadow`}>
                          <Icon className="w-5 h-5" />
                        </div>
                        <span className={`text-xs font-black ${data.weather.colorClass.split(" ")[0]} mb-0.5`}>{data.weather.label}</span>
                        <span className="text-[10px] font-mono font-bold text-slate-500 mb-2">
                          {data.deviation >= 0 ? "+" : ""}{(data.deviation * 100).toFixed(0)}%
                        </span>
                        <div className="w-full border-t border-white/5 pt-2 mt-1 flex flex-col text-[10px] font-mono text-slate-600 dark:text-slate-400 leading-tight">
                          <span>予測: {formatVal(data.p50)}</span>
                          <span className="text-[9px] text-slate-400 dark:text-slate-600">平均: {formatVal(data.historicalMean)}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8 text-xs text-slate-500">データを読み込めませんでした。</div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
