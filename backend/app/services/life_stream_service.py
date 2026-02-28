import json
import os
import asyncio
import logging
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.services import comfyui_service
from app.services.persona_storage import load_persona
from app.services.schedule_storage import save_schedule, load_schedule
from app.services.cloudinary_service import upload_from_url

logger = logging.getLogger(__name__)

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SCENE_CAMERA_MAP = {
    "night": "night", "neon": "night", "bar": "night", "club": "night",
    "portrait": "portrait", "studio": "portrait",
    "outdoor": "outdoor", "beach": "outdoor", "park": "outdoor", "mountain": "outdoor",
    "indoor": "indoor", "cafe": "indoor", "office": "indoor", "home": "indoor",
}

SINGLE_POST_PROMPT = """你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃 1 篇 Instagram 圖文內容。

**重要：必須用繁體中文，且只輸出單一 JSON 物件，不要任何前綴說明或註解！**

輸出格式（嚴格的 JSON 物件）：
{
  "scene": "場景描述（中文，25字以內）",
  "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
  "scene_prompt": "詳細場景描述（英文，60-100字）：包含場景環境、光線、動作、表情、真實手機照片的物理缺陷（如：汗水閃爍、皮膚油光、衣服污漬與皺褶、頭髮黏臉、嘴微張、眼神看向畫面外、手機畸變、雜亂背景、harsh lighting、blown-out highlights、crushed shadows）。營造偷拍感與未修圖的真實瞬間。",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}"""

SCHEDULE_PROMPT = """你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃未來 3 天的 Instagram 圖文內容。

**重要：必須用繁體中文，且只輸出 JSON 陣列，不要任何前綴說明或註解！**

輸出格式（嚴格的 JSON 陣列，共 3 天）：
[
  {
    "day": 1,
    "scene": "場景描述（中文，25字以內）",
    "caption": "Instagram 文案（中文，含 1-2 個 emoji，80字以內）",
    "scene_prompt": "詳細場景描述（英文，60-100字）：包含場景環境、光線、動作、表情、**真實手機照片的物理缺陷**（如：汗水閃爍、皮膚油光、衣服污漬與皺褶、頭髮黏臉、嘴微張、眼神看向畫面外、手機畸變、雜亂背景、harsh lighting、blown-out highlights、crushed shadows）。營造「偷拍感」與「未修圖的真實瞬間」。不要描述人物基本外觀（臉型、髮色等由系統統一注入），但要描述當下的狀態細節",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }
]

scene_prompt 範例（V7 真實感版本，參考用）：
- 健身房："lying on gym mat after intense workout, exhausted expression with mouth slightly open panting, drenched in sweat with glistening forehead and collarbone, beads of perspiration visible, flushed red cheeks, clumped wet hair sticking to sweaty face and neck, eyes looking at water bottle off-camera, harsh overhead gym fluorescent creating blown-out highlights on sweaty skin, crushed shadows under equipment, messy gym clutter in background with towels and bottles, unstaged candid moment"
- 咖啡廳："at messy Taipei coffee shop, caught mid-sentence with mouth slightly open, glistening forehead with light perspiration, small mole on cheek, wrinkled t-shirt with visible coffee stain near collar, messy hair strands stuck to face, eyes looking at menu off-camera with natural gaze, cheap oxidized silver necklace visible, harsh overhead fluorescent creating half face in shadow, crushed blacks in dark areas, cluttered cafe background with cups and bags on table, social media compression artifacts feel"
- 夜市："eating noodles mid-chew with mouth open showing food, visible sauce stain on shirt collar, sweaty forehead glistening under harsh night market fluorescent, matted hair stuck to face from humidity, small mole visible on cheek, eyes looking down at bowl naturally, harsh overhead lighting creating blown-out highlights and crushed shadows, messy food stall background with equipment and condiment bottles visible through soft blur, unstaged candid eating moment"

確保 3 天場景多樣化（室內/室外、日間/夜間交替），符合人設生活風格。每個 scene_prompt 必須包含：
1. **真實瑕疵**：汗水、油光、污漬、皺褶、痣、不對稱
2. **動態瞬間**：嘴微張、眼神看向畫面外、mid-action
3. **光線缺陷**：harsh lighting、blown-out highlights、crushed shadows
4. **背景雜亂**：clutter、equipment、bottles、messy environment
5. **手機感**：candid、unstaged、social media compression feel"""

