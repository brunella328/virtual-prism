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
    "perfect symmetry, overly saturated, studio lighting, "
    "professional headshot style, perfect skin, immaculate, "
    "oversharpened, HDR overprocessed, commercial photography look"
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
    
    # 加入真人感優化 suffix
    optimized_prompt = f"{prompt}, {REALISM_SUFFIX}"
    
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
    """測試 flux-dev-realism"""
    start_time = time.time()
    
    # 加入真人感優化 suffix
    optimized_prompt = f"{prompt}, {REALISM_SUFFIX}"
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "39b3434f820f5b0927e2306682bd58745d26764f70cfb2e76c01c5ed60dfb9c5",
        "input": {
            "prompt": optimized_prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "lora_strength": 0.8,
            "guidance_scale": 3.5,
            "num_inference_steps": 30,
            "seed": seed,
            "aspect_ratio": "4:5",
            "output_format": "jpg",
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
    """測試 flux-cinestill"""
    start_time = time.time()
    
    # 加入 CNSTLL trigger word + 真人感優化 suffix
    cinestill_prompt = f"CNSTLL {prompt}, {REALISM_SUFFIX}"
    
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "216a43b9a17eb45843819acee40659e5912e84fb60f04bd6bc0f6b15cdd45a78",
        "input": {
            "prompt": cinestill_prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "seed": seed,
            "output_format": "jpg",
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
                "creativity": 0.35,
                "resemblance": 0.6,
                "dynamic": 6,
                "num_inference_steps": 18,
            }
        }
        
        async with httpx.AsyncClient(timeout=180.0) as client:
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
    POC endpoint: 序列測試 4 個模型（避免 rate limit）
    """
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="REPLICATE_API_TOKEN not configured")
    
    logger.info(f"Starting model comparison with prompt: {req.prompt[:50]}...")
    
    # 序列執行，每個模型之間加 3 秒延遲避免 rate limit
    results = []
    
    # 1. flux-schnell
    logger.info("Testing flux-schnell...")
    results.append(await test_flux_schnell(req.prompt, req.seed))
    await asyncio.sleep(3)
    
    # 2. flux-dev-realism
    logger.info("Testing flux-dev-realism...")
    results.append(await test_flux_realism(req.prompt, req.seed))
    await asyncio.sleep(3)
    
    # 3. flux-cinestill
    logger.info("Testing flux-cinestill...")
    results.append(await test_flux_cinestill(req.prompt, req.seed))
    await asyncio.sleep(3)
    
    # 4. cinestill + clarity
    logger.info("Testing cinestill + clarity...")
    results.append(await test_cinestill_with_clarity(req.prompt, req.seed))
    
    return results
