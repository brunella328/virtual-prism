import json
import re
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.chat_session import ChatSession
from app.services.chat_session_storage import save_session, load_session

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