async def generate_weekly_schedule(persona_id: str, appearance_prompt: str = "") -> dict:
    """T6: 根據人設生成 3 天圖文排程（含生圖）

    persona JSON 直接從 storage 讀取，前端只需提供 persona_id。
    降低為 3 天以減少 API 呼叫次數，避免 rate limit。
    """
    # 從存儲讀取 persona（唯一來源，不依賴前端傳入）
    persona_data = load_persona(persona_id)
    if not persona_data:
        raise ValueError(f"Persona {persona_id} 不存在。請先完成 Onboarding 創建人設。")

    # persona dict 給 LLM 規劃用
    persona = persona_data.model_dump(exclude={"reference_face_url", "created_at", "id"})
    face_image_url = persona_data.reference_face_url or ""
    # appearance_prompt 優先用前端傳入的，fallback 到 persona 內儲存的
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
        system=SCHEDULE_PROMPT
    )
    
    schedule_raw = message.content[0].text.strip()
    
    # 提取 JSON（處理多種情況：markdown代碼塊、前綴文字等）
    if schedule_raw.startswith("```"):
        # 移除 ```json 和 ``` 標記
        schedule_raw = schedule_raw.split("```")[1]
        if schedule_raw.startswith("json"):
            schedule_raw = schedule_raw[4:].strip()
    
    # 找到第一個 [ 的位置（JSON 陣列起點）
    json_start = schedule_raw.find("[")
    if json_start > 0:
        schedule_raw = schedule_raw[json_start:]
    elif json_start == -1:
        logger.error(f"No JSON array found in Claude response: {schedule_raw[:500]}")
        raise ValueError("Claude 返回的內容中找不到 JSON 陣列，請重試。")
    
    # 解析 JSON
    try:
        schedule = json.loads(schedule_raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse schedule JSON. Raw response: {schedule_raw[:500]}")
        raise ValueError(
            f"❌ Claude 返回的排程格式錯誤（無法解析 JSON）。\n"
            f"錯誤位置：{e.msg} at line {e.lineno} column {e.colno}\n"
            f"請重試，或檢查 Claude 是否返回了說明文字而非純 JSON。"
        ) from e

    # Step 2: 為每天加入日期 + 呼叫生圖
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
            replicate_url = await comfyui_service.generate_image(
                prompt=full_prompt,
                seed=item.get("seed", 42),
                face_image_url=face_image_url,
                camera_style=camera_style,
            )
            seed_val = item.get("seed", 42)
            # 轉存 Cloudinary，避免 Replicate URL ~1h 失效
            if replicate_url:
                try:
                    image_url = await upload_from_url(
                        replicate_url,
                        folder=f"virtual_prism/{persona_id}"
                    )
                except Exception as cdn_err:
                    logger.warning(f"Cloudinary upload failed, using Replicate URL: {cdn_err}")
                    image_url = replicate_url
            else:
                image_url = None
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

    # 循序生成 3 天圖片（避免 Replicate 限速）
    days = []
    for i, item in enumerate(schedule):
        if i > 0:
            # 增加間隔到 10 秒，避免 429 Too Many Requests
            logger.info(f"⏳ Waiting 10 seconds before generating day {i+1}/3...")
            await asyncio.sleep(10)
        
        logger.info(f"🎨 Generating image for day {i+1}/3...")
        day_result = await generate_day(item, i)
        days.append(day_result)

    # 生圖完成後持久化排程
    save_schedule(persona_id, days)
    logger.info(f"Schedule saved for persona_id={persona_id} ({len(days)} days)")

    return {
        "persona_id": persona_id,
        "generated_at": datetime.now().isoformat(),
        "schedule": days
    }

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

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:].strip()
    json_start = raw.find("{")
    if json_start > 0:
        raw = raw[json_start:]
    try:
        item = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 返回格式錯誤：{e}") from e

    # Step 2: 生圖
    scene_prompt = item.get("scene_prompt", "lifestyle photo")
    scene_lower = scene_prompt.lower()
    camera_style = "lifestyle"
    for kw, style in SCENE_CAMERA_MAP.items():
        if kw in scene_lower:
            camera_style = style
            break

    full_prompt = comfyui_service.build_realism_prompt(
        character_desc=base_prompt,
        scene_prompt=scene_prompt,
        camera_style=camera_style,
    )

    try:
        replicate_url = await comfyui_service.generate_image(
            prompt=full_prompt,
            face_image_url=face_image_url,
            camera_style=camera_style,
        )
        if replicate_url:
            try:
                image_url = await upload_from_url(replicate_url, folder=f"virtual_prism/{persona_id}")
            except Exception as cdn_err:
                logger.warning(f"Cloudinary upload failed: {cdn_err}")
                image_url = replicate_url
        else:
            image_url = None
    except Exception as e:
        logger.error(f"Image generation failed for {date}: {e}")
        image_url = None

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
    # 取得人臉參考圖與外觀描述
    face_image_url = ""
    base_prompt = "attractive person, high quality, realistic"
    if persona_id:
        persona_data = load_persona(persona_id)
        if persona_data:
            face_image_url = persona_data.reference_face_url or ""

    # 將重繪指令加入場景描述
    enhanced_scene = f"{scene_prompt}, {instruction}" if instruction else scene_prompt

    scene_lower = enhanced_scene.lower()
    camera_style = "lifestyle"
    for kw, style in SCENE_CAMERA_MAP.items():
        if kw in scene_lower:
            camera_style = style
            break

    # 正確重建 prompt（與原始生成流程一致）
    full_prompt = comfyui_service.build_realism_prompt(
        character_desc=base_prompt,
        scene_prompt=enhanced_scene,
        camera_style=camera_style,
    )

    replicate_url = await comfyui_service.generate_image(
        prompt=full_prompt,
        face_image_url=face_image_url,
        camera_style=camera_style,
    )

    # 轉存 Cloudinary
    image_url = replicate_url
    if replicate_url:
        try:
            folder = f"virtual_prism/{persona_id}" if persona_id else "virtual_prism/regen"
            image_url = await upload_from_url(replicate_url, folder=folder)
        except Exception as cdn_err:
            logger.warning(f"Cloudinary upload failed on regen, using Replicate URL: {cdn_err}")

    return {
        "content_id": content_id,
        "image_url": image_url,
        "image_prompt": full_prompt,
        "seed": -1,
        "status": "draft"
    }
