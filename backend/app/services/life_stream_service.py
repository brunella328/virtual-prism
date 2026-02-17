import json
import asyncio
import anthropic
from datetime import datetime, timedelta
from app.services import comfyui_service

client = anthropic.AsyncAnthropic()

SCHEDULE_PROMPT = """你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃未來 7 天的 Instagram 圖文內容。

輸出必須是嚴格的 JSON 陣列（無多餘文字），每天一個物件：
[
  {
    "day": 1,
    "scene": "場景描述（中文，25字以內）",
    "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
    "image_prompt": "SDXL 生圖 Prompt（英文，包含人設外觀特徵 + 場景，50字以內）",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }
]
確保 7 天場景多樣化（室內/室外、日間/夜間交替），符合人設生活風格。"""

async def generate_weekly_schedule(persona_id: str, persona: dict, appearance_prompt: str = "") -> dict:
    """T6: 根據人設生成 7 天圖文排程（含生圖）"""
    
    base_prompt = appearance_prompt or "attractive person, high quality, realistic"
    start_date = datetime.now()

    # Step 1: LLM 規劃 7 天內容
    message = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
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
    async def generate_day(item: dict, offset: int) -> dict:
        date = (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        full_prompt = f"{base_prompt}, {item['image_prompt']}"
        
        try:
            img_result = await comfyui_service.generate_image(prompt=full_prompt)
            image_url = img_result["url"]
            seed = img_result["seed"]
        except Exception as e:
            image_url = None
            seed = -1
        
        return {
            **item,
            "date": date,
            "image_url": image_url,
            "seed": seed,
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
    result = await comfyui_service.generate_image(prompt=enhanced)
    return {
        "content_id": content_id,
        "image_url": result["url"],
        "seed": result["seed"],
        "status": "regenerated"
    }


# Alias for regenerate (T8)
async def regenerate_content(content_id: str, original_prompt: str, instruction: str = "") -> dict:
    enhanced = f"{original_prompt}, {instruction}" if instruction else original_prompt
    result = await comfyui_service.generate_image(prompt=enhanced)
    return {
        "content_id": content_id,
        "image_url": result["url"],
        "seed": result["seed"],
        "status": "regenerated"
    }
