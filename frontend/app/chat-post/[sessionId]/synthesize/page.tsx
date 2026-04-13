"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiGet, apiPost, apiPatch } from "@/lib/api";

type Status = "synthesizing" | "done" | "error";

export default function SynthesizePage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [status, setStatus] = useState<Status>("synthesizing");
  const [errorMessage, setErrorMessage] = useState("");
  const [editedText, setEditedText] = useState("");
  const [wordCount, setWordCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const applyDraftData = (data: { status: string; draft_text?: string; error_message?: string }) => {
    setStatus(data.status as Status);
    if (data.status === "done") {
      const text = data.draft_text ?? "";
      setEditedText(text);
      setWordCount(text.length);
    }
    if (data.status === "error") {
      setErrorMessage(data.error_message ?? "生成失敗，請重試");
    }
  };

  const startPolling = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const data = await apiGet(`/api/chat-sessions/${sessionId}/draft`);
        if (data.status === "done" || data.status === "error") {
          applyDraftData(data);
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {
        // ignore transient errors
      }
    }, 3000);
  };

  // Initial: trigger synthesize then start polling
  useEffect(() => {
    apiPost(`/api/chat-sessions/${sessionId}/synthesize`, {}).catch(() => {});
    startPolling();

    // Immediate first poll
    apiGet(`/api/chat-sessions/${sessionId}/draft`).then((data) => {
      if (data.status === "done" || data.status === "error") {
        applyDraftData(data);
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }).catch(() => {});

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditedText(e.target.value);
    setWordCount(e.target.value.length);
  };

  const handleRegenerate = () => {
    setStatus("synthesizing");
    setEditedText("");
    setWordCount(0);
    setErrorMessage("");
    apiPost(`/api/chat-sessions/${sessionId}/synthesize`, {}).catch(() => {});
    startPolling();
  };

  const handleConfirm = async () => {
    setSaving(true);
    try {
      await apiPatch(`/api/chat-sessions/${sessionId}/draft`, { draft_text: editedText });
      router.push(`/chat-post/${sessionId}/publish`);
    } catch {
      setSaving(false);
    }
  };

  // ── Loading state ──────────────────────────────────────────────
  if (status === "synthesizing") {
    return (
      <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-6">
        <div className="text-center">
          <div className="relative w-20 h-20 mx-auto mb-8">
            <div className="absolute inset-0 rounded-full border-2 border-purple-500/30 animate-ping" />
            <div
              className="absolute inset-2 rounded-full border-2 border-purple-400/50 animate-ping"
              style={{ animationDelay: "300ms" }}
            />
            <div className="absolute inset-4 rounded-full bg-purple-600 animate-pulse flex items-center justify-center">
              <span className="text-xl">✍️</span>
            </div>
          </div>
          <h2 className="text-xl font-semibold mb-2">AI 正在為你整理思路</h2>
          <p className="text-gray-500 text-sm">根據你的回答生成貼文草稿中…</p>
        </div>
      </main>
    );
  }

  // ── Error state ────────────────────────────────────────────────
  if (status === "error") {
    return (
      <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-6">
        <div className="text-center max-w-md">
          <p className="text-4xl mb-4">⚠️</p>
          <h2 className="text-xl font-semibold mb-2">生成失敗</h2>
          <p className="text-gray-400 text-sm mb-6">{errorMessage}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => router.back()}
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl text-gray-300 transition-colors"
            >
              返回修改答案
            </button>
            <button
              onClick={handleRegenerate}
              className="px-6 py-3 bg-purple-700 hover:bg-purple-600 rounded-xl text-white transition-colors"
            >
              重新生成
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ── Draft ready ────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center p-6 pt-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold">草稿預覽</h2>
          <span className="text-gray-500 text-sm">{wordCount} 字</span>
        </div>
        <p className="text-gray-500 text-sm mb-5">
          你可以直接編輯文字，完成後確認進入排程。
        </p>

        {/* Editable draft */}
        <textarea
          value={editedText}
          onChange={handleTextChange}
          rows={16}
          className="w-full bg-gray-800/80 border border-gray-700 rounded-2xl px-5 py-4 text-white text-base leading-relaxed focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none mb-4"
        />

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleRegenerate}
            className="px-5 py-3 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl text-sm transition-colors"
          >
            重新生成
          </button>
          <button
            onClick={handleConfirm}
            disabled={!editedText.trim() || saving}
            className="flex-1 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {saving ? "儲存中..." : "確認草稿，選擇排程時間 →"}
          </button>
        </div>
      </div>
    </main>
  );
}
