"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, Layers, Settings, BookOpen } from "lucide-react";

import { useForecast } from "@/hooks/useForecast";
import { useAdminData } from "@/hooks/useAdminData";
import { PromptModal } from "@/components/ui/PromptModal";
import { ToastContainer } from "@/components/ui/Toast";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

// Forecast components
import { ForecastControls } from "@/components/forecast/ForecastControls";
import { WeatherForecast } from "@/components/forecast/WeatherForecast";
import { ForecastCards } from "@/components/forecast/ForecastCards";
import { ForecastChart } from "@/components/forecast/ForecastChart";
import { ForecastTable } from "@/components/forecast/ForecastTable";
import { ForestChart } from "@/components/forecast/ForestChart";

// Admin components
import { DataUploader } from "@/components/admin/DataUploader";
import { BatchTrainer } from "@/components/admin/BatchTrainer";
import { PublicationPlanGauge } from "@/components/admin/PublicationPlanGauge";
import { CandidatesTable } from "@/components/admin/CandidatesTable";
import { OperationsTable } from "@/components/admin/OperationsTable";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
const isProd = process.env.NODE_ENV === "production";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"liver" | "admin">("liver");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Derive activeTab safely depending on production flag
  const currentTab = isProd ? "liver" : activeTab;

  // Load custom hooks
  const forecast = useForecast();
  const admin = useAdminData(currentTab);

  // Recharts custom formatted data
  const chartData = useMemo(() => {
    if (!forecast.predictionData || !forecast.predictionData.steps) return [];
    
    // Sort steps chronologically
    const sortedSteps = [...forecast.predictionData.steps].sort((a, b) => a.date.localeCompare(b.date));
    
    return sortedSteps.map((step) => {
      const formattedDate = step.date.slice(5); // MM-DD
      const t2 = step.predictions[`${forecast.selectedGroup} +2`] || { p10: 0, p50: 0, p90: 0 };
      const t4 = step.predictions[`${forecast.selectedGroup} +4`] || { p10: 0, p50: 0, p90: 0 };
      const t6 = step.predictions[`${forecast.selectedGroup} +6`] || { p10: 0, p50: 0, p90: 0 };

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
  }, [forecast.predictionData, forecast.selectedGroup]);

  // Sync selectedDate when chartData updates
  // We derive the selected row safely
  const selectedRow = useMemo(() => {
    if (chartData.length === 0) return null;
    return chartData.find((d) => d.rawDate === selectedDate) || chartData[0];
  }, [chartData, selectedDate]);

  const latestForecast = selectedRow;

  return (
    <div className="min-h-screen flex flex-col relative z-10 bg-transparent text-foreground font-sans selection:bg-purple-500/30 selection:text-purple-200">
      {/* Dynamic Navigation Header */}
      <header className="sticky top-0 z-40 w-full bg-white/60 dark:bg-slate-900/60 backdrop-blur-md border-b border-slate-200/50 dark:border-white/5 py-4 px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <TrendingUp className="text-white w-5 h-5" />
          </div>
          <div>
            <h1 className="font-sans font-black tracking-tight text-lg leading-tight bg-gradient-to-r from-slate-900 dark:from-white via-slate-700 dark:via-slate-100 to-slate-500 dark:to-slate-300 bg-clip-text text-transparent">
              Border Analysis
            </h1>
            <p className="text-[10px] text-slate-400 dark:text-slate-500 tracking-wider uppercase font-bold leading-none mt-0.5">
              IRIAM Rank Boundary Forecast
            </p>
          </div>
        </div>

        {/* Tab Selector */}
        {!isProd && (
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-200/60 dark:bg-slate-950/60 border border-slate-300/30 dark:border-white/5" role="tablist">
            <button
              role="tab"
              aria-selected={currentTab === "liver"}
              aria-controls="panel-liver"
              onClick={() => setActiveTab("liver")}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                currentTab === "liver"
                  ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/10"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              ライバー予測画面
            </button>
            <button
              role="tab"
              aria-selected={currentTab === "admin"}
              aria-controls="panel-admin"
              onClick={() => setActiveTab("admin")}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                currentTab === "admin"
                  ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/10"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white"
              }`}
            >
              <Settings className="w-3.5 h-3.5" />
              運用者パネル
            </button>
          </div>
        )}

        {/* API Docs link & Theme Toggle */}
        <div className="flex items-center gap-3 text-xs">
          {!isProd && (
            <a
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-slate-600 dark:text-slate-400 hover:text-slate-950 dark:hover:text-white border border-slate-300 dark:border-white/10 hover:border-slate-400 dark:hover:border-white/20 rounded-lg px-3 py-1.5 transition-colors font-bold"
            >
              <BookOpen className="w-3.5 h-3.5" />
              API Docs
            </a>
          )}
          <ThemeToggle />
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 md:px-12 py-8 flex flex-col gap-8 z-10">
        <AnimatePresence mode="wait">
          {currentTab === "liver" ? (
            <motion.div
              key="liver-tab"
              id="panel-liver"
              role="tabpanel"
              aria-labelledby="tab-liver"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="flex flex-col gap-8"
            >
              <ForecastControls
                selectedGroup={forecast.selectedGroup}
                onGroupChange={forecast.handleGroupChange}
                predictionMode={forecast.predictionMode}
                onPredictionModeChange={forecast.setPredictionMode}
                wTft={forecast.wTft}
                onWTftChange={forecast.setWTft}
                dateRange={forecast.dateRange}
                onDateRangeChange={forecast.setDateRange}
              />

              {forecast.error && (
                <div role="alert" aria-live="assertive" className="bg-red-500/10 border border-red-500/20 rounded-2xl p-4 flex items-center gap-3 text-sm text-red-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                  <div>{forecast.error}</div>
                </div>
              )}

              <WeatherForecast
                selectedGroup={forecast.selectedGroup}
                predictionData={forecast.predictionData}
                isLoading={forecast.isLoading}
                dateRange={forecast.dateRange}
                predictionMode={forecast.predictionMode}
                wTft={forecast.wTft}
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                onGroupChange={forecast.handleGroupChange}
              />

              <ForecastCards
                selectedGroup={forecast.selectedGroup}
                latestForecast={latestForecast}
                isLoading={forecast.isLoading}
              />

              {chartData.length > 1 && (
                <ForecastChart
                  chartData={chartData}
                  isLoading={forecast.isLoading}
                  onDateClick={setSelectedDate}
                />
              )}

              <ForestChart
                selectedRow={selectedRow}
                isLoading={forecast.isLoading}
              />

              <ForecastTable
                chartData={chartData}
                modelVersion={forecast.predictionData?.model_version}
                modelType={forecast.predictionData?.model_type}
                blendingStatus={forecast.predictionData?.blending_status}
              />
            </motion.div>
          ) : (
            <motion.div
              key="admin-tab"
              id="panel-admin"
              role="tabpanel"
              aria-labelledby="tab-admin"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              {/* Left Panel */}
              <div className="col-span-1 lg:col-span-4 flex flex-col gap-8">
                <DataUploader
                  uploadFile={admin.uploadFile}
                  setUploadFile={admin.setUploadFile}
                  uploadStatus={admin.uploadStatus}
                  uploadProgress={admin.uploadProgress}
                  isUploading={admin.isUploading}
                  dragActive={admin.dragActive}
                  onDrag={admin.handleDrag}
                  onDrop={admin.handleDrop}
                  onUpload={admin.handleUpload}
                />

                <BatchTrainer
                  trainStatus={admin.trainStatus}
                  isTraining={admin.isTraining}
                  onBatchTrain={admin.handleBatchTrain}
                />
              </div>

              {/* Right Panel */}
              <div className="col-span-1 lg:col-span-8 flex flex-col gap-8">
                <PublicationPlanGauge publicationPlan={admin.publicationPlan} />

                <CandidatesTable
                  candidates={admin.candidates}
                  onPromoteBeta={admin.triggerPromoteBeta}
                />

                <OperationsTable
                  operationRows={admin.operationRows}
                  onTogglePublish={admin.triggerTogglePublish}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="w-full border-t border-slate-200 dark:border-white/5 py-6 px-6 mt-12 text-center text-xs text-slate-500 dark:text-slate-500 font-mono z-10">
        © 2026 Border Analysis. Created using Next.js, FastAPI & Recharts.
      </footer>

      {/* Custom Dialog Modals and Toast Notifications */}
      <PromptModal
        isOpen={admin.promptModal.isOpen}
        onClose={admin.promptModal.onClose}
        title={admin.promptModal.title}
        description={admin.promptModal.description}
        onSubmit={admin.promptModal.onSubmit}
      />

      <ToastContainer toast={admin.toast} onClose={admin.closeToast} />
    </div>
  );
}
