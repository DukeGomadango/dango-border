"use client";

import React from "react";
import {
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  CartesianGrid,
} from "recharts";
import { formatVal } from "@/utils/format";

interface ChartRow {
  rawDate: string;
  date: string;
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

interface RechartsClickPayload {
  payload: {
    rawDate: string;
    [key: string]: unknown;
  };
}

interface RechartsClickEvent {
  activePayload?: RechartsClickPayload[];
  activeLabel?: string;
}

interface ForecastChartProps {
  chartData: ChartRow[];
  isLoading: boolean;
  onDateClick?: (rawDate: string) => void;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      date: string;
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
    };
  }>;
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="glass-card rounded-xl p-3.5 text-xs border border-slate-200/50 dark:border-white/10 shadow-xl bg-white/95 dark:bg-[#060913]/95 backdrop-blur-md text-slate-800 dark:text-slate-200 min-w-[210px] flex flex-col gap-2.5">
        <p className="font-extrabold text-slate-900 dark:text-white border-b border-slate-200 dark:border-white/5 pb-1">{data.rawDate}</p>
        
        {/* +2 Group */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-black text-[#38bdf8] uppercase tracking-wider">+2 ボーダー</span>
          <div className="flex justify-between gap-4 items-baseline">
            <span className="text-slate-500 dark:text-slate-400">目安:</span>
            <span className="font-mono font-black text-[#38bdf8] text-sm">{formatVal(data["+2_p50"])}</span>
          </div>
          <div className="flex justify-between gap-4 text-[10px] text-slate-450 dark:text-slate-500">
            <span>範囲:</span>
            <span className="font-mono">{formatVal(data["+2_p10"])} 〜 {formatVal(data["+2_p90"])}</span>
          </div>
        </div>

        {/* +4 Group */}
        <div className="flex flex-col gap-0.5 border-t border-slate-200 dark:border-white/5 pt-2">
          <span className="text-[10px] font-black text-[#34d399] uppercase tracking-wider">+4 ボーダー</span>
          <div className="flex justify-between gap-4 items-baseline">
            <span className="text-slate-500 dark:text-slate-400">目安:</span>
            <span className="font-mono font-black text-[#34d399] text-sm">{formatVal(data["+4_p50"])}</span>
          </div>
          <div className="flex justify-between gap-4 text-[10px] text-slate-455 dark:text-slate-500">
            <span>範囲:</span>
            <span className="font-mono">{formatVal(data["+4_p10"])} 〜 {formatVal(data["+4_p90"])}</span>
          </div>
        </div>

        {/* +6 Group */}
        <div className="flex flex-col gap-0.5 border-t border-slate-200 dark:border-white/5 pt-2">
          <span className="text-[10px] font-black text-[#a855f7] uppercase tracking-wider">+6 ボーダー</span>
          <div className="flex justify-between gap-4 items-baseline">
            <span className="text-slate-500 dark:text-slate-400">目安:</span>
            <span className="font-mono font-black text-[#a855f7] text-sm">{formatVal(data["+6_p50"])}</span>
          </div>
          <div className="flex justify-between gap-4 text-[10px] text-slate-460 dark:text-slate-500">
            <span>範囲:</span>
            <span className="font-mono">{formatVal(data["+6_p10"])} 〜 {formatVal(data["+6_p90"])}</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export function ForecastChart({ chartData, isLoading, onDateClick }: ForecastChartProps) {
  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">期間予測トレンド推移（下振れ・目安・上振れの幅）</h3>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          面グラフの網掛け（下振れ〜上振れ）は不確実性の幅を表し、実線（目安）はモデルの中央予測を示します。（日付をクリックすると下部詳細が連動します）
        </p>
      </div>

      <div className="h-96 w-full mt-4 bg-white/40 dark:bg-slate-950/40 border border-slate-200 dark:border-white/5 rounded-xl p-4">
        {isLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <AreaChart
              data={chartData}
              margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              style={{ cursor: onDateClick ? "pointer" : "default" }}
              onClick={(state) => {
                const event = state as unknown as RechartsClickEvent;
                if (event && event.activePayload && event.activePayload.length > 0 && onDateClick) {
                  const clickedRow = event.activePayload[0].payload;
                  if (clickedRow && clickedRow.rawDate) {
                    onDateClick(clickedRow.rawDate);
                  }
                }
              }}
            >
              <defs>
                <linearGradient id="colorP2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="colorP4" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34d399" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#34d399" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="colorP6" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
              <XAxis
                dataKey="date"
                stroke="#64748b"
                fontSize={11}
                fontWeight="bold"
              />
              <YAxis
                stroke="#64748b"
                fontSize={11}
                fontWeight="bold"
                tickFormatter={(v) => formatVal(v)}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: "var(--card-border)", strokeWidth: 1.5 }}
              />
              {/* +2 Area and line */}
              <Area
                type="monotone"
                dataKey="+2_p90"
                stroke="none"
                fill="url(#colorP2)"
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="+2_p10"
                stroke="none"
                fill="var(--background)"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="+2_p50"
                name="+2 目安"
                stroke="#38bdf8"
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />

              {/* +4 Area and line */}
              <Area
                type="monotone"
                dataKey="+4_p90"
                stroke="none"
                fill="url(#colorP4)"
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="+4_p10"
                stroke="none"
                fill="var(--background)"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="+4_p50"
                name="+4 目安"
                stroke="#34d399"
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />

              {/* +6 Area and line */}
              <Area
                type="monotone"
                dataKey="+6_p90"
                stroke="none"
                fill="url(#colorP6)"
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="+6_p10"
                stroke="none"
                fill="var(--background)"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="+6_p50"
                name="+6 目安"
                stroke="#a855f7"
                strokeWidth={3}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-slate-500">
            データがありません。別の日付範囲を選択してください。
          </div>
        )}
      </div>
    </section>
  );
}
