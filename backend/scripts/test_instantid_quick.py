"""
InstantID 快速參數測試（選項 B - 修正版）
場景：咖啡廳
使用與 POC 驗證一致的 REALISM_V7_CASUAL prompt
測試 3 個 controlnet_conditioning_scale 參數：0.6, 0.8, 1.0
共 3 張圖，預估費用 ~$0.11
"""
import asyncio
import json
import os
import sys
import httpx
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_BASE = "https://api.replicate.com/v1"

# ── 與 poc.py 完全一致的 V7 prompt ──────────────────────────────
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

CASUAL_MODE = (
    "bland flat lighting, hazy atmosphere, low contrast, muted colors, "
    "slight lens smudge, wide angle distortion, cluttered cafe background"
)

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
# ────────────────────────────────────────────────────────────────

PARAMS_TO_TEST = [0.6, 0.8, 1.0]
SEED = 42

CHARACTER_DESC = "young Asian woman, casual style"
SCENE_PROMPT = "at a coffee shop, sitting by window, drinking coffee, casual clothes"
FULL_PROMPT = f"A raw photo of {CHARACTER_DESC}, {SCENE_PROMPT}, {REALISM_V7_CASUAL}"

REFERENCE_FACE_URL = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800"


async def _poll(client, url, headers, timeout=120):
    for _ in range(timeout // 3):
        await asyncio.sleep(3)
        r = await client.get(url, headers=headers)
        d = r.json()
        if d.get("status") == "succeeded":
            out = d.get("output", [])
            return out[0] if isinstance(out, list) and out else out
        elif d.get("status") in ("failed", "canceled"):
            return None
    return None


async def test_param(param: float, output_dir: str) -> dict:
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "2e4785a4d80dadf580077b2244c8d7c05d8e3faac04a04c02d8e099dd2876789",
        "input": {
            "image": REFERENCE_FACE_URL,
            "prompt": FULL_PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "num_inference_steps": 28,
            "guidance_scale": 2.5,
            "seed": SEED,
            "width": 832,
            "height": 1040,
            "controlnet_conditioning_scale": param,
            "enhance_nonface_region": True,
        }
    }

    print(f"⏳ controlnet_conditioning_scale = {param} ...")
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{REPLICATE_BASE}/predictions", json=payload, headers=headers)
            r.raise_for_status()
            d = r.json()
            if d.get("output"):
                out = d["output"]
                image_url = out[0] if isinstance(out, list) else out
            else:
                poll_url = d.get("urls", {}).get("get", "")
                image_url = await _poll(client, poll_url, headers) or ""

        result = {"param": param, "image_url": image_url, "success": True}
        print(f"  ✅ → {image_url}")
    except Exception as e:
        result = {"param": param, "image_url": None, "success": False, "error": str(e)}
        print(f"  ❌ → {e}")

    with open(f"{output_dir}/cafe_param{param}.json", 'w') as f:
        json.dump(result, f, indent=2)
    return result


async def run():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"test_results/instantid_quick_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    print(f"🔬 InstantID 快速測試（修正版，使用 REALISM_V7_CASUAL）")
    print(f"📸 場景：咖啡廳")
    print(f"🎯 params：{PARAMS_TO_TEST}（共 {len(PARAMS_TO_TEST)} 張，~$0.11）")
    print()

    results = []
    for i, param in enumerate(PARAMS_TO_TEST):
        r = await test_param(param, output_dir)
        results.append(r)
        if i < len(PARAMS_TO_TEST) - 1:
            await asyncio.sleep(3)

    summary = {"test_time": timestamp, "prompt_version": "REALISM_V7_CASUAL",
               "scene": "cafe", "params": PARAMS_TO_TEST, "seed": SEED, "results": results}
    with open(f"{output_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print("📊 結果：")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} param={r['param']} → {r.get('image_url', r.get('error'))}")
    print(f"\n📁 {output_dir}/summary.json")
    return summary


if __name__ == "__main__":
    if not REPLICATE_API_TOKEN:
        print("❌ 未設定 REPLICATE_API_TOKEN")
        exit(1)
    asyncio.run(run())
