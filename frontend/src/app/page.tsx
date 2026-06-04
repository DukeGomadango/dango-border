"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  CartesianGrid,
} from "recharts";
import {
  TrendingUp,
  Sliders,
  Upload,
  Activity,
  Layers,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  BookOpen,
  ArrowRight,
  Database,
  Terminal,
  Settings,
} from "lucide-react";

// API Base detection (uses env var if provided, otherwise defaults based on environment)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

const TARGET_GROUPS = ["S1", "S2", "S3", "A1", "A2", "A3", "B1", "B2", "B3", "C3", "C4", "C5"];

interface PredictionStep {
  date: string;
  predictions: {
    [key: string]: {
      p10: number;
      p50: number;
      p90: number;
    };
  };
}

interface DeepPredictionResponse {
  target_group: string;
  model_type: string;
  model_version: string;
  blending_status?: string;
  w_tft?: number;
  steps: PredictionStep[];
}

const formatVal = (val: number | null | undefined) => {
  if (val === null || val === undefined || typeof val !== "number" || isNaN(val)) return "-";
  return val.toLocaleString();
};

export default function Dashboard() {
  const [isMounted, setIsMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<"liver" | "admin">("liver");
  const [selectedGroup, setSelectedGroup] = useState("S1");
  const [predictionMode, setPredictionMode] = useState<"hybrid" | "tft_only">("hybrid");
  const [wTft, setWTft] = useState(0.6);
  
  // Data States
  const [predictionData, setPredictionData] = useState<DeepPredictionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Admin States
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<any>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [trainStatus, setTrainStatus] = useState<string | null>(null);
  const [isTraining, setIsTraining] = useState(false);
  const [publicationPlan, setPublicationPlan] = useState<any>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [operationRows, setOperationRows] = useState<any[]>([]);
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);
  
  // Drag and drop ref
  const [dragActive, setDragActive] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsMounted(true);
    // Restore selected rank from LocalStorage if available
    const savedGroup = localStorage.getItem("selectedGroup");
    if (savedGroup && TARGET_GROUPS.includes(savedGroup)) {
      setSelectedGroup(savedGroup);
    }
  }, []);

  // Set default dates for next Tuesday to Monday range
  const getEventDateRange = () => {
    const today = new Date();
    const nextTue = new Date(today);
    nextTue.setDate(today.getDate() + ((1 + 7 - today.getDay()) % 7 || 7));
    const nextMon = new Date(nextTue);
    nextMon.setDate(nextTue.getDate() + 6);
    return {
      from: nextTue.toISOString().split("T")[0],
      to: nextMon.toISOString().split("T")[0],
    };
  };

  const [dateRange, setDateRange] = useState(getEventDateRange());

  // Fetch forecast data
  const fetchForecast = async (groupName: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        target_group: groupName,
        from_date: dateRange.from,
        to_date: dateRange.to,
        use_hybrid: String(predictionMode === "hybrid"),
        w_tft: String(wTft),
      });
      const response = await fetch(`${API_BASE}/deep/predictions?${params}`);
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail || "予測データの取得に失敗しました。");
      }
      setPredictionData(body);
    } catch (err: any) {
      setError(err.message || "エラーが発生しました。");
    } finally {
      setIsLoading(false);
    }
  };

  // Trigger fetch on group or date change
  useEffect(() => {
    if (isMounted) {
      fetchForecast(selectedGroup);
    }
  }, [selectedGroup, dateRange, predictionMode, wTft, isMounted]);

  // Save selected group
  const handleGroupChange = (group: string) => {
    setSelectedGroup(group);
    localStorage.setItem("selectedGroup", group);
  };

  // Admin: Fetch publication plans & lists
  const fetchAdminData = async () => {
    try {
      const [planRes, candRes, rowsRes, metricsRes] = await Promise.all([
        fetch(`${API_BASE}/datasets/publication/plan`).then((r) => r.json().catch(() => ({}))),
        fetch(`${API_BASE}/datasets/publication/candidates`).then((r) => r.json().catch(() => ({}))),
        fetch(`${API_BASE}/datasets/targets/operations`).then((r) => r.json().catch(() => ({}))),
        fetch(`${API_BASE}/system/metrics`).then((r) => r.json().catch(() => ({}))),
      ]);

      setPublicationPlan(planRes);
      setCandidates(candRes.candidates || []);
      setOperationRows(rowsRes.targets || []);
      setSystemMetrics(metricsRes);
    } catch (e) {
      console.error("Admin data fetch error", e);
    }
  };

  useEffect(() => {
    if (activeTab === "admin" && isMounted) {
      fetchAdminData();
    }
  }, [activeTab, isMounted]);

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadFile(e.dataTransfer.files[0]);
    }
  };

  // Upload handler with job polling
  const handleUpload = async () => {
    if (!uploadFile) return;
    setIsUploading(true);
    setUploadStatus("ファイルをアップロード中...");
    
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);

      const res = await fetch(`${API_BASE}/datasets/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "アップロードに失敗しました。");

      // Poll job
      const jobId = data.job_id;
      setUploadStatus(`ジョブ起動中 (ID: ${jobId})`);

      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const jobRes = await fetch(`${API_BASE}/datasets/jobs/${jobId}`);
        const job = await jobRes.json();
        setUploadProgress(job);
        setUploadStatus(`解析中... ステージ: ${job.stage}`);

        if (job.status === "completed") {
          setUploadStatus("データの取り込みと品質チェックが正常に完了しました！");
          setIsUploading(false);
          fetchAdminData();
          return;
        } else if (job.status === "failed") {
          throw new Error(`ジョブエラー: ${job.error || "品質ゲート失敗"}`);
        }
      }
      throw new Error("ジョブ処理がタイムアウトしました。");
    } catch (err: any) {
      setUploadStatus(`エラー: ${err.message}`);
      setIsUploading(false);
    }
  };

  // Batch train handler
  const handleBatchTrain = async () => {
    setIsTraining(true);
    setTrainStatus("全ターゲットの一括学習を開始中...");
    try {
      const res = await fetch(`${API_BASE}/models/train-all`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "一括学習に失敗しました。");
      
      const adopted = (data.results || []).filter((r: any) => r.adopted).length;
      const errors = (data.errors || []).length;
      setTrainStatus(
        `学習完了: 成功=${(data.results || []).length}件 (採用=${adopted}件), エラー=${errors}件`
      );
    } catch (err: any) {
      setTrainStatus(`学習エラー: ${err.message}`);
    } finally {
      setIsTraining(false);
      fetchAdminData();
    }
  };

  // Toggle publish
  const handleTogglePublish = async (target: string, currentPublish: boolean) => {
    const reason = prompt(
      `「${target}」の公開状態を ${currentPublish ? "非公開" : "公開"} にします。理由を入力してください:`
    );
    if (reason === null) return;
    try {
      const res = await fetch(`${API_BASE}/datasets/targets/${encodeURIComponent(target)}/publish`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ publish: !currentPublish, reason }),
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "ステータス更新に失敗しました。");
      }
      fetchAdminData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Promote single beta
  const handlePromoteBeta = async (target: string) => {
    const reason = prompt(`「${target}」を正式公開します。理由を入力してください:`);
    if (!reason) return;
    try {
      const res = await fetch(`${API_BASE}/datasets/publication/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, reason }),
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || "公開に失敗しました。");
      }
      fetchAdminData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Recharts custom formatted data
  const chartData = React.useMemo(() => {
    if (!predictionData || !predictionData.steps) return [];
    
    // Sort steps chronologically
    const sortedSteps = [...predictionData.steps].sort((a, b) => a.date.localeCompare(b.date));
    
    return sortedSteps.map((step) => {
      const formattedDate = step.date.slice(5); // MM-DD
      const t2 = step.predictions[`${selectedGroup} +2`] || { p10: 0, p50: 0, p90: 0 };
      const t4 = step.predictions[`${selectedGroup} +4`] || { p10: 0, p50: 0, p90: 0 };
      const t6 = step.predictions[`${selectedGroup} +6`] || { p10: 0, p50: 0, p90: 0 };

      return {
        rawDate: step.date,
        date: formattedDate,
        "+2_p10": t2.p10,
        "+2_p50": t2.p50,
        "+2_p90": t2.p90,
        "+4_p10": t4.p10,
        "+4_p50": t4.p50,
        "+4_p90": t4.p90,
        "+6_p10": t6.p10,
        "+6_p50": t6.p50,
        "+6_p90": t6.p90,
      };
    });
  }, [predictionData, selectedGroup]);

  // Extract tonight's (latest day) forecast card info
  const latestForecast = React.useMemo(() => {
    if (chartData.length === 0) return null;
    return chartData[0]; // Shows the first prediction in the date range
  }, [chartData]);



  return (
    <div className="min-h-screen flex flex-col relative">
      {/* Dynamic Navigation Header */}
      <header className="sticky top-0 z-40 w-full glass-card border-b border-white/5 py-4 px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <TrendingUp className="text-white w-5 h-5" />
          </div>
          <div>
            <h1 className="font-sans font-black tracking-tight text-lg leading-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
              Border Analysis
            </h1>
            <p className="text-[10px] text-slate-500 tracking-wider uppercase font-bold leading-none mt-0.5">
              IRIAM Rank Boundary Forecast
            </p>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-950/60 border border-white/5">
          <button
            onClick={() => setActiveTab("liver")}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-black transition-all ${
              activeTab === "liver"
                ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/10"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            ライバー予測画面
          </button>
          <button
            onClick={() => setActiveTab("admin")}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-black transition-all ${
              activeTab === "admin"
                ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/10"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            運用者パネル
          </button>
        </div>

        {/* API Docs link */}
        <div className="flex items-center gap-3 text-xs">
          <a
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-slate-400 hover:text-white border border-white/10 hover:border-white/20 rounded-lg px-3 py-1.5 transition-colors font-bold"
          >
            <BookOpen className="w-3.5 h-3.5" />
            API Docs
          </a>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 md:px-12 py-8 flex flex-col gap-8">
        <AnimatePresence mode="wait">
          {activeTab === "liver" ? (
            <motion.div
              key="liver-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="flex flex-col gap-8"
            >
              {/* Rank Group Filter Settings */}
              <section className="glass-card rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                <div className="flex flex-col gap-1.5">
                  <h2 className="text-base font-extrabold text-white flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-purple-400" />
                    表示対象の設定
                  </h2>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    所属するランクグループを選択してください。対応する「+2」「+4」「+6」予測が表示されます。
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">所属ランク</label>
                    <select
                      value={selectedGroup}
                      onChange={(e) => handleGroupChange(e.target.value)}
                      className="bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-sm text-white font-bold outline-none focus:border-purple-500 transition-colors"
                    >
                      {TARGET_GROUPS.map((g) => (
                        <option key={g} value={g}>
                          {g} グループ
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">開始日</label>
                    <input
                      type="date"
                      value={dateRange.from}
                      onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
                      className="bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-sm text-white font-bold outline-none focus:border-purple-500 transition-colors"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">終了日</label>
                    <input
                      type="date"
                      value={dateRange.to}
                      onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
                      className="bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-sm text-white font-bold outline-none focus:border-purple-500 transition-colors"
                    />
                  </div>
                </div>
              </section>

              {/* Hybrid & Blending controls */}
              <section className="glass-card rounded-2xl p-6 flex flex-col md:flex-row gap-6 items-start md:items-center">
                <div className="flex-1">
                  <h3 className="text-sm font-extrabold text-white">予測モデル構成</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    イベント進行（経過日数）や曜日影響を自動分析する TFT (Temporal Fusion Transformer) と勾配ブースティングを調整します。
                  </p>
                </div>
                
                <div className="flex flex-wrap gap-4 items-center w-full md:w-auto">
                  <div className="flex flex-col gap-1 w-full md:w-56">
                    <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">構成モード</label>
                    <select
                      value={predictionMode}
                      onChange={(e: any) => setPredictionMode(e.target.value)}
                      className="bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-sm text-white font-bold outline-none focus:border-purple-500 transition-colors"
                    >
                      <option value="hybrid">ハイブリッドアンサンブル</option>
                      <option value="tft_only">TFT 単体モデル</option>
                    </select>
                  </div>

                  {predictionMode === "hybrid" && (
                    <div className="flex flex-col gap-1 w-full md:w-56">
                      <div className="flex justify-between items-center text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        <span>TFT比率 (w_tft)</span>
                        <span className="text-purple-400 font-mono font-black">{wTft.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={wTft}
                        onChange={(e) => setWTft(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-purple-500 mt-2"
                      />
                    </div>
                  )}
                </div>
              </section>

              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-4 flex items-center gap-3 text-sm text-red-200">
                  <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
                  <div>{error}</div>
                </div>
              )}

              {/* Tonight's target points dashboard */}
              {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="glass-card rounded-2xl p-6 h-40 animate-pulse flex flex-col gap-3">
                      <div className="h-4 bg-white/5 rounded-md w-24" />
                      <div className="h-8 bg-white/5 rounded-md w-36" />
                      <div className="h-3 bg-white/5 rounded-md w-full" />
                    </div>
                  ))}
                </div>
              ) : latestForecast ? (
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
                      <span className="text-3xl font-black font-mono text-white tracking-tight">
                        {formatVal(latestForecast["+2_p50"])}
                      </span>
                      <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
                        <span className="font-mono font-bold text-slate-300">
                          {formatVal(latestForecast["+2_p10"])}
                        </span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
                        <span className="font-mono font-bold text-slate-300">
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
                      <span className="text-3xl font-black font-mono text-white tracking-tight">
                        {formatVal(latestForecast["+4_p50"])}
                      </span>
                      <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
                        <span className="font-mono font-bold text-slate-300">
                          {formatVal(latestForecast["+4_p10"])}
                        </span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
                        <span className="font-mono font-bold text-slate-300">
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
                      <span className="text-3xl font-black font-mono text-white tracking-tight">
                        {formatVal(latestForecast["+6_p50"])}
                      </span>
                      <span className="text-xs font-bold text-slate-500">ポイント (目安)</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mt-2 pt-3 border-t border-white/5 text-xs">
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">下振れ</span>
                        <span className="font-mono font-bold text-slate-300">
                          {formatVal(latestForecast["+6_p10"])}
                        </span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-500 font-bold">上振れ</span>
                        <span className="font-mono font-bold text-slate-300">
                          {formatVal(latestForecast["+6_p90"])}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                </div>
              ) : null}

              {/* Area Chart visualization of uncertainty */}
              <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-extrabold text-white">期間予測トレンド推移（下振れ・目安・上振れの幅）</h3>
                  <p className="text-xs text-slate-400">
                    面グラフの網掛け（下振れ〜上振れ）は不確実性の幅を表し、実線（目安）はモデルの中央予測を示します。
                  </p>
                </div>

                <div className="h-96 w-full mt-4 bg-slate-950/40 border border-white/5 rounded-xl p-4">
                  {isLoading ? (
                    <div className="w-full h-full flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
                    </div>
                  ) : chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
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
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
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
                          contentStyle={{
                            backgroundColor: "#0f172a",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                            borderRadius: "12px",
                            color: "#cbd5e1",
                            fontSize: "12px",
                          }}
                          itemStyle={{ padding: "2px 0" }}
                          formatter={(value: any, name: any) => [
                            formatVal(value),
                            name ? String(name).replace("_p50", " 目安").replace("_p90", " 上振れ").replace("_p10", " 下振れ") : "",
                          ]}
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
                          fill="#090d16"
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
                          fill="#090d16"
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
                          fill="#090d16"
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

              {/* Data Table */}
              <section className="glass-card rounded-2xl p-6">
                <h3 className="text-sm font-extrabold text-white mb-4">予測値データ一覧</h3>
                <div className="overflow-x-auto custom-scrollbar border border-white/5 rounded-xl">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-950/80 border-b border-white/5 text-slate-400 font-extrabold uppercase">
                        <th className="py-3.5 px-4">日付</th>
                        <th className="py-3.5 px-4 text-center border-l border-white/5" colSpan={3}>
                          +2 ボーダー
                        </th>
                        <th className="py-3.5 px-4 text-center border-l border-white/5" colSpan={3}>
                          +4 ボーダー
                        </th>
                        <th className="py-3.5 px-4 text-center border-l border-white/5" colSpan={3}>
                          +6 ボーダー
                        </th>
                      </tr>
                      <tr className="bg-slate-950/40 border-b border-white/5 text-slate-500 font-bold text-[10px]">
                        <th className="py-2.5 px-4"></th>
                        <th className="py-2.5 px-3 text-right border-l border-white/5">下振れ</th>
                        <th className="py-2.5 px-3 text-right text-[#38bdf8] font-extrabold">目安</th>
                        <th className="py-2.5 px-3 text-right">上振れ</th>
                        <th className="py-2.5 px-3 text-right border-l border-white/5">下振れ</th>
                        <th className="py-2.5 px-3 text-right text-[#34d399] font-extrabold">目安</th>
                        <th className="py-2.5 px-3 text-right">上振れ</th>
                        <th className="py-2.5 px-3 text-right border-l border-white/5">下振れ</th>
                        <th className="py-2.5 px-3 text-right text-[#a855f7] font-extrabold">目安</th>
                        <th className="py-2.5 px-3 text-right">上振れ</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 font-mono text-slate-300">
                      {chartData.map((row) => (
                        <tr key={row.rawDate} className="hover:bg-white/5 transition-colors">
                          <td className="py-3.5 px-4 font-sans font-extrabold text-white">
                            {row.rawDate}
                          </td>
                          <td className="py-3.5 px-3 text-right border-l border-white/5 text-slate-500">
                            {formatVal(row["+2_p10"])}
                          </td>
                          <td className="py-3.5 px-3 text-right font-black text-white">
                            {formatVal(row["+2_p50"])}
                          </td>
                          <td className="py-3.5 px-3 text-right text-slate-500">
                            {formatVal(row["+2_p90"])}
                          </td>
                          <td className="py-3.5 px-3 text-right border-l border-white/5 text-slate-500">
                            {formatVal(row["+4_p10"])}
                          </td>
                          <td className="py-3.5 px-3 text-right font-black text-white">
                            {formatVal(row["+4_p50"])}
                          </td>
                          <td className="py-3.5 px-3 text-right text-slate-500">
                            {formatVal(row["+4_p90"])}
                          </td>
                          <td className="py-3.5 px-3 text-right border-l border-white/5 text-slate-500">
                            {formatVal(row["+6_p10"])}
                          </td>
                          <td className="py-3.5 px-3 text-right font-black text-white">
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
                
                {predictionData && (
                  <p className="text-[10px] text-slate-500 mt-4 text-right">
                    モデルバージョン: {predictionData.model_version} ({predictionData.model_type})
                    {predictionData.blending_status ? ` | 構成: ${predictionData.blending_status}` : ""}
                  </p>
                )}
              </section>
            </motion.div>
          ) : (
            <motion.div
              key="admin-tab"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              {/* Left Panel - Control panel */}
              <div className="col-span-1 lg:col-span-4 flex flex-col gap-8">
                {/* Drag and Drop Upload */}
                <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
                  <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                    <Database className="w-4 h-4 text-indigo-400" />
                    データ取り込み
                  </h3>
                  
                  <div
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center gap-3 transition-colors text-center cursor-pointer ${
                      dragActive
                        ? "border-purple-500 bg-purple-500/10 text-white"
                        : "border-white/10 hover:border-white/20 text-slate-400"
                    }`}
                  >
                    <Upload className="w-8 h-8 text-slate-500" />
                    <div className="text-xs">
                      <p className="font-extrabold text-slate-300">生データファイルをドラッグ＆ドロップ</p>
                      <p className="text-slate-500 mt-1">またはファイルを選択 (.xlsx, .csv)</p>
                    </div>
                    <input
                      type="file"
                      accept=".xlsx,.csv"
                      onChange={(e) => e.target.files && setUploadFile(e.target.files[0])}
                      className="hidden"
                      id="file-upload-input"
                    />
                    <label
                      htmlFor="file-upload-input"
                      className="bg-slate-900 text-white border border-white/10 px-4 py-1.5 rounded-lg text-[10px] font-bold cursor-pointer hover:bg-slate-800 transition-colors"
                    >
                      ファイルを選択
                    </label>
                  </div>

                  {uploadFile && (
                    <div className="bg-slate-950 border border-white/5 rounded-xl p-3 flex justify-between items-center text-xs">
                      <span className="font-bold text-slate-300 truncate max-w-[180px]">
                        {uploadFile.name}
                      </span>
                      <button
                        onClick={() => setUploadFile(null)}
                        className="text-red-400 hover:text-red-300 font-extrabold"
                      >
                        削除
                      </button>
                    </div>
                  )}

                  <button
                    onClick={handleUpload}
                    disabled={!uploadFile || isUploading}
                    className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white disabled:opacity-40 font-black py-2.5 rounded-xl text-xs flex items-center justify-center gap-2 shadow-md shadow-indigo-600/10"
                  >
                    {isUploading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                    アップロードして取り込み
                  </button>

                  {uploadStatus && (
                    <div className="bg-slate-950 border border-white/5 rounded-xl p-3 text-[10px] font-mono leading-relaxed text-slate-400">
                      {uploadStatus}
                      {uploadProgress && (
                        <div className="mt-2 text-slate-500">
                          進捗: {uploadProgress.stage} ({uploadProgress.status})
                        </div>
                      )}
                    </div>
                  )}
                </section>

                {/* Batch model training */}
                <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
                  <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-purple-400" />
                    モデル一括学習
                  </h3>
                  <p className="text-xs text-slate-400">
                    新しく投入したデータをもとに、すべての公開ターゲットモデルを自動再学習させます。
                  </p>
                  
                  <button
                    onClick={handleBatchTrain}
                    disabled={isTraining}
                    className="w-full bg-slate-900 border border-white/10 hover:border-white/20 text-white disabled:opacity-40 font-black py-2.5 rounded-xl text-xs flex items-center justify-center gap-2"
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
              </div>

              {/* Right Panel - Grid dashboards */}
              <div className="col-span-1 lg:col-span-8 flex flex-col gap-8">
                {/* M3 Goal Gauge */}
                {publicationPlan && (
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
                          目標達成率: {Math.round((publicationPlan.published_count / publicationPlan.goal) * 100)}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-2 mt-2">
                        <div
                          className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 h-2 rounded-full"
                          style={{ width: `${(publicationPlan.published_count / publicationPlan.goal) * 100}%` }}
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
                )}

                {/* Beta targets promotion */}
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
                                  onClick={() => handlePromoteBeta(cand.target)}
                                  disabled={!cand.eligible}
                                  className="bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-30 px-3 py-1 rounded font-bold"
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

                {/* Operations target management table */}
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
                                onChange={() => handleTogglePublish(row.target, row.publish)}
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
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="w-full border-t border-white/5 py-6 px-6 mt-12 text-center text-xs text-slate-500 font-mono">
        © 2026 Border Analysis. Created using Next.js, FastAPI & Recharts.
      </footer>
    </div>
  );
}

// Simple Helper Components for Layout
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
