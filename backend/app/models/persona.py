from pydantic import BaseModel, field_validator
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
    content_types: Optional[List[str]] = None  # 預設內容類型（1-3 種），None 表示使用預設值
    created_at: Optional[str] = None  # 建立時間（ISO 8601 格式）
    
    @field_validator('content_types')
    @classmethod
    def validate_content_types(cls, v):
        # 允許 None（向後相容）或空list
        if v is None or len(v) == 0:
            return v
            
        allowed_types = ['educational', 'entertainment', 'promotional', 'engagement', 'personal_story']
        
        # 檢查數量限制：最多 3 個
        if len(v) > 3:
            raise ValueError('content_types must contain at most 3 items')
        
        # 檢查值是否在允許清單內
        for content_type in v:
            if content_type not in allowed_types:
                raise ValueError(f'Invalid content_type: {content_type}. Allowed values: {", ".join(allowed_types)}')
        
        # 檢查是否有重複值
        if len(v) != len(set(v)):
            raise ValueError('content_types must not contain duplicates')
        
        return v

class PersonaResponse(BaseModel):
    persona_id: str
    persona: PersonaCard
    appearance: AppearanceFeatures
