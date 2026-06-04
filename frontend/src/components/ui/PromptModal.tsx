import React, { useState, useEffect, startTransition } from "react";
import { Modal } from "./Modal";

interface PromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description: string;
  placeholder?: string;
  onSubmit: (val: string) => void | Promise<void>;
  defaultValue?: string;
}

export function PromptModal({
  isOpen,
  onClose,
  title,
  description,
  placeholder = "理由を入力してください...",
  onSubmit,
  defaultValue = "",
}: PromptModalProps) {
  const [value, setValue] = useState(defaultValue);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      startTransition(() => {
        setValue(defaultValue);
        setError(null);
        setIsSubmitting(false);
      });
    }
  }, [isOpen, defaultValue]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) {
      setError("入力は必須です。");
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit(value);
      setValue("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "送信に失敗しました。");
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-xs text-slate-300 leading-relaxed">{description}</p>
        
        <div className="flex flex-col gap-1">
          <textarea
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (error) setError(null);
            }}
            placeholder={placeholder}
            rows={3}
            className="w-full bg-slate-950 border border-white/10 rounded-xl px-4 py-2 text-sm text-white font-bold outline-none focus:border-purple-500 transition-colors placeholder:text-slate-600 resize-none font-sans"
            disabled={isSubmitting}
          />
          {error && <span className="text-[10px] text-red-400 font-bold">{error}</span>}
        </div>

        <div className="flex justify-end gap-2.5 mt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-white/10 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-white/5 transition-colors font-bold"
            disabled={isSubmitting}
          >
            キャンセル
          </button>
          <button
            type="submit"
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-black px-4 py-2 rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-md shadow-indigo-600/10"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : null}
            決定
          </button>
        </div>
      </form>
    </Modal>
  );
}
