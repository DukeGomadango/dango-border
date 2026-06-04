"use client";

import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
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

interface ForestChartProps {
  selectedRow: ChartRow | null;
  isLoading: boolean;
}

interface CustomP50MarkerProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
}

// Custom shape to render p50 as a vertical tick marker in the horizontal bar chart
const CustomP50Marker = (props: CustomP50MarkerProps) => {
  const { x = 0, y = 0, width = 0, height = 0, fill = "" } = props;
  if (width === 0 || isNaN(width) || isNaN(x)) return null;

  // The right edge of the bar represents the p50 value coordinate
  const p50X = x + width;

  return (
    <g>
      {/* Outer glow line */}
      <line
        x1={p50X}
        y1={y - 2}
        x2={p50X}
        y2={y + height + 2}
        stroke={fill}
        strokeWidth={6}
        strokeLinecap="round"
        opacity={0.3}
      />
      {/* Solid inner line */}
      <line
        x1={p50X}
        y1={y - 2}
        x2={p50X}
        y2={y + height + 2}
        stroke="#ffffff"
        strokeWidth={2.5}
        strokeLinecap="round"
      />
    </g>
  );
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      name: string;
      p10: number;
      p50: number;
      p90: number;
      fill: string;
    };
  }>;
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="glass-card rounded-xl p-3 text-xs border border-slate-200/50 dark:border-white/10 shadow-xl bg-white/90 dark:bg-[#060913]/90 backdrop-blur-md text-slate-800 dark:text-slate-200">
        <p className="font-extrabold mb-1.5 text-slate-900 dark:text-white">{data.name}</p>
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between gap-6">
            <span className="text-slate-500 dark:text-slate-400">予測変動幅:</span>
            <span className="font-mono text-slate-750 dark:text-slate-300">
              {formatVal(data.p10)} 〜 {formatVal(data.p90)}
            </span>
          </div>
          <div className="flex justify-between gap-6 items-center border-t border-slate-200 dark:border-white/5 pt-1.5 mt-0.5">
            <span className="text-slate-500 dark:text-slate-400 font-extrabold">目安値:</span>
            <span className="font-mono font-black text-sm" style={{ color: data.fill }}>
              {formatVal(data.p50)}
            </span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export function ForestChart({ selectedRow, isLoading }: ForestChartProps) {
  const barData = useMemo(() => {
    if (!selectedRow) return [];

    return [
      {
        name: "+2 ボーダー",
        p10: selectedRow["+2_p10"],
        p50: selectedRow["+2_p50"],
        p90: selectedRow["+2_p90"],
        range: [selectedRow["+2_p10"], selectedRow["+2_p90"]],
        fill: "#38bdf8",
      },
      {
        name: "+4 ボーダー",
        p10: selectedRow["+4_p10"],
        p50: selectedRow["+4_p50"],
        p90: selectedRow["+4_p90"],
        range: [selectedRow["+4_p10"], selectedRow["+4_p90"]],
        fill: "#34d399",
      },
      {
        name: "+6 ボーダー",
        p10: selectedRow["+6_p10"],
        p50: selectedRow["+6_p50"],
        p90: selectedRow["+6_p90"],
        range: [selectedRow["+6_p10"], selectedRow["+6_p90"]],
        fill: "#a855f7",
      },
    ];
  }, [selectedRow]);

  // Calculate dynamic X-axis domain to prevent empty space
  const xDomain = useMemo(() => {
    if (barData.length === 0) return [0, 10000];
    const mins = barData.map((d) => d.p10);
    const maxs = barData.map((d) => d.p90);
    const minVal = Math.min(...mins);
    const maxVal = Math.max(...maxs);
    const padding = (maxVal - minVal) * 0.15 || 1000;
    return [Math.max(0, Math.floor(minVal - padding)), Math.ceil(maxVal + padding)];
  }, [barData]);

  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">
            選択日詳細予測（目標別ブレ幅・目安の横比較）
          </h3>
          {selectedRow && (
            <span className="text-[10px] bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 font-bold px-2 py-0.5 rounded-md">
              対象日: {selectedRow.rawDate}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          横帯のグラデーション（下振れ〜上振れの幅）は不確実性を表し、中央の白い縦線は目安値を示します。
        </p>
      </div>

      <div className="h-64 w-full mt-4 bg-white/40 dark:bg-slate-950/40 border border-slate-200 dark:border-white/5 rounded-xl p-4">
        {isLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
          </div>
        ) : barData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={barData}
              barGap="-100%"
              margin={{ top: 10, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" horizontal={false} />
              
              <XAxis
                type="number"
                domain={xDomain}
                stroke="#64748b"
                fontSize={11}
                fontWeight="bold"
                tickFormatter={(v) => formatVal(v)}
              />
              
              <YAxis
                type="category"
                dataKey="name"
                stroke="#64748b"
                fontSize={11}
                fontWeight="bold"
                width={85}
              />
              
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "var(--card-border)" }}
              />

              {/* 1. Uncertainty range [p10, p90] represented by a floating bar */}
              <Bar dataKey="range" radius={6} barSize={20} name="range">
                {barData.map((entry, index) => (
                  <Cell
                    key={`cell-range-${index}`}
                    fill={entry.fill}
                    fillOpacity={0.12}
                    stroke={entry.fill}
                    strokeDasharray="4 4"
                    strokeWidth={1}
                  />
                ))}
              </Bar>

              {/* 2. Expected value p50 marker */}
              <Bar dataKey="p50" shape={<CustomP50Marker />} barSize={20} name="p50">
                {barData.map((entry, index) => (
                  <Cell key={`cell-p50-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
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
