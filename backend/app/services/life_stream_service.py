import json
import anthropic
import uuid

client = anthropic.AsyncAnthropic()

SCHEDULE_PROMPT = """你是一個 AI 網紅內容規劃師。
根據以下人設 JSON，為這個 AI 網紅規劃未來 7 天的 Instagram 圖文內容。

輸出必須是嚴格的 JSON 陣列（不要有多餘文字）：
[
  {
    "day": 1,
    "date": "YYYY-MM-DD",
    "scene": "場景描述（中文，30字以內）",
    "caption": "Instagram 文案（中文，含 emoji，100字以內）",
    "image_prompt": "場景的英文生圖 Prompt，適合 SDXL，需包含人設外觀特徵"
  }
]
確保 7 天內容多樣化，符合人設的生活風格。"""

async def generate_weekly_schedule(persona_id: str) -> dict:
    """T6: 根據人設生成 7 天圖文排程"""
    # TODO: 從 DB 讀取人設
    # persona = await db.get_persona(persona_id)
    
    # Placeholder 測試
    persona_json = '{"name": "測試人設", "weekly_lifestyle": "熱愛戶外活動"}'
    
    message = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": f"請為以下人設規劃 7 天內容：{persona_json}"}
        ],
        system=SCHEDULE_PROMPT
    )
    
    schedule = json.loads(message.content[0].text)
    return {"persona_id": persona_id, "schedule": schedule}

async def regenerate(content_id: str, instruction: str = "") -> dict:
    """T8: 一鍵重繪"""
    # TODO: 從 DB 讀取原始 image_prompt，附加 instruction 後重新呼叫 ComfyUI
    return {"content_id": content_id, "status": "regenerating"}
