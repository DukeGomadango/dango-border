import React from "react";
import { Upload, RefreshCw, Database } from "lucide-react";
import { JobProgress } from "@/types/api";

interface DataUploaderProps {
  uploadFile: File | null;
  setUploadFile: (file: File | null) => void;
  uploadStatus: string | null;
  uploadProgress: JobProgress | null;
  isUploading: boolean;
  dragActive: boolean;
  onDrag: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onUpload: () => void;
}

export function DataUploader({
  uploadFile,
  setUploadFile,
  uploadStatus,
  uploadProgress,
  isUploading,
  dragActive,
  onDrag,
  onDrop,
  onUpload,
}: DataUploaderProps) {
  return (
    <section className="glass-card rounded-2xl p-6 flex flex-col gap-4">
      <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
        <Database className="w-4 h-4 text-indigo-400" />
        データ取り込み
      </h3>
      
      <div
        onDragEnter={onDrag}
        onDragOver={onDrag}
        onDragLeave={onDrag}
        onDrop={onDrop}
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
        onClick={onUpload}
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
  );
}
