import httpx
import asyncio
import os
import uuid
import json
import base64
from typing import Optional

COMFYUI_URL = os.getenv("COMFYUI_BASE_URL", "http://localhost:8188")
MOCK_MODE = os.getenv("MOCK_COMFYUI", "true").lower() == "true"

# Mock 圖片（1x1 透明 PNG，Base64）
MOCK_IMAGE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

SDXL_WORKFLOW_TEMPLATE = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "ugly, blurry, low quality, deformed, nsfw"}},
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0], "seed": 0, "steps": 20,
            "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0
        }
    },
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "vp", "images": ["8", 0]}}
}

async def health_check() -> bool:
    """檢查 ComfyUI 是否可用"""
    if MOCK_MODE:
        return True
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{COMFYUI_URL}/system_stats")
            return resp.status_code == 200
    except Exception:
        return False

async def generate_image(
    prompt: str,
    negative_prompt: str = "ugly, blurry, low quality, deformed",
    seed: int = -1,
    steps: int = 20,
    width: int = 1024,
    height: int = 1024,
) -> dict:
    """
    生成圖片，回傳 {url, seed, prompt_id}
    MOCK_MODE=true 時回傳假圖（用於無 ComfyUI 環境的 Demo）
    """
    if MOCK_MODE:
        await asyncio.sleep(1)  # 模擬生成延遲
        mock_seed = seed if seed >= 0 else int(uuid.uuid4().int % (2**32))
        return {
            "url": f"data:image/png;base64,{MOCK_IMAGE_B64}",
            "seed": mock_seed,
            "prompt_id": str(uuid.uuid4()),
            "mock": True
        }

    workflow = json.loads(json.dumps(SDXL_WORKFLOW_TEMPLATE))
    workflow["6"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["text"] = negative_prompt
    workflow["3"]["inputs"]["seed"] = seed if seed >= 0 else int(uuid.uuid4().int % (2**32))
    workflow["3"]["inputs"]["steps"] = steps
    workflow["5"]["inputs"]["width"] = width
    workflow["5"]["inputs"]["height"] = height

    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=120) as client:
        # 提交任務
        resp = await client.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": client_id}
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # 輪詢結果（最多等 90 秒）
        for attempt in range(45):
            await asyncio.sleep(2)
            history_resp = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
            history = history_resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                if "9" in outputs and outputs["9"].get("images"):
                    img = outputs["9"]["images"][0]
                    img_url = f"{COMFYUI_URL}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img.get('type','output')}"
                    return {
                        "url": img_url,
                        "seed": workflow["3"]["inputs"]["seed"],
                        "prompt_id": prompt_id,
                        "mock": False
                    }

    raise TimeoutError(f"ComfyUI 生成超時（prompt_id: {prompt_id}）")

async def inpaint(
    image_url: str,
    mask_prompt: str,
    instruction: str,
    seed: int = -1,
) -> dict:
    """T8: In-painting — 根據指令修改圖片局部"""
    if MOCK_MODE:
        await asyncio.sleep(1)
        return {
            "url": f"data:image/png;base64,{MOCK_IMAGE_B64}",
            "seed": seed if seed >= 0 else 42,
            "mock": True
        }
    # TODO: 實作 ComfyUI Inpaint workflow
    raise NotImplementedError("Inpaint workflow 待實作（T8）")
