"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

interface SessionData {
  id: string;
  topic: string;
  questions: string[];
  answers: string[];
}

export default function QuestionsPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [session, setSession] = useState<SessionData | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet(`/api/chat-sessions/${sessionId}`)
      .then((data) => {
        setSession(data);
        // 如果已有答案，從上次繼續
        const nextUnanswered = data.answers.findIndex((a: string) => !a);
        if (nextUnanswered !== -1) setCurrentIndex(nextUnanswered);
      })
      .catch(() => setError("無法載入問題"));
  }, [sessionId]);

  const handleNext = async () => {
    if (!answer.trim() || !session) return;
    setSaving(true);

    try {
      await apiPost(`/api/chat-sessions/${sessionId}/answer`, {
        question_index: currentIndex,
        answer: answer.trim(),
      });

      // 更新本地狀態
      const updated = { ...session };
      while (updated.answers.length <= currentIndex) updated.answers.push("");
      updated.answers[currentIndex] = answer.trim();
      setSession(updated);

      if (currentIndex < session.questions.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setAnswer("");
      }
    } catch {
      setError("儲存失敗，請重試");
    } finally {
      setSaving(false);
    }
  };

  const handleFinish = async () => {
    if (!answer.trim() || !session) return;
    setLoading(true);

    try {
      await apiPost(`/api/chat-sessions/${sessionId}/answer`, {
        question_index: currentIndex,
        answer: answer.trim(),
      });

      router.push(`/chat-post/${sessionId}/synthesize`);
    } catch {
      setError("儲存失敗，請重試");
    } finally {
      setLoading(false);
    }
  };

  if (error) return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <p className="text-red-400">{error}</p>
    </main>
  );

  if (!session) return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <p className="text-gray-400">載入中...</p>
    </main>
  );

  const isLast = currentIndex === session.questions.length - 1;
  const progressPercent = Math.round((currentIndex / session.questions.length) * 100);

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* 話題 */}
        <p className="text-gray-500 text-sm mb-1">話題：{session.topic}</p>

        {/* 進度條 */}
        <div className="flex items-center gap-3 mb-8">
          <div className="flex-1 bg-gray-800 rounded-full h-2">
            <div
              className="bg-purple-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-gray-400 text-sm whitespace-nowrap">
            {currentIndex + 1} / {session.questions.length}
          </span>
        </div>

        {/* 問題 */}
        <div className="bg-gray-800 rounded-xl p-5 mb-5">
          <p className="text-white text-lg leading-relaxed">
            {session.questions[currentIndex]}
          </p>
        </div>

        {/* 回答輸入 */}
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="輸入你的回答..."
          rows={5}
          className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none mb-4"
          disabled={saving || loading}
          autoFocus
        />

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <div className="flex gap-3">
          {/* 跳過 */}
          <button
            onClick={() => {
              if (isLast) router.push(`/chat-post/${sessionId}/synthesize`);
              else { setCurrentIndex(currentIndex + 1); setAnswer(""); }
            }}
            className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-3 rounded-xl transition-colors"
            disabled={saving || loading}
          >
            跳過
          </button>

          {/* 下一題 / 完成 */}
          {isLast ? (
            <button
              onClick={handleFinish}
              disabled={!answer.trim() || loading}
              className="flex-1 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors"
            >
              {loading ? "處理中..." : "完成，生成草稿"}
            </button>
          ) : (
            <button
              onClick={handleNext}
              disabled={!answer.trim() || saving}
              className="flex-1 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors"
            >
              {saving ? "儲存中..." : "下一題"}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
