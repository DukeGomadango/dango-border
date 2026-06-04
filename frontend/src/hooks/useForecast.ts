import useSWR from "swr";
import { useState, useEffect, useCallback, startTransition } from "react";
import { DeepPredictionResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export const TARGET_GROUPS = ["S3", "S2", "S1", "A3", "A2", "A1", "B3", "B2", "B1", "C5", "C4", "C3"];

const getInitialGroup = (): string => {
  if (typeof window === "undefined") return "S3";
  const saved = window.localStorage.getItem("selectedGroup");
  return saved && TARGET_GROUPS.includes(saved) ? saved : "S3";
};

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

const fetcher = async (url: string) => {
  const response = await fetch(url);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? "予測データの取得に失敗しました。");
  }
  return body as DeepPredictionResponse;
};

export function useForecast() {
  const [selectedGroup, setSelectedGroup] = useState<string>("S3");
  const [predictionMode, setPredictionMode] = useState<"hybrid" | "tft_only">("hybrid");
  const [wTft, setWTft] = useState(0.6);
  const [dateRange, setDateRange] = useState({ from: "", to: "" });

  useEffect(() => {
    startTransition(() => {
      setSelectedGroup(getInitialGroup());
      setDateRange(getEventDateRange());
    });
  }, []);

  const handleGroupChange = useCallback((group: string) => {
    setSelectedGroup(group);
    localStorage.setItem("selectedGroup", group);
  }, []);

  const swrKey = dateRange.from && dateRange.to
    ? `${API_BASE}/deep/predictions?target_group=${encodeURIComponent(selectedGroup)}&from_date=${encodeURIComponent(dateRange.from)}&to_date=${encodeURIComponent(dateRange.to)}&use_hybrid=${predictionMode === "hybrid"}&w_tft=${wTft}`
    : null;

  const { data: predictionData, error } = useSWR<DeepPredictionResponse>(
    swrKey,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
      shouldRetryOnError: false,
    }
  );

  const isLoading = !predictionData && !error && !!swrKey;

  return {
    selectedGroup,
    handleGroupChange,
    predictionMode,
    setPredictionMode,
    wTft,
    setWTft,
    dateRange,
    setDateRange,
    predictionData: predictionData ?? null,
    isLoading,
    error: error instanceof Error ? error.message : (error ? String(error) : null),
  };
}
