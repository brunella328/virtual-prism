"""
POC API — Model Comparison
用於測試不同模型的生成品質差異
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import httpx
import logging
import os
import time
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/poc", tags=["POC"])

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_BASE = "https://api.replicate.com/v1"

# 基礎物理缺陷層（全場景適用）
BASE_IMPERFECTIONS = (
    "compressed jpeg artifacts, low bitrate compression, "
    "heavy digital noise, social media compression artifacts, "
    "poor focus on background, accidental finger slightly covering lens corner, "
    "messy background clutter"
)

# LDR 真實感核心（低動態範圍邏輯）
LDR_REALISM_CORE = (
    "low dynamic range, heavy digital noise, shot on iPhone 12 front camera, "
    "yellowish white balance, blown-out highlights, crushed deep shadows, "
    "motion blur, poor focus, chromatic aberration, "
    "purple fringing on edges, harsh flat lighting, "
    "unedited raw mobile upload"
)

# 場景模組 1：閃光燈模式（室內/夜間自拍）
FLASH_MODE = (
    "direct flash photography, high contrast, harsh shadows against the wall, "
    "oily skin reflection, slight red-eye effect, dark underexposed background, "
    "blue tint from flash"
)

# 場景模組 2：平淡日常模式（咖啡廳/戶外）
CASUAL_MODE = (
    "bland flat lighting, hazy atmosphere, low contrast, muted colors, "
    "slight lens smudge, wide angle distortion, cluttered cafe background"
)

# V7 整合版：閃光燈健身房自拍
REALISM_V7_FLASH_GYM = (
    f"{LDR_REALISM_CORE}, {FLASH_MODE}, {BASE_IMPERFECTIONS}, "
    "dripping sweat, glistening skin after workout, drenched in perspiration, "
    "beads of sweat on forehead and collarbone, skin flushed and red from exercise, "
    "clumped wet hair, sweaty matted hair sticking to neck, messy strands plastered to forehead, "
    "harsh overhead fluorescent lighting, blown-out highlights on sweaty skin, "
    "mouth slightly open panting, eyes looking at something off-camera, "
    "small mole on cheek, uneven skin pigmentation, minor acne scar, "
    "wearing cheap oxidized necklace, simple ring, "
    "wrinkled clothes with sweat stains, fabric creases, "
    "workout equipment in background, water bottles, towels, gym clutter, "
    "bad gym lighting, unstaged, accidental selfie, candid moment"
)

# V7 整合版：平淡日常模式
REALISM_V7_CASUAL = (
    f"{LDR_REALISM_CORE}, {CASUAL_MODE}, {BASE_IMPERFECTIONS}, "
    "candid moment, looking at something off-camera, natural expression, "
    "small mole on cheek, uneven skin pigmentation, "
    "wearing simple everyday clothes, fabric wrinkles, "
    "cafe interior or street background, everyday life scene"
)

NEGATIVE_PROMPT = (
    "plastic skin, oversmoothed, airbrushed, CGI, anime, illustration, "
    "cartoon, painting, render, 3d, artificial, fake, doll-like, "
    "perfect symmetry, overly saturated, studio lighting, "
    "professional headshot style, perfect skin, immaculate, "
    "oversharpened, HDR overprocessed, commercial photography look, "
    "professional photography, DSLR, perfect focus, clean background"
)


class ModelComparisonRequest(BaseModel):
    prompt: str
    seed: int = 42


class ModelResult(BaseModel):
    model_name: str
    image_url: str
    generation_time: float
    cost_estimate: float
    error: Optional[str] = None


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


async def test_flux_schnell(prompt: str, seed: int) -> ModelResult:
    """測試 flux-schnell（現用基準）"""
    start_time = time.time()
    
    # 加入 V7 閃光燈健身房真實感 suffix
    optimized_prompt = f"{prompt}, {REALISM_V7_FLASH_GYM}"
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = {
        "input": {
            "prompt": optimized_prompt,
            "num_outputs": 1,
            "aspect_ratio": "4:5",
            "output_format": "jpg",
            "output_quality": 90,
            "seed": seed,
            "go_fast": True,
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            url = f"{REPLICATE_BASE}/models/black-forest-labs/flux-schnell/predictions"
            r = await client.post(url, json=payload, headers=headers)
            
            if r.status_code == 429:
                await asyncio.sleep(10)  # 等待 10 秒後重試
                r = await client.post(url, json=payload, headers=headers)
            
            r.raise_for_status()
            d = r.json()
            
            if d.get("output"):
                out = d["output"]
                image_url = out[0] if isinstance(out, list) else out
            else:
                poll_url = d.get("urls", {}).get("get", "")
                image_url = await _poll_prediction(client, poll_url, headers) or ""
            
            generation_time = time.time() - start_time
            return ModelResult(
                model_name="flux-schnell (現用)",
                image_url=image_url,
                generation_time=generation_time,
                cost_estimate=0.003
            )
    except Exception as e:
        logger.error(f"flux-schnell failed: {e}")
        return ModelResult(
            model_name="flux-schnell (現用)",
            image_url="",
            generation_time=0,
            cost_estimate=0.003,
            error=str(e)
        )


async def test_flux_realism(prompt: str, seed: int) -> ModelResult:
    """測試 flux-dev-realism (V7：LDR低動態範圍+物理缺陷+閃光燈模式)"""
    start_time = time.time()
    
    # 加入 V7 LDR 真實感：物理缺陷+閃光燈健身房場景
    optimized_prompt = f"{prompt}, {REALISM_V7_FLASH_GYM}"
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "39b3434f194f87a900d1bc2b6d4b983e90f0dde1d5022c27b52c143d670758fa",
        "input": {
            "prompt": optimized_prompt,
            "guidance": 2.5,  # 降至2.0-2.8讓AI「不那麼聽話」，產生更多隨機瑕疵
            "num_outputs": 1,
            "aspect_ratio": "4:5",
            "lora_strength": 0.8,
            "output_format": "jpg",
            "output_quality": 90,
            "num_inference_steps": 28,  # 降至25-30避免過度銳化
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            
            if r.status_code == 429:
                await asyncio.sleep(10)
                r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            
            r.raise_for_status()
            d = r.json()
            
            if d.get("output"):
                out = d["output"]
                image_url = out[0] if isinstance(out, list) else out
            else:
                poll_url = d.get("urls", {}).get("get", "")
                image_url = await _poll_prediction(client, poll_url, headers) or ""
            
            generation_time = time.time() - start_time
            return ModelResult(
                model_name="flux-dev-realism",
                image_url=image_url,
                generation_time=generation_time,
                cost_estimate=0.037
            )
    except Exception as e:
        logger.error(f"flux-dev-realism failed: {e}")
        return ModelResult(
            model_name="flux-dev-realism",
            image_url="",
            generation_time=0,
            cost_estimate=0.037,
            error=str(e)
        )


async def test_flux_cinestill(prompt: str, seed: int) -> ModelResult:
    """測試 flux-cinestill（V7 LDR 版本）"""
    start_time = time.time()
    
    # 加入 CNSTLL trigger word + V7 真實感
    cinestill_prompt = f"CNSTLL, {prompt}, {REALISM_V7_FLASH_GYM}"
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "216a43b9975de9768114644bbf8cd0cba54a923c6d0f65adceaccfc9383a938f",
        "input": {
            "prompt": cinestill_prompt,
            "model": "dev",
            "lora_scale": 0.6,
            "num_outputs": 1,
            "aspect_ratio": "4:5",
            "output_format": "jpg",
            "guidance_scale": 3.5,
            "output_quality": 90,
            "num_inference_steps": 28,
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            
            if r.status_code == 429:
                await asyncio.sleep(10)
                r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            
            r.raise_for_status()
            d = r.json()
            
            if d.get("output"):
                out = d["output"]
                image_url = out[0] if isinstance(out, list) else out
            else:
                poll_url = d.get("urls", {}).get("get", "")
                image_url = await _poll_prediction(client, poll_url, headers) or ""
            
            generation_time = time.time() - start_time
            return ModelResult(
                model_name="flux-cinestill",
                image_url=image_url,
                generation_time=generation_time,
                cost_estimate=0.014
            )
    except Exception as e:
        logger.error(f"flux-cinestill failed: {e}")
        return ModelResult(
            model_name="flux-cinestill",
            image_url="",
            generation_time=0,
            cost_estimate=0.014,
            error=str(e)
        )


async def test_cinestill_with_clarity(prompt: str, seed: int) -> ModelResult:
    """測試 flux-cinestill + clarity-upscaler"""
    start_time = time.time()
    
    try:
        # Step 1: 生成基礎圖
        base_result = await test_flux_cinestill(prompt, seed)
        if not base_result.image_url or base_result.error:
            return ModelResult(
                model_name="cinestill + clarity",
                image_url="",
                generation_time=0,
                cost_estimate=0.025,
                error=base_result.error or "Base generation failed"
            )
        
        # Step 2: Clarity upscale
        headers = {
            "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json",
        }
        clarity_payload = {
            "version": "dfad41707589d68ecdccd1dfa600d55a208f9310748e44bfe35b4a6291453d5e",
            "input": {
                "image": base_result.image_url,
                "prompt": "masterpiece, best quality, highres",
                "negative_prompt": "(worst quality, low quality, normal quality:2)",
                "creativity": 0.35,
                "resemblance": 0.6,
                "dynamic": 6,
                "num_inference_steps": 18,
                "scale_factor": 1,  # 不放大，只優化質量
            }
        }
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{REPLICATE_BASE}/predictions", json=clarity_payload, headers=headers)
            
            if r.status_code == 429:
                await asyncio.sleep(10)
                r = await client.post(f"{REPLICATE_BASE}/predictions", json=clarity_payload, headers=headers)
            
            r.raise_for_status()
            d = r.json()
            
            if d.get("output"):
                image_url = d["output"]
            else:
                poll_url = d.get("urls", {}).get("get", "")
                image_url = await _poll_prediction(client, poll_url, headers) or ""
            
            generation_time = time.time() - start_time
            return ModelResult(
                model_name="cinestill + clarity",
                image_url=image_url,
                generation_time=generation_time,
                cost_estimate=0.025  # 0.014 + 0.011
            )
    except Exception as e:
        logger.error(f"cinestill+clarity failed: {e}")
        return ModelResult(
            model_name="cinestill + clarity",
            image_url="",
            generation_time=0,
            cost_estimate=0.025,
            error=str(e)
        )


@router.post("/model-comparison", response_model=List[ModelResult])
async def model_comparison(req: ModelComparisonRequest):
    """
    POC endpoint: 測試 flux-dev-realism V7
    
    V7 更新：LDR 低動態範圍邏輯 + 物理缺陷三大面向
    - 畫質：JPEG 壓縮痕跡、數位雜訊
    - 動態範圍：blown-out highlights（死白）+ crushed shadows（死黑）
    - 色彩：閃光燈藍調 / 室內黃綠偏色
    """
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="REPLICATE_API_TOKEN not configured")
    
    logger.info(f"Starting V7 LDR realism test with prompt: {req.prompt[:50]}...")
    
    # 單一模型測試
    results = []
    
    # flux-dev-realism (V7: LDR + 物理缺陷)
    logger.info("Testing flux-dev-realism V7 (LDR + physical imperfections)...")
    results.append(await test_flux_realism(req.prompt, req.seed))
    
    return results
