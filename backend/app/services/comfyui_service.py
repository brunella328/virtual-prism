"""
Image Generation Service
MVP: Replicate API with FLUX.1-schnell
Price: ~$0.003/image (13x cheaper than DALL-E 3)
"""
import os
import httpx
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_MODEL = "black-forest-labs/flux-schnell"
REPLICATE_API_URL = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"

async def generate_image(prompt: str, seed: int = 42) -> str:
    """
    呼叫 Replicate FLUX.1-schnell API 生成圖片。
    返回圖片 URL（Replicate CDN）。
    若 REPLICATE_API_TOKEN 未設定，返回 placeholder。
    """
    if not REPLICATE_API_TOKEN:
        logger.warning("REPLICATE_API_TOKEN not set, returning placeholder")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",  # 同步等待結果（最多 60 秒）
    }

    payload = {
        "input": {
            "prompt": prompt,
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "webp",
            "output_quality": 80,
            "seed": seed % (2**32),  # FLUX seed range
        }
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        # 建立 prediction（帶 Prefer: wait 會同步等待）
        resp = await client.post(REPLICATE_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        # 如果 Prefer: wait 生效，output 直接在回應裡
        if data.get("output"):
            urls = data["output"]
            return urls[0] if isinstance(urls, list) else urls

        # Fallback: polling（部分情況需要）
        prediction_url = data.get("urls", {}).get("get", "")
        if not prediction_url:
            logger.error("No prediction URL returned")
            return ""

        for _ in range(30):  # 最多等 60 秒
            await asyncio.sleep(2)
            poll = await client.get(prediction_url, headers=headers)
            poll_data = poll.json()
            status = poll_data.get("status")
            if status == "succeeded":
                output = poll_data.get("output", [])
                return output[0] if output else ""
            elif status in ("failed", "canceled"):
                logger.error(f"Prediction {status}: {poll_data.get('error')}")
                return ""

    return ""


async def generate_images_batch(prompts: List[str], seeds: List[int]) -> List[str]:
    """批次生成多張圖片（並發）"""
    tasks = [generate_image(p, s) for p, s in zip(prompts, seeds)]
    return await asyncio.gather(*tasks)
