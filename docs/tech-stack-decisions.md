# 技術棧決策記錄 (ADR)

**日期**：2026-02-18
**狀態**：已確認（T0 執行）

## 決策

| 層次 | 技術選型 | 決策理由 |
|------|----------|---------|
| 前端 | Next.js 14 (TypeScript) | SSR 支援、Vercel 一鍵部署、生態系成熟 |
| 後端 | Python FastAPI | AI/ML 生態最豐富，與 ComfyUI/OpenAI SDK 整合最順 |
| 關係型 DB | PostgreSQL | 儲存人設卡、內容草稿、排程任務 |
| Vector DB | Pinecone | 管理型服務，免維運，適合 MVP 快速驗證 |
| 生圖引擎 | ComfyUI + SDXL/Flux | 本地可控，支援 LoRA/Embedding，API 呼叫靈活 |
| LLM | Claude 3.5 Sonnet（主）/ GPT-4o（視覺反推）| Claude 文字能力強；GPT-4o Vision 圖片分析 |
| IG 串接 | Instagram Graph API | 官方 API，支援排程發布 |
| 前端部署 | Vercel | Next.js 原生支援，免設定 |
| 後端部署 | Docker + Railway | 容器化方便遷移 |

## MVP 範圍界定

**包含**：三模組（Genesis Engine + Life Stream + Interaction Hub）
**不含**：付費機制（拆到 MMVP）、TikTok 串接（拆到 v2）、虛擬衣櫥（DP-2）
