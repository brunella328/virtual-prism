"""
Image Generation Service — Virtual Prism
-----------------------------------------
Mode A (Kontext): 有人臉參考圖 → black-forest-labs/flux-kontext-max (保持同一張臉 + 真實感)
Mode B (Realism): 無參考圖     → xlabs-ai/flux-dev-realism (最佳真人感)

架構決策（2026-02-27）：
- InstantID 淘汰：AI 感太重，人臉過度平滑
- 改用 flux-kontext-max：input_image 傳參考臉照，模型自動保留人物特徵
- 真實感 + 人臉一致性兩者兼顧
"""
import os
import httpx
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

REPLICATE_BASE = "https://api.replicate.com/v1"

# flux-kontext-max 用 deployment endpoint（不需要 version hash）
KONTEXT_MAX_URL = f"{REPLICATE_BASE}/models/black-forest-labs/flux-kontext-max/predictions"

# V7 LDR 真實感模組（2026-02-21 整合）
BASE_IMPERFECTIONS = (
    "compressed jpeg artifacts, low bitrate compression, "
    "heavy digital noise, social media compression artifacts, "
    "poor focus on background, accidental finger slightly covering lens corner, "
    "messy background clutter"
)

LDR_REALISM_CORE = (
    "low dynamic range, heavy digital noise, shot on iPhone 12 front camera, "
    "yellowish white balance, blown-out highlights, crushed deep shadows, "
    "motion blur, poor focus, chromatic aberration, "
    "purple fringing on edges, harsh flat lighting, "
    "unedited raw mobile upload"
)

REALISM_SUFFIX = f"{LDR_REALISM_CORE}, {BASE_IMPERFECTIONS}"

# 攝影風格模板
CAMERA_STYLES = {
    "lifestyle": "shot on iPhone 15 Pro, candid mobile photography, natural colors",
    "portrait":  "shot on 85mm lens, f/1.8 aperture, creamy bokeh, Sony A7R IV, ISO 200",
    "outdoor":   "golden hour sunlight, warm tones, shot on iPhone 15 Pro, vertical composition",
    "indoor":    "soft window lighting, shot on 35mm lens, f/2.8, film grain",
    "night":     "neon city lights, night photography, ISO 3200, slight motion blur",
}

COLOR_CAST = {
    "night":     "blue tint from flash, direct flash photography, harsh shadows against the wall, oily skin reflection",
    "indoor":    "yellowish indoor lighting, warm color cast, slightly muted tones",
    "outdoor":   "natural daylight, slight color variation, warm afternoon glow",
    "portrait":  "studio white balance, neutral tones, balanced exposure",
    "lifestyle": "unedited mobile white balance, natural indoor-outdoor mix, slight yellow-green cast",
}


def build_realism_prompt(character_desc: str, scene_prompt: str, camera_style: str = "lifestyle") -> str:
    """
    V7 結構化 Prompt 架構：
    [主體描述] + [穿搭與動作] + [環境場景] + [攝影器材] + [場景化色偏] + [LDR 真實感]
    """
    camera = CAMERA_STYLES.get(camera_style, CAMERA_STYLES["lifestyle"])
    color_cast = COLOR_CAST.get(camera_style, COLOR_CAST["lifestyle"])

    return (
        f"A raw photo of {character_desc}, "
        f"{scene_prompt}, "
        f"{camera}, "
        f"{color_cast}, "
        f"{REALISM_SUFFIX}"
    )


