"""
Image Generation Service — Virtual Prism
-----------------------------------------
Mode A (InstantID): 有人臉參考圖 → zsxkib/instant-id (保持同一張臉)
Mode B (Realism):   無參考圖     → xlabs-ai/flux-dev-realism (最佳真人感)

大哥的真人感 Prompt 指南已整合：
- 攝影器材模擬 (iPhone/DSLR)
- 皮膚真實質感關鍵字
- 結構化 prompt 架構
- Guidance Scale 2.5-3.5
"""
import os
import httpx
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# Model versions
MODEL_INSTANT_ID = "zsxkib/instant-id"
MODEL_FLUX_REALISM = "xlabs-ai/flux-dev-realism"
MODEL_FLUX_PRO = "black-forest-labs/flux-1.1-pro"

REPLICATE_BASE = "https://api.replicate.com/v1"

# 真人感必加關鍵字（基礎組）
REALISM_SUFFIX = (
    "candid photo, raw unedited photo, film grain, "
    "highly detailed skin texture, visible skin pores, slight skin imperfections, "
    "non-plastic skin, real person, not AI generated, "
    "natural color grading, VSCO film preset, "
    "8k, ultra sharp focus, depth of field"
)

NEGATIVE_PROMPT = (
    "plastic skin, oversmoothed, airbrushed, CGI, anime, illustration, "
    "cartoon, painting, render, 3d, artificial, fake, doll-like, "
    "perfect symmetry, overly saturated, HDR"
)

# 攝影風格模板（依場景類型選擇）
CAMERA_STYLES = {
    "lifestyle": "shot on iPhone 15 Pro, candid mobile photography, natural colors",
    "portrait":  "shot on 85mm lens, f/1.8 aperture, creamy bokeh, Sony A7R IV, ISO 200",
    "outdoor":   "golden hour sunlight, warm tones, shot on iPhone 15 Pro, vertical composition",
    "indoor":    "soft window lighting, shot on 35mm lens, f/2.8, film grain",
    "night":     "neon city lights, night photography, ISO 3200, slight motion blur",
}


def build_realism_prompt(character_desc: str, scene_prompt: str, camera_style: str = "lifestyle") -> str:
    """
    大哥的結構化 Prompt 架構：
    [主體描述] + [穿搭與動作] + [環境場景] + [攝影器材] + [氛圍關鍵字]
    """
    camera = CAMERA_STYLES.get(camera_style, CAMERA_STYLES["lifestyle"])
    return (
        f"A raw photo of {character_desc}, "
        f"{scene_prompt}, "
        f"{camera}, "
        f"{REALISM_SUFFIX}"
    )


async def _poll_prediction(client: httpx.AsyncClient, url: str, headers: dict, timeout: int = 120) -> Optional[str]:
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


async def generate_image_instantid(
    face_image_url: str,
    prompt: str,
    seed: int = 42,
) -> str:
    """
    Mode A: InstantID — 保持人臉一致性
    face_image_url: 已上傳的人臉圖 URL
    """
    if not REPLICATE_API_TOKEN:
        return ""

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "2e4785a4d80dadf580077b2244c8d7c05d8e3faac04a04c02d8e099dd2876789",
        "input": {
            "image": face_image_url,
            "prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "num_inference_steps": 30,
            "guidance_scale": 3.0,   # 大哥建議 2.5-3.5，避免塑膠感
            "seed": seed % (2**32),
            "width": 832,
            "height": 1040,           # 接近 4:5 比例（IG 最佳）
            "controlnet_conditioning_scale": 0.8,
            "enhance_nonface_region": True,
        }
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
        r.raise_for_status()
        d = r.json()
        if d.get("output"):
            out = d["output"]
            return out[0] if isinstance(out, list) else out
        poll_url = d.get("urls", {}).get("get", "")
        return await _poll_prediction(client, poll_url, headers) or ""


async def generate_image_realism(
    prompt: str,
    seed: int = 42,
) -> str:
    """
    Mode B: flux-schnell（穩定可用 + 真人感 prompt + 429 retry）
    """
    if not REPLICATE_API_TOKEN:
        return ""

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "num_outputs": 1,
            "aspect_ratio": "4:5",
            "output_format": "webp",
            "output_quality": 85,
            "seed": seed % (2**32),
            "go_fast": True,
        }
    }

    url = f"{REPLICATE_BASE}/models/black-forest-labs/flux-schnell/predictions"

    # 429 retry with backoff（最多 4 次，間隔 5/10/15 秒）
    for attempt in range(4):
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 429:
                wait = (attempt + 1) * 5
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt+1})")
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            d = r.json()
            if d.get("output"):
                out = d["output"]
                return out[0] if isinstance(out, list) else out
            poll_url = d.get("urls", {}).get("get", "")
            return await _poll_prediction(client, poll_url, headers) or ""

    logger.error("All retries exhausted for image generation")
    return ""


async def generate_image(
    prompt: str,
    seed: int = 42,
    face_image_url: str = "",
    camera_style: str = "lifestyle",
) -> str:
    """
    主入口：自動選擇生成模式
    - 有 face_image_url → InstantID（保持人臉）
    - 無             → flux-dev-realism（最佳真人感）
    """
    if not REPLICATE_API_TOKEN:
        logger.warning("REPLICATE_API_TOKEN not set, returning placeholder")
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    if face_image_url:
        logger.info(f"Using InstantID for face consistency (seed={seed})")
        return await generate_image_instantid(face_image_url, prompt, seed)
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
