import json
import os
import anthropic
from dotenv import load_dotenv
from app.models.persona import AppearanceFeatures, PersonaCard, PersonaResponse
import uuid
import base64
from typing import Optional

load_dotenv()

client_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PERSONA_PROMPT = """你是一個專業的虛擬人設設計師。
根據用戶的一句話描述，生成一個完整的 AI 網紅人設。

輸出必須是嚴格的 JSON 格式（不要有多餘文字）：
{
  "name": "人設的全名（中文名 + 英文名）",
  "occupation": "職業或身分",
  "personality_tags": ["個性標籤1", "個性標籤2", "個性標籤3"],
  "speech_pattern": "說話習慣或口癖，例如：愛用 🤙 表情符號，句尾常說「啊」",
  "values": ["核心價值觀1", "核心價值觀2"],
  "weekly_lifestyle": "一段描述這個人典型一週生活的文字，50字以內"
}"""

APPEARANCE_PROMPT = """你是一個專業的角色視覺分析師，專門為 AI 生圖（FLUX/SDXL）提取人物描述。
分析圖片中人物的外觀特徵，輸出高度詳細的描述，用於保持角色一致性。

輸出必須是嚴格的 JSON 格式（不要有多餘文字）：
{
  "facial_features": "臉部特徵（英文）：臉型、眼睛形狀/顏色、鼻子、嘴唇、眉毛等細節",
  "skin_tone": "膚色（英文）：具體描述如 warm olive skin tone, fair porcelain skin 等",
  "hair": "髮型髮色（英文）：長度、顏色、質地、樣式，如 long straight black hair with slight waves",
  "body": "體型（英文）：身材比例、肩寬、整體輪廓",
  "style": "穿搭風格（英文）：服裝類型和風格傾向",
  "image_prompt": "整合所有特徵的完整英文生圖 Prompt（100字以上），格式：[性別+年齡] [族裔] woman/man, [臉部細節], [膚色], [髮型], [體型], [風格特徵], ultra detailed face, consistent character, photorealistic"
}
重要：image_prompt 必須極度詳細，讓 AI 生圖模型能在不同場景中生成同一個人。"""

async def create_persona(description: str, persona_id: Optional[str] = None) -> dict:
    """T3: 一句話 → 人設 JSON
    
    persona_id: if provided (e.g. ig_user_id), use it; otherwise auto-generate UUID.
    """
    message = await client_anthropic.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": f"請根據以下描述生成人設：{description}"}
        ],
        system=PERSONA_PROMPT
    )
    
    raw = message.content[0].text
    persona_data = json.loads(raw)
    pid = persona_id or str(uuid.uuid4())
    
    return {
        "persona_id": pid,
        "persona": PersonaCard(**persona_data)
    }

async def analyze_appearance(images) -> dict:
    """T2: 圖片 → 外觀描述（GPT-4o Vision）"""
    image_contents = []
    for img in images:
        content = await img.read()
        b64 = base64.b64encode(content).decode()
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img.content_type};base64,{b64}"}
        })
    
    # 用 Claude Vision 替代 GPT-4o（同樣支援圖片輸入）
    claude_content = []
    for img_item in image_contents:
        if img_item["type"] == "image_url":
            url = img_item["image_url"]["url"]
            # data:image/jpeg;base64,xxxx → media_type + data
            header, data = url.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]
            claude_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data}
            })
    claude_content.append({
        "type": "text",
        "text": APPEARANCE_PROMPT + "\n\n請分析這些圖片中人物的外觀特徵，輸出 JSON 格式。"
    })

    response = await client_anthropic.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[{"role": "user", "content": claude_content}]
    )

    raw = response.content[0].text
    # 從回應中取出 JSON
    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    appearance_data = json.loads(match.group() if match else raw)
    return {"appearance": AppearanceFeatures(**appearance_data)}

async def confirm_persona(persona: PersonaCard) -> dict:
    """T4: 鎖定人設，儲存至 DB（DB 整合 T0+ 後實作）"""
    persona_id = str(uuid.uuid4())
    # TODO: 儲存至 PostgreSQL
    return {"persona_id": persona_id, "status": "locked", "persona": persona}
