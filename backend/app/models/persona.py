from pydantic import BaseModel
from typing import Optional, List

class PersonaCreate(BaseModel):
    description: str  # 一句話描述
    image_urls: List[str] = []  # 上傳的圖片 URLs

class AppearanceFeatures(BaseModel):
    facial_features: str
    skin_tone: str
    hair: str
    body: str
    style: str
    image_prompt: str  # 給 ComfyUI 用的生圖 Prompt

class PersonaCard(BaseModel):
    id: Optional[str] = None
    name: str
    occupation: str
    personality_tags: List[str]
    speech_pattern: str  # 口癖
    values: List[str]
    weekly_lifestyle: str
    appearance: Optional[AppearanceFeatures] = None
    reference_face_url: Optional[str] = None  # 人臉參考圖 URL（用於 InstantID）
    ig_user_id: Optional[str] = None  # 綁定的 IG 帳號 ID
    created_at: Optional[str] = None  # 建立時間（ISO 8601 格式）

class PersonaResponse(BaseModel):
    persona_id: str
    persona: PersonaCard
    appearance: AppearanceFeatures
