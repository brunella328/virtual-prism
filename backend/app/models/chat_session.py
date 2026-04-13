from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    persona_id: str
    user_id: Optional[str] = None
    topic: str
    questions: List[str] = []
    answers: List[str] = []
    draft_text: Optional[str] = None
    error_message: Optional[str] = None
    image_url: Optional[str] = None
    status: str = "questioning"  # questioning | synthesizing | done | published | error
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
