import json
import os
import asyncio
import logging
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional
from app.services import comfyui_service
from app.services.persona_storage import load_persona
from app.services.schedule_storage import save_schedule, load_schedule
from app.services.cloudinary_service import upload_from_url

logger = logging.getLogger(__name__)

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCENE_CAMERA_MAP = {
    "night": "night", "neon": "night", "bar": "night", "club": "night",
    "portrait": "portrait", "studio": "portrait",
    "outdoor": "outdoor", "beach": "outdoor", "park": "outdoor", "mountain": "outdoor",
    "indoor": "indoor", "cafe": "indoor", "office": "indoor", "home": "indoor",
}

SCENE_PROMPT_QUALITY_GUIDE = """scene_prompt 範例（V7 真實感版本，參考用）：
- 健身房："lying on gym mat after intense workout, exhausted expression with mouth slightly open panting, drenched in sweat with glistening forehead and collarbone, beads of perspiration visible, flushed red cheeks, clumped wet hair sticking to sweaty face and neck, eyes looking at water bottle off-camera, harsh overhead gym fluorescent creating blown-out highlights on sweaty skin, crushed shadows under equipment, messy gym clutter in background with towels and bottles, unstaged candid moment"
- 咖啡廳："at messy Taipei coffee shop, caught mid-sentence with mouth slightly open, glistening forehead with light perspiration, small mole on cheek, wrinkled t-shirt with visible coffee stain near collar, messy hair strands stuck to face, eyes looking at menu off-camera with natural gaze, cheap oxidized silver necklace visible, harsh overhead fluorescent creating half face in shadow, crushed blacks in dark areas, cluttered cafe background with cups and bags on table, social media compression artifacts feel"
- 夜市："eating noodles mid-chew with mouth open showing food, visible sauce stain on shirt collar, sweaty forehead glistening under harsh night market fluorescent, matted hair stuck to face from humidity, small mole visible on cheek, eyes looking down at bowl naturally, harsh overhead lighting creating blown-out highlights and crushed shadows, messy food stall background with equipment and condiment bottles visible through soft blur, unstaged candid eating moment"

scene_prompt 必須包含：
1. **真實瑕疵**：汗水、油光、污漬、皺褶、痣、不對稱
2. **動態瞬間**：嘴微張、眼神看向畫面外、mid-action
3. **光線缺陷**：harsh lighting、blown-out highlights、crushed shadows
4. **背景雜亂**：clutter、equipment、bottles、messy environment
5. **手機感**：candid、unstaged、social media compression feel"""

SCENE_PROMPT_FIELD = (
    '"scene_prompt": "詳細場景描述（英文，60-100字）：包含場景環境、光線、動作、表情、'
    '**真實手機照片的物理缺陷**（如：汗水閃爍、皮膚油光、衣服污漬與皺褶、頭髮黏臉、嘴微張、'
    '眼神看向畫面外、手機畸變、雜亂背景、harsh lighting、blown-out highlights、crushed shadows）。'
    '營造「偷拍感」與「未修圖的真實瞬間」。不要描述人物基本外觀（臉型、髮色等由系統統一注入），'
    '但要描述當下的狀態細節"'
)

SINGLE_POST_PROMPT = f"""你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃 1 篇 Instagram 圖文內容。

**重要：必須用繁體中文，且只輸出單一 JSON 物件，不要任何前綴說明或註解！**

輸出格式（嚴格的 JSON 物件）：
{{
  "scene": "場景描述（中文，25字以內）",
  "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
  {SCENE_PROMPT_FIELD},
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}}

{SCENE_PROMPT_QUALITY_GUIDE}"""

