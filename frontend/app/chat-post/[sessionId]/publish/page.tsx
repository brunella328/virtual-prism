"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";

export default function PublishPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;

  const draftFromQuery = searchParams.get("draft") ?? "";
  const [draft, setDraft] = useState(draftFromQuery);
  const [scheduledAt, setScheduledAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 預設排程時間：明天同一時間
  useEffect(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setSeconds(0, 0);
    // datetime-local 格式：YYYY-MM-DDTHH:mm
    const iso = tomorrow.toISOString().slice(0, 16);
    setScheduledAt(iso);
  }, []);

  const handlePublish = async () => {
    if (!draft.trim() || !scheduledAt) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/chat-sessions/${sessionId}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          final_text: draft,
          scheduled_at: new Date(scheduledAt).toISOString(),
        }),
      });

      if (!res.ok) throw new Error("發布失敗");

      // 成功，導向 dashboard
      router.push("/");
    } catch {
      setError("排程失敗，請重試");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center p-6 pt-12">
      <div className="w-full max-w-2xl">
        <h2 className="text-lg font-semibold mb-1">確認排程</h2>
        <p className="text-gray-500 text-sm mb-6">選擇發布時間，貼文將由系統自動發布到 Instagram。</p>

        {/* 草稿預覽 */}
        <div className="bg-gray-800/60 border border-gray-700 rounded-2xl p-5 mb-6">
          <p className="text-gray-400 text-xs mb-2 uppercase tracking-wide">草稿內容</p>
          <p className="text-white text-sm leading-relaxed whitespace-pre-wrap line-clamp-6">{draft}</p>
        </div>

        {/* 排程時間選擇 */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            排程時間
          </label>
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        <div className="flex gap-3">
          <button
            onClick={() => router.back()}
            className="px-5 py-3 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl text-sm transition-colors"
            disabled={loading}
          >
            返回編輯
          </button>
          <button
            onClick={handlePublish}
            disabled={!draft.trim() || !scheduledAt || loading}
            className="flex-1 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {loading ? "排程中..." : "確認排程 ✓"}
          </button>
        </div>
      </div>
    </main>
  );
}
