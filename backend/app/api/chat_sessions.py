"""
Chat Sessions API — full CRUD + synthesize flow
"""
import asyncio
import json
import logging
import os
import re

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.auth import get_current_user
from app.models.chat_session import ChatSession
from app.services.chat_session_storage import save_session, load_session, update_session

logger = logging.getLogger(__name__)
router = APIRouter()

client_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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


def _check_session_owner(session: ChatSession, current_user: dict) -> None:
    if session.user_id and session.user_id != current_user["uuid"]:
        raise HTTPException(status_code=403, detail="Access denied")


class CreateChatSessionRequest(BaseModel):
    persona_id: str
    topic: str


@router.post("/chat-sessions")
async def create_chat_session(
    req: CreateChatSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    """T1: 用戶輸入話題 → Claude Haiku 生成引導問題 → 回傳問題清單"""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="話題不能為空")
    if not req.persona_id.strip():
        raise HTTPException(status_code=400, detail="persona_id 不能為空")

    prompt = QUESTION_PROMPT_TEMPLATE.format(topic=req.topic.strip())

    try:
        response = await client_anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
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

    raw_text = response.content[0].text.strip()
    try:
        questions = json.loads(raw_text)
        if not isinstance(questions, list):
            raise ValueError("Not a list")
    except (json.JSONDecodeError, ValueError):
        match = re.search(r'\[.*?\]', raw_text, re.DOTALL)
        if match:
            try:
                questions = json.loads(match.group())
            except json.JSONDecodeError:
                questions = []
        else:
            questions = []

    questions = [q for q in questions if isinstance(q, str) and q.strip()]
    if not questions:
        logger.warning(f"Claude returned no parseable questions. Raw: {raw_text[:200]}")
        raise HTTPException(
            status_code=500,
            detail={"error": "PARSE_ERROR", "message": "AI 回傳格式異常，請再試一次"},
        )

    session = ChatSession(
        persona_id=req.persona_id,
        user_id=current_user["uuid"],
        topic=req.topic.strip(),
        questions=questions,
    )
    try:
        save_session(session)
    except Exception as e:
        logger.error(f"Failed to save chat session: {e}")

    return {
        "session_id": session.id,
        "questions": questions,
    }


@router.get("/chat-sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)
    return session


class AnswerRequest(BaseModel):
    question_index: int
    answer: str


@router.post("/chat-sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    body: AnswerRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)

    while len(session.answers) <= body.question_index:
        session.answers.append("")
    session.answers[body.question_index] = body.answer
    update_session(session)

    return {
        "session_id": session_id,
        "question_index": body.question_index,
        "total_answered": len([a for a in session.answers if a]),
        "total_questions": len(session.questions),
    }


@router.post("/chat-sessions/{session_id}/synthesize", status_code=202)
async def synthesize_draft(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)

    if session.status not in ("questioning", "done"):
        raise HTTPException(status_code=409, detail=f"Session status is {session.status}")

    session.status = "synthesizing"
    update_session(session)

    asyncio.create_task(_do_synthesize(session_id))
    return {"session_id": session_id, "status": "synthesizing"}


async def _do_synthesize(session_id: str):
    """背景合成任務（使用 async client，不阻塞 event loop）"""
    try:
        session = load_session(session_id)

        qa_text = "\n".join(
            f"Q{i+1}: {q}\nA: {session.answers[i] if i < len(session.answers) else '（略過）'}"
            for i, q in enumerate(session.questions)
        )

        prompt = f"""你是一個專業的社群媒體內容創作者，擅長用真實、有溫度的文字打動讀者。

用戶想寫一篇關於「{session.topic}」的社群貼文，以下是 AI 引導的問答內容：

{qa_text}

請根據上方的問答，幫用戶整理成一篇完整的社群媒體長文貼文。要求：
- 字數約 300-500 字（繁體中文）
- 語氣真實、自然，像在跟朋友分享
- 有開頭吸引人的一句話
- 內容有深度，分享真實感受和具體細節
- 結尾有行動呼召或問題引發互動
- 不要加 hashtag，不要標題

只回傳貼文內容本身，不要其他說明。"""

        response = await client_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        session.draft_text = response.content[0].text.strip()
        session.error_message = None
        session.status = "done"
        update_session(session)

    except Exception as e:
        logger.error(f"Synthesize failed for session {session_id}: {type(e).__name__}: {e}")
        try:
            session = load_session(session_id)
            session.status = "error"
            session.error_message = "AI 生成失敗，請重試"
            update_session(session)
        except Exception:
            pass


@router.get("/chat-sessions/{session_id}/draft")
async def get_draft(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)

    return {
        "session_id": session_id,
        "status": session.status,
        "draft_text": session.draft_text,
        "error_message": session.error_message,
        "image_url": session.image_url,
    }


class SaveDraftRequest(BaseModel):
    draft_text: str


@router.patch("/chat-sessions/{session_id}/draft")
async def save_draft(
    session_id: str,
    body: SaveDraftRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)

    session.draft_text = body.draft_text
    update_session(session)
    return {"session_id": session_id, "status": "saved"}


class PublishRequest(BaseModel):
    final_text: str
    scheduled_at: str  # ISO 8601


@router.post("/chat-sessions/{session_id}/publish")
async def publish_draft(
    session_id: str,
    body: PublishRequest,
    current_user: dict = Depends(get_current_user),
):
    import uuid
    from app.services.schedule_storage import load_schedule, save_schedule

    try:
        session = load_session(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_owner(session, current_user)

    post_id = str(uuid.uuid4())

    new_post = {
        "post_id": post_id,
        "day": None,
        "date": body.scheduled_at[:10],
        "scene": "chat_post",
        "caption": body.final_text,
        "image_url": session.image_url,
        "image_prompt": None,
        "scene_prompt": None,
        "status": "scheduled",
        "scheduled_at": body.scheduled_at,
        "job_id": None,
        "published_at": None,
        "ig_media_id": None,
        "error_message": None,
        "hashtags": [],
        "session_id": session_id,
        "content_type": "chat_post",
    }

    posts = load_schedule(session.persona_id)
    posts.append(new_post)
    save_schedule(session.persona_id, posts)

    session.status = "published"
    update_session(session)

    return {
        "post_id": post_id,
        "persona_id": session.persona_id,
        "scheduled_at": body.scheduled_at,
        "status": "scheduled",
    }
