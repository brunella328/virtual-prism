"""
Chat Sessions API — T1: 話題 → Claude Haiku 生成引導問題
"""
import json
import logging
import os

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.chat_session import ChatSession
from app.services.chat_session_storage import save_session

logger = logging.getLogger(__name__)
router = APIRouter()

client_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class CreateChatSessionRequest(BaseModel):
    persona_id: str
    topic: str


QUESTION_PROMPT_TEMPLATE = """你是一個專業的寫作教練，擅長幫助社群媒體創作者整理思路、產出真實有共鳴的內容。

用戶想寫一篇關於「{topic}」的社群貼文。

請生成 5 到 10 個引導問題，幫助他們深入思考這個話題，整理出獨特的個人觀點與故事細節。

要求：
- 問題要具體、有深度，能引發真實的個人回憶或感受
- 涵蓋不同角度：起因、過程、感受、收穫、對讀者的啟發
- 全部使用繁體中文
- 以 JSON 陣列格式回傳，不要有其他說明文字

範例格式：
["問題1", "問題2", "問題3"]"""


@router.post("/chat-sessions")
async def create_chat_session(req: CreateChatSessionRequest):
    """T1: 用戶輸入話題 → Claude Haiku 生成引導問題 → 回傳問題清單

    body: { persona_id: str, topic: str }
    回傳: { session_id: str, questions: list[str] }
    """
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="話題不能為空")
    if not req.persona_id.strip():
        raise HTTPException(status_code=400, detail="persona_id 不能為空")

    prompt = QUESTION_PROMPT_TEMPLATE.format(topic=req.topic.strip())

    try:
        response = await client_anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "API_RATE_LIMIT",
                "message": "⏳ Claude API 達到速率限制，請稍後再試（約 1-2 分鐘）",
            },
        )
    except Exception as e:
        logger.error(f"Claude API error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "CLAUDE_ERROR", "message": "AI 服務暫時無法使用，請稍後再試"},
        )

    # 解析回傳的 JSON 陣列
    raw_text = response.content[0].text.strip()
    try:
        # 嘗試直接解析
        questions = json.loads(raw_text)
        if not isinstance(questions, list):
            raise ValueError("Not a list")
    except (json.JSONDecodeError, ValueError):
        # 嘗試從文字中擷取 JSON 陣列
        import re
        match = re.search(r'\[.*?\]', raw_text, re.DOTALL)
        if match:
            try:
                questions = json.loads(match.group())
            except json.JSONDecodeError:
                questions = []
        else:
            questions = []

    # 過濾空字串，確保至少有一個問題
    questions = [q for q in questions if isinstance(q, str) and q.strip()]
    if not questions:
        logger.warning(f"Claude returned no parseable questions. Raw: {raw_text[:200]}")
        raise HTTPException(
            status_code=500,
            detail={"error": "PARSE_ERROR", "message": "AI 回傳格式異常，請再試一次"},
        )

    # 建立並儲存 session
    session = ChatSession(
        persona_id=req.persona_id,
        topic=req.topic.strip(),
        questions=questions,
    )
    try:
        save_session(session)
    except Exception as e:
        logger.error(f"Failed to save chat session: {e}")
        # 儲存失敗不影響回傳，仍回傳問題

    return {
        "session_id": session.id,
        "questions": questions,
    }
