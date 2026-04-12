import json
import re
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.chat_session import ChatSession
from app.services.chat_session_storage import save_session, load_session, update_session

router = APIRouter(prefix="/api/chat-sessions", tags=["chat-sessions"])

client = anthropic.Anthropic()


class CreateSessionRequest(BaseModel):
    persona_id: str
    topic: str


class CreateSessionResponse(BaseModel):
    session_id: str
    questions: list[str]


@router.post("", response_model=CreateSessionResponse)
async def create_chat_session(body: CreateSessionRequest):
    """建立聊天 session，用 Claude Haiku 生成引導問題"""
    prompt = f"""你是一個社群貼文寫作教練。用戶想寫一篇關於「{body.topic}」的社群媒體貼文。
請生成 5 到 10 個引導問題，幫助用戶整理思路、挖掘有價值的內容。
問題要具體、開放式，適合繁體中文的社群貼文風格。
請以 JSON 陣列格式回傳，例如：["問題1", "問題2", "問題3"]
只回傳 JSON 陣列，不要其他文字。"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # 嘗試解析 JSON
    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        # 嘗試從文字中提取 JSON 陣列
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            questions = json.loads(match.group())
        else:
            raise HTTPException(status_code=500, detail="Failed to parse questions from Claude")

    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=500, detail="No questions generated")

    session = ChatSession(
        persona_id=body.persona_id,
        topic=body.topic,
        questions=questions,
    )
    save_session(session)

    return CreateSessionResponse(session_id=session.id, questions=questions)


@router.get("/{session_id}")
async def get_chat_session(session_id: str):
    try:
        session = load_session(session_id)
        return session
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


class AnswerRequest(BaseModel):
    question_index: int
    answer: str


@router.post("/{session_id}/answer")
async def submit_answer(session_id: str, body: AnswerRequest):
    """儲存用戶對某題的回答"""
    try:
        session = load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

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


@router.post("/{session_id}/synthesize", status_code=202)
async def synthesize_draft(session_id: str):
    """觸發背景合成：Claude Sonnet 合成長文草稿"""
    import asyncio

    try:
        session = load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("questioning", "done"):
        raise HTTPException(status_code=409, detail=f"Session status is {session.status}")

    session.status = "synthesizing"
    update_session(session)

    asyncio.create_task(_do_synthesize(session_id))
    return {"session_id": session_id, "status": "synthesizing"}


async def _do_synthesize(session_id: str):
    """背景合成任務"""
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

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        draft_text = message.content[0].text.strip()

        session.draft_text = draft_text
        session.status = "done"
        update_session(session)

    except Exception as e:
        try:
            session = load_session(session_id)
            session.status = "error"
            session.draft_text = f"生成失敗：{str(e)}"
            update_session(session)
        except Exception:
            pass


@router.get("/{session_id}/draft")
async def get_draft(session_id: str):
    """輪詢草稿狀態"""
    try:
        session = load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "status": session.status,
        "draft_text": session.draft_text,
        "image_url": session.image_url,
    }
