import httpx
import os
import uuid
import json

COMFYUI_URL = os.getenv("COMFYUI_BASE_URL", "http://localhost:8188")

async def generate_image(prompt: str, seed: int = -1) -> str:
    """T5: 呼叫 ComfyUI 生成圖片，回傳圖片 URL"""
    # ComfyUI workflow JSON（SDXL 基礎 workflow）
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed if seed >= 0 else int(uuid.uuid4().int % (2**32)),
                "steps": 20,
                "cfg": 7,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly, blurry, low quality", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "virtual_prism", "images": ["8", 0]}}
    }
    
    async with httpx.AsyncClient() as client:
        # 提交 workflow
        resp = await client.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
        prompt_id = resp.json()["prompt_id"]
        
        # 輪詢結果（簡化版，生產環境應用 WebSocket）
        for _ in range(30):
            history = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
            data = history.json()
            if prompt_id in data:
                outputs = data[prompt_id]["outputs"]
                filename = outputs["9"]["images"][0]["filename"]
                return f"{COMFYUI_URL}/view?filename={filename}"
        
        raise TimeoutError("ComfyUI 生成超時")