SCHEDULE_PROMPT = f"""你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃未來 3 天的 Instagram 圖文內容。

**重要：必須用繁體中文，且只輸出 JSON 陣列，不要任何前綴說明或註解！**

輸出格式（嚴格的 JSON 陣列，共 3 天）：
[
  {{
    "day": 1,
    "scene": "場景描述（中文，25字以內）",
    "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
    {SCENE_PROMPT_FIELD},
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }}
]

確保 3 天場景多樣化（室內/室外、日間/夜間交替），符合人設生活風格。
{SCENE_PROMPT_QUALITY_GUIDE}"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_camera_style(scene_prompt: str) -> str:
    """從 scene_prompt 關鍵字推斷攝影風格，預設 'lifestyle'。"""
    scene_lower = scene_prompt.lower()
    for keyword, style in SCENE_CAMERA_MAP.items():
        if keyword in scene_lower:
            return style
    return "lifestyle"


def _extract_json_from_claude(raw: str, start_char: str) -> any:
    """從 Claude 回應中提取 JSON，處理 markdown code block 與前綴文字。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:].strip()
    idx = text.find(start_char)
    if idx == -1:
        raise ValueError(f"Claude 回應中找不到 JSON（找 '{start_char}'）：{text[:200]}")
    text = text[idx:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 回應 JSON 格式錯誤：{e}") from e


async def _generate_and_upload_image(
    full_prompt: str,
    face_image_url: str,
    persona_id: str,
    camera_style: str,
    seed: int = -1,
) -> Optional[str]:
    """生成圖片並上傳至 Cloudinary；失敗時 fallback 到 Replicate URL，生圖失敗回傳 None。"""
    try:
        replicate_url = await comfyui_service.generate_image(
            prompt=full_prompt,
            seed=seed,
            face_image_url=face_image_url,
            camera_style=camera_style,
        )
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None

    if not replicate_url:
        return None

    try:
        return await upload_from_url(replicate_url, folder=f"virtual_prism/{persona_id}")
    except Exception as cdn_err:
        logger.warning(f"Cloudinary upload failed, using Replicate URL: {cdn_err}")
        return replicate_url


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_weekly_schedule(persona_id: str, appearance_prompt: str = "") -> dict:
    """根據人設生成 3 天圖文排程（含生圖）"""
    persona_data = load_persona(persona_id)
    if not persona_data:
        raise ValueError(f"Persona {persona_id} 不存在。請先完成 Onboarding 創建人設。")

    persona = persona_data.model_dump(exclude={"reference_face_url", "created_at", "id"})
    face_image_url = persona_data.reference_face_url or ""
    base_prompt = (
        appearance_prompt
        or (persona_data.appearance.image_prompt if persona_data.appearance else "")
        or "attractive person, high quality, realistic"
    )
    start_date = datetime.now()

    # Step 1: LLM 規劃 3 天內容
    message = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"請為以下人設規劃 7 天 Instagram 內容：\n{json.dumps(persona, ensure_ascii=False)}"
        }],
        system=SCHEDULE_PROMPT,
    )
    schedule = _extract_json_from_claude(message.content[0].text, start_char="[")

    # Step 2: 循序生圖（避免 Replicate 限速）
    async def generate_day(item: dict, offset: int) -> dict:
        date = (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        scene_prompt = item.get("scene_prompt", item.get("image_prompt", "lifestyle photo"))
        camera_style = _infer_camera_style(scene_prompt)
        full_prompt = comfyui_service.build_realism_prompt(
            character_desc=base_prompt,
            scene_prompt=scene_prompt,
            camera_style=camera_style,
        )
        image_url = await _generate_and_upload_image(
            full_prompt=full_prompt,
            face_image_url=face_image_url,
            persona_id=persona_id,
            camera_style=camera_style,
            seed=item.get("seed", 42),
        )
        return {
            **item,
            "image_prompt": full_prompt,
            "date": date,
            "image_url": image_url,
            "seed": item.get("seed", 42) if image_url else -1,
            "status": "draft",
        }

    days = []
    for i, item in enumerate(schedule):
        if i > 0:
            logger.info(f"⏳ Waiting 10 seconds before generating day {i+1}/3...")
            await asyncio.sleep(10)
        logger.info(f"🎨 Generating image for day {i+1}/3...")
        days.append(await generate_day(item, i))

    save_schedule(persona_id, days)
    logger.info(f"Schedule saved for persona_id={persona_id} ({len(days)} days)")
    return {"persona_id": persona_id, "generated_at": datetime.now().isoformat(), "schedule": days}


async def generate_single_post(persona_id: str, date: str, appearance_prompt: str = "") -> dict:
    """月曆模式：為指定日期生成單篇貼文並 append 到排程"""
    persona_data = load_persona(persona_id)
    if not persona_data:
        raise ValueError(f"Persona {persona_id} 不存在。")

    persona = persona_data.model_dump(exclude={"reference_face_url", "created_at", "id"})
    face_image_url = persona_data.reference_face_url or ""
    base_prompt = (
        appearance_prompt
        or (persona_data.appearance.image_prompt if persona_data.appearance else "")
        or "attractive person, high quality, realistic"
    )

    # Step 1: LLM 規劃 1 篇內容
    message = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"請為以下人設規劃 1 篇 Instagram 內容（日期：{date}）：\n{json.dumps(persona, ensure_ascii=False)}"
        }],
        system=SINGLE_POST_PROMPT,
    )
    item = _extract_json_from_claude(message.content[0].text, start_char="{")

    # Step 2: 生圖
    scene_prompt = item.get("scene_prompt", "lifestyle photo")
    camera_style = _infer_camera_style(scene_prompt)
    full_prompt = comfyui_service.build_realism_prompt(
        character_desc=base_prompt,
        scene_prompt=scene_prompt,
        camera_style=camera_style,
    )
    image_url = await _generate_and_upload_image(
        full_prompt=full_prompt,
        face_image_url=face_image_url,
        persona_id=persona_id,
        camera_style=camera_style,
    )

    # Step 3: Append 到現有排程
    existing = load_schedule(persona_id)
    next_day = max((p.get("day", 0) for p in existing), default=0) + 1
    new_post = {
        **item,
        "day": next_day,
        "date": date,
        "image_url": image_url,
        "image_prompt": full_prompt,
        "seed": -1,
        "status": "draft",
    }
    save_schedule(persona_id, existing + [new_post])
    logger.info(f"Single post generated for persona={persona_id} date={date} day={next_day}")
    return new_post


async def regenerate_content(content_id: str, scene_prompt: str, instruction: str = "", persona_id: str = "") -> dict:
    """一鍵重繪：正確重建 prompt 並帶入 face_image_url"""
    face_image_url = ""
    base_prompt = "attractive person, high quality, realistic"
    if persona_id:
        persona_data = load_persona(persona_id)
        if persona_data:
            face_image_url = persona_data.reference_face_url or ""

    enhanced_scene = f"{scene_prompt}, {instruction}" if instruction else scene_prompt
    camera_style = _infer_camera_style(enhanced_scene)
    full_prompt = comfyui_service.build_realism_prompt(
        character_desc=base_prompt,
        scene_prompt=enhanced_scene,
        camera_style=camera_style,
    )
    image_url = await _generate_and_upload_image(
        full_prompt=full_prompt,
        face_image_url=face_image_url,
        persona_id=persona_id or "regen",
        camera_style=camera_style,
    )
    return {
        "content_id": content_id,
        "image_url": image_url,
        "image_prompt": full_prompt,
        "seed": -1,
        "status": "draft",
    }
