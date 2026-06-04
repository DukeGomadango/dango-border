import { useState, useCallback, useEffect, useRef, startTransition } from "react";
import {
  PublicationPlan,
  PublicationCandidate,
  TargetOperationRow,
  JobProgress,
  UploadData,
  TrainAllData,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

export interface PromptModalState {
  isOpen: boolean;
  title: string;
  description: string;
  value: string;
  onSubmit: (reason: string) => Promise<void> | void;
  onClose: () => void;
}

export interface ToastState {
  message: string;
  type: "success" | "error" | "info";
}

export function useAdminData(activeTab: "liver" | "admin") {
  const isMountedRef = useRef(true);

  // Mounted status tracking
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // UI Dialog/Notification States
  const [toast, setToast] = useState<ToastState | null>(null);
  const [promptModal, setPromptModal] = useState<PromptModalState>({
    isOpen: false,
    title: "",
    description: "",
    value: "",
    onSubmit: () => {},
    onClose: () => {},
  });

  const showToast = useCallback((message: string, type: ToastState["type"] = "info") => {
    if (!isMountedRef.current) return;
    setToast({ message, type });
  }, []);

  const closeToast = useCallback(() => {
    if (!isMountedRef.current) return;
    setToast(null);
  }, []);

  const closePromptModal = useCallback(() => {
    if (!isMountedRef.current) return;
    setPromptModal((prev) => ({ ...prev, isOpen: false }));
  }, []);

  // Data States
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<JobProgress | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [trainStatus, setTrainStatus] = useState<string | null>(null);
  const [isTraining, setIsTraining] = useState(false);
  const [publicationPlan, setPublicationPlan] = useState<PublicationPlan | null>(null);
  const [candidates, setCandidates] = useState<PublicationCandidate[]>([]);
  const [operationRows, setOperationRows] = useState<TargetOperationRow[]>([]);
  const [dragActive, setDragActive] = useState(false);

  // Fetch admin stats and rows
  const fetchAdminData = useCallback(async () => {
    try {
      const [planRes, candRes, rowsRes] = await Promise.all([
        fetch(`${API_BASE}/datasets/publication/plan`).then((r) =>
          r.json().catch(() => null)
        ) as Promise<PublicationPlan | null>,
        fetch(`${API_BASE}/datasets/publication/candidates`).then((r) =>
          r.json().catch(() => null)
        ) as Promise<{ candidates?: PublicationCandidate[] } | null>,
        fetch(`${API_BASE}/datasets/targets/operations`).then((r) =>
          r.json().catch(() => null)
        ) as Promise<{ targets?: TargetOperationRow[] } | null>,
      ]);

      if (!isMountedRef.current) return;

      if (planRes) setPublicationPlan(planRes);
      setCandidates(candRes?.candidates ?? []);
      setOperationRows(rowsRes?.targets ?? []);
    } catch (e: unknown) {
      console.error("Admin data fetch error", e);
      showToast("管理者データの取得に失敗しました。", "error");
    }
  }, [showToast]);

  // Fetch data on activeTab change
  useEffect(() => {
    if (activeTab === "admin") {
      startTransition(() => {
        void fetchAdminData();
      });
    }
  }, [activeTab, fetchAdminData]);

  // Drag and Drop
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadFile(e.dataTransfer.files[0]);
    }
  }, []);

  // Upload with Job Polling and clean unmount handling
  const handleUpload = useCallback(async () => {
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
      const data = (await res.json()) as UploadData;
      if (!res.ok) throw new Error(data.detail ?? "アップロードに失敗しました。");

      const jobId = data.job_id;
      if (!jobId) throw new Error("job_id が返却されませんでした。");
      
      if (isMountedRef.current) {
        setUploadStatus(`ジョブ起動中 (ID: ${jobId})`);
      }

      for (let i = 0; i < 30; i++) {
        if (!isMountedRef.current) return; // Exit loop if unmounted
        
        await new Promise<void>((r) => setTimeout(r, 2000));
        
        if (!isMountedRef.current) return;

        const jobRes = await fetch(`${API_BASE}/datasets/jobs/${jobId}`);
        const job = (await jobRes.json()) as JobProgress;
        
        if (isMountedRef.current) {
          setUploadProgress(job);
          setUploadStatus(`解析中... ステージ: ${job.stage}`);
        }

        if (job.status === "completed") {
          if (isMountedRef.current) {
            setUploadStatus("データの取り込みと品質チェックが正常に完了しました！");
            setIsUploading(false);
            setUploadFile(null);
            showToast("データの取り込みが完了しました。", "success");
            void fetchAdminData();
          }
          return;
        } else if (job.status === "failed") {
          throw new Error(`ジョブエラー: ${job.error ?? "品質ゲート失敗"}`);
        }
      }
      throw new Error("ジョブ処理がタイムアウトしました。");
    } catch (err: unknown) {
      if (isMountedRef.current) {
        const errMsg = err instanceof Error ? err.message : String(err);
        setUploadStatus(`エラー: ${errMsg}`);
        setIsUploading(false);
        showToast(`アップロードエラー: ${errMsg}`, "error");
      }
    }
  }, [uploadFile, fetchAdminData, showToast]);

  // Batch Train handler
  const handleBatchTrain = useCallback(async () => {
    setIsTraining(true);
    setTrainStatus("全ターゲットの一括学習を開始中...");
    try {
      const res = await fetch(`${API_BASE}/models/train-all`, { method: "POST" });
      const data = (await res.json()) as TrainAllData;
      if (!res.ok) throw new Error(data.detail ?? "一括学習に失敗しました。");

      if (!isMountedRef.current) return;

      const adopted = (data.results ?? []).filter((r) => r.adopted).length;
      const errors = (data.errors ?? []).length;
      const statusText = `学習完了: 成功=${(data.results ?? []).length}件 (採用=${adopted}件), エラー=${errors}件`;
      setTrainStatus(statusText);
      showToast("モデル一括学習が完了しました。", "success");
    } catch (err: unknown) {
      if (isMountedRef.current) {
        const errMsg = err instanceof Error ? err.message : String(err);
        setTrainStatus(`学習エラー: ${errMsg}`);
        showToast(`一括学習エラー: ${errMsg}`, "error");
      }
    } finally {
      if (isMountedRef.current) {
        setIsTraining(false);
        void fetchAdminData();
      }
    }
  }, [fetchAdminData, showToast]);

  // Toggle publish
  const triggerTogglePublish = useCallback((target: string, currentPublish: boolean) => {
    setPromptModal({
      isOpen: true,
      title: "公開状態の切り替え",
      description: `「${target}」の公開状態を ${currentPublish ? "非公開" : "公開"} にします。理由を入力してください:`,
      value: "",
      onClose: closePromptModal,
      onSubmit: async (reason: string) => {
        closePromptModal();
        try {
          const res = await fetch(`${API_BASE}/datasets/targets/${encodeURIComponent(target)}/publish`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ publish: !currentPublish, reason }),
          });
          if (!res.ok) {
            const body = (await res.json()) as { detail?: string };
            throw new Error(body.detail ?? "ステータス更新に失敗しました。");
          }
          showToast(`「${target}」の公開状態を更新しました。`, "success");
          void fetchAdminData();
        } catch (err: unknown) {
          const errMsg = err instanceof Error ? err.message : String(err);
          showToast(`更新エラー: ${errMsg}`, "error");
        }
      },
    });
  }, [closePromptModal, fetchAdminData, showToast]);

  // Promote single beta
  const triggerPromoteBeta = useCallback((target: string) => {
    setPromptModal({
      isOpen: true,
      title: "正式公開へプロモート",
      description: `「${target}」を正式公開します。理由を入力してください:`,
      value: "",
      onClose: closePromptModal,
      onSubmit: async (reason: string) => {
        if (!reason.trim()) {
          showToast("理由を入力してください。", "error");
          return;
        }
        closePromptModal();
        try {
          const res = await fetch(`${API_BASE}/datasets/publication/promote`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target, reason }),
          });
          if (!res.ok) {
            const body = (await res.json()) as { detail?: string };
            throw new Error(body.detail ?? "公開に失敗しました。");
          }
          showToast(`「${target}」を正式公開しました。`, "success");
          void fetchAdminData();
        } catch (err: unknown) {
          const errMsg = err instanceof Error ? err.message : String(err);
          showToast(`プロモートエラー: ${errMsg}`, "error");
        }
      },
    });
  }, [closePromptModal, fetchAdminData, showToast]);

  return {
    uploadFile,
    setUploadFile,
    uploadStatus,
    uploadProgress,
    isUploading,
    trainStatus,
    isTraining,
    publicationPlan,
    candidates,
    operationRows,
    dragActive,
    handleDrag,
    handleDrop,
    handleUpload,
    handleBatchTrain,
    triggerTogglePublish,
    triggerPromoteBeta,
    // dialog states
    toast,
    closeToast,
    promptModal,
  };
}
