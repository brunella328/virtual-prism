import json
import os
import anthropic
from dotenv import load_dotenv
from app.models.persona import AppearanceFeatures, PersonaCard, PersonaResponse
import uuid
import base64
from typing import Optional
from PIL import Image
import io

load_dotenv()

client_anthropic = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def compress_image(image_bytes: bytes, max_size: int = 1024, quality: int = 80) -> tuple[bytes, str]:
    """
    压缩图片以减少 token 消耗
    
    Args:
        image_bytes: 原始图片字节
        max_size: 最大边长（像素）
        quality: JPEG 质量（1-100）
    
    Returns:
        (压缩后的字节, MIME type)
    """
    img = Image.open(io.BytesIO(image_bytes))
    
    # 转换 RGBA 到 RGB（处理 PNG）
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # Alpha channel
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # 按比例缩放
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    # 压缩为 JPEG
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    
    return buffer.getvalue(), 'image/jpeg'

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
  "hair": "髮型髮色（英文，使用範圍描述保留彈性）：長度範圍、顏色範圍、可能的質地和樣式，如 long dark hair, can be straight or slightly wavy",
  "body": "體型（英文）：身材比例、肩寬、整體輪廓",
  "style": "穿搭風格（英文）：服裝類型和風格傾向",
  "image_prompt": "整合所有特徵的完整英文生圖 Prompt（100字以上），格式：[性別+年齡] [族裔] woman/man, [臉部細節], [膚色], [髮型], [體型], [風格特徵], ultra detailed face, consistent character, photorealistic"
}
重要：
1. image_prompt 必須極度詳細，讓 AI 生圖模型能在不同場景中生成同一個人
2. hair 欄位使用範圍描述（如 \"long dark hair\"），避免過於具體（如 \"shoulder-length layered black hair\"），保留後續調整彈性"""

async def create_persona(description: str, persona_id: Optional[str] = None, ig_user_id: Optional[str] = None) -> dict:
    """T3: 一句話 → 人設 JSON
    
    Args:
        description: 一句話人設描述
        persona_id: 指定的 persona ID（若無則自動生成 UUID）
        ig_user_id: 綁定的 IG 帳號 ID（可選）
    """
    from datetime import datetime
    
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
    
    persona_card = PersonaCard(
        id=pid,
        **persona_data,
        ig_user_id=ig_user_id,
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    return {
        "persona_id": pid,
        "persona": persona_card
    }

async def analyze_appearance(images, image_urls: Optional[list] = None) -> dict:
    """T2: 圖片 → 外觀描述（Claude Vision）
    
    Args:
        images: 上傳的圖片檔案列表
        image_urls: （可選）對應的圖片 URL 列表，若提供則保存第一張為 reference_face_url
    
    Returns:
        {
            "appearance": AppearanceFeatures,
            "reference_face_url": str  # 第一張圖片的 URL（用於 InstantID）
        }
    """
    image_contents = []
    for img in images:
        content = await img.read()
        # 压缩图片减少 token 消耗（最大 1024px，质量 80%）
        compressed, mime_type = compress_image(content, max_size=1024, quality=80)
        b64 = base64.b64encode(compressed).decode()
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64}"}
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

    # 重试机制：处理 rate limit（增加等待时间）
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    max_retries = 4  # 增加到 4 次
    for attempt in range(max_retries):
        try:
            response = await client_anthropic.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": claude_content}]
            )
            break  # 成功则跳出
        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                # 增加等待时间：20/40/60 秒
                wait_time = (attempt + 1) * 20
                logger.warning(f"⏳ Claude API rate limit, waiting {wait_time}s (attempt {attempt+1}/{max_retries})...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Claude API rate limit exceeded after {max_retries} retries")
                raise  # 最后一次仍失败则抛出异常

    raw = response.content[0].text
    # 從回應中取出 JSON
    import re
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    appearance_data = json.loads(match.group() if match else raw)
    
    # 保存第一張圖片的 URL 作為 reference_face_url
    reference_face_url = image_urls[0] if image_urls and len(image_urls) > 0 else ""
    
    return {
        "appearance": AppearanceFeatures(**appearance_data),
        "reference_face_url": reference_face_url
    }

async def confirm_persona(persona: PersonaCard, reference_face_url: Optional[str] = None) -> dict:
    """T4: 鎖定人設，儲存至存儲系統
    
    Args:
        persona: PersonaCard 物件
        reference_face_url: 人臉參考圖 URL（用於 InstantID）
    """
    from datetime import datetime
    
    persona_id = persona.id or str(uuid.uuid4())
    
    # 確保 persona 包含所有必要欄位
    if not persona.created_at:
        persona.created_at = datetime.utcnow().isoformat() + "Z"
    if reference_face_url and not persona.reference_face_url:
        persona.reference_face_url = reference_face_url
    
    # 儲存 persona 到檔案系統
    from app.services.persona_storage import save_persona
    save_persona(persona_id, persona)
    
    return {"persona_id": persona_id, "status": "locked", "persona": persona}