async def _poll_prediction(client: httpx.AsyncClient, url: str, headers: dict, timeout: int = 180) -> Optional[str]:
    """Poll Replicate prediction until complete."""
    for _ in range(timeout // 3):
        await asyncio.sleep(3)
        r = await client.get(url, headers=headers)
        d = r.json()
        status = d.get("status")
        if status == "succeeded":
            output = d.get("output", [])
            return output[0] if isinstance(output, list) and output else output
        elif status in ("failed", "canceled"):
            logger.error(f"Prediction {status}: {d.get('error')}")
            return None
    return None


async def generate_image_kontext(
    face_image_url: str,
    prompt: str,
    seed: int = 42,
) -> str:
    """
    Mode A: flux-kontext-max — 保持人臉一致性 + 真實感
    (取代 InstantID，2026-02-27)

    Args:
        face_image_url: 人臉參考圖 URL（公開 HTTP(S) URL）
        prompt: 場景 Prompt（用 "This [描述] person" 開頭效果最佳）
        seed: 隨機種子

    Returns:
        生成圖片的 URL
    """
    if not REPLICATE_API_TOKEN:
        return ""

    if not face_image_url:
        logger.warning("generate_image_kontext called with empty face_image_url")
        return ""

    logger.info(f"Using flux-kontext-max for face consistency (seed={seed})")

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "input_image": face_image_url,
            "aspect_ratio": "4:5",
            "output_format": "jpg",
            "seed": seed % (2**32),
            "safety_tolerance": 5,
        }
    }

    for attempt in range(4):
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(KONTEXT_MAX_URL, json=payload, headers=headers)
            if r.status_code == 429:
                wait = (attempt + 1) * 15
                logger.warning(f"Rate limited (kontext-max), retrying in {wait}s (attempt {attempt+1})")
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            d = r.json()
            status = d.get("status")
            if status == "succeeded" or d.get("output"):
                out = d.get("output", [])
                return out[0] if isinstance(out, list) and out else out
            poll_url = d.get("urls", {}).get("get", "")
            return await _poll_prediction(client, poll_url, headers) or ""

    logger.error("All retries exhausted for flux-kontext-max image generation")
    return ""


async def generate_image_realism(
    prompt: str,
    seed: int = 42,
) -> str:
    """
    Mode B: flux-dev-realism（V7 LDR 真人感 + 429 retry）
    無參考臉照時使用
    """
    if not REPLICATE_API_TOKEN:
        return ""

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "39b3434f194f87a900d1bc2b6d4b983e90f0dde1d5022c27b52c143d670758fa",
        "input": {
            "prompt": prompt,
            "guidance": 2.5,
            "num_outputs": 1,
            "aspect_ratio": "4:5",
            "lora_strength": 0.8,
            "output_format": "jpg",
            "output_quality": 90,
            "num_inference_steps": 28,
        }
    }

    for attempt in range(4):
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            if r.status_code == 429:
                wait = (attempt + 1) * 10
                logger.warning(f"Rate limited (flux-dev-realism), retrying in {wait}s (attempt {attempt+1})")
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            d = r.json()
            if d.get("output"):
                out = d["output"]
                return out[0] if isinstance(out, list) else out
            poll_url = d.get("urls", {}).get("get", "")
            return await _poll_prediction(client, poll_url, headers) or ""

    logger.error("All retries exhausted for flux-dev-realism image generation")
    return ""


async def generate_image(
    prompt: str,
    seed: int = 42,
    face_image_url: str = "",
    camera_style: str = "lifestyle",
) -> str:
    """
    主入口：自動選擇生成模式
    - 有 face_image_url → flux-kontext-max（保持人臉 + 真實感）
    - 無             → flux-dev-realism（最佳真人感）
    """
    if not REPLICATE_API_TOKEN:
        logger.warning("REPLICATE_API_TOKEN not set, returning placeholder")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    if face_image_url:
        logger.info(f"Using flux-kontext-max for face consistency (seed={seed})")
        return await generate_image_kontext(face_image_url, prompt, seed)
    else:
        logger.info(f"Using flux-dev-realism (seed={seed})")
        return await generate_image_realism(prompt, seed)


async def generate_images_batch(
    prompts: list,
    seeds: list,
    face_image_url: str = "",
) -> list:
    """批次並發生成（最多 3 個並發）"""
    sem = asyncio.Semaphore(3)

    async def bounded(p, s):
        async with sem:
            return await generate_image(p, s, face_image_url)

    return await asyncio.gather(*[bounded(p, s) for p, s in zip(prompts, seeds)])
