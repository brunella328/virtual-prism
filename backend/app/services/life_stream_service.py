import json
import os
import asyncio
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.services import comfyui_service

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SCHEDULE_PROMPT = """你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃未來 7 天的 Instagram 圖文內容。

輸出必須是嚴格的 JSON 陣列（無多餘文字），每天一個物件：
[
  {
    "day": 1,
    "scene": "場景描述（中文，25字以內）",
    "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
    "scene_prompt": "純場景描述（英文，只描述場景/環境/光線/氣氛，不含人物，30字以內）",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }
]
確保 7 天場景多樣化（室內/室外、日間/夜間交替），符合人設生活風格。
重要：scene_prompt 只描述場景環境，不要描述人物外觀（人物描述由系統統一注入）。"""

async def generate_weekly_schedule(persona_id: str, persona: dict, appearance_prompt: str = "", face_image_url: str = "") -> dict:
    """T6: 根據人設生成 7 天圖文排程（含生圖）"""
    
    base_prompt = appearance_prompt or "attractive person, high quality, realistic"
    start_date = datetime.now()

    # Step 1: LLM 規劃 7 天內容
    message = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"請為以下人設規劃 7 天 Instagram 內容：\n{json.dumps(persona, ensure_ascii=False)}"
        }],
        system=SCHEDULE_PROMPT
    )
    
    schedule_raw = message.content[0].text
    schedule = json.loads(schedule_raw)

    # Step 2: 為每天加入日期 + 呼叫生圖（並行）
    # 推斷攝影風格（依場景關鍵字）
    SCENE_CAMERA_MAP = {
        "night": "night", "neon": "night", "bar": "night", "club": "night",
        "portrait": "portrait", "studio": "portrait",
        "outdoor": "outdoor", "beach": "outdoor", "park": "outdoor", "mountain": "outdoor",
        "indoor": "indoor", "cafe": "indoor", "office": "indoor", "home": "indoor",
    }

    async def generate_day(item: dict, offset: int) -> dict:
        date = (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        scene_prompt = item.get("scene_prompt", item.get("image_prompt", "lifestyle photo"))

        # 推斷攝影風格
        scene_lower = scene_prompt.lower()
        camera_style = "lifestyle"
        for kw, style in SCENE_CAMERA_MAP.items():
            if kw in scene_lower:
                camera_style = style
                break

        # 大哥的結構化 prompt（角色描述優先）
        full_prompt = comfyui_service.build_realism_prompt(
            character_desc=base_prompt,
            scene_prompt=scene_prompt,
            camera_style=camera_style,
        )

        try:
            image_url = await comfyui_service.generate_image(
                prompt=full_prompt,
                seed=item.get("seed", 42),
                face_image_url=face_image_url,
                camera_style=camera_style,
            )
            seed_val = item.get("seed", 42)
        except Exception as e:
            logger.error(f"Image generation failed for day {item.get('day')}: {e}")
            image_url = None
            seed_val = -1

        return {
            **item,
            "image_prompt": full_prompt,
            "date": date,
            "image_url": image_url,
            "seed": seed_val,
            "status": "draft"
        }

    # 並行生成 7 天圖片（最多 3 個並發，避免超載）
    semaphore = asyncio.Semaphore(3)
    async def bounded_generate(item, offset):
        async with semaphore:
            return await generate_day(item, offset)

    days = await asyncio.gather(*[
        bounded_generate(item, i) for i, item in enumerate(schedule)
    ])

    return {
        "persona_id": persona_id,
        "generated_at": datetime.now().isoformat(),
        "schedule": days
    }

async def regenerate_content(content_id: str, original_prompt: str, instruction: str = "") -> dict:
    """T8: 一鍵重繪"""
    enhanced = f"{original_prompt}, {instruction}" if instruction else original_prompt
    image_url = await comfyui_service.generate_image(prompt=enhanced)
    return {
        "content_id": content_id,
        "image_url": image_url,
        "seed": -1,
        "status": "regenerated"
    }
