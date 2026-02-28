"""
flux-kontext-max 人臉一致性測試
策略：把參考臉照 + 場景 prompt 餵給 kontext-max（它的 input_image 會保留人物特徵）

測試 3 個場景，確認同一張臉能否在不同場景中保持一致：
- 場景 1：咖啡廳（cafe）
- 場景 2：街道（street）
- 場景 3：辦公室（office）

使用 REFERENCE_FACE_URL 作為基礎臉孔
"""
import asyncio
import json
import os
import sys
from datetime import datetime

import httpx

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_BASE = "https://api.replicate.com/v1"

# 與 T7 測試相同的參考臉孔
REFERENCE_FACE_URL = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800"

# kontext-max 的 deployment model endpoint（不需要 version hash）
KONTEXT_MAX_URL = f"{REPLICATE_BASE}/models/black-forest-labs/flux-kontext-max/predictions"

# POC 驗證過的 cafe preset（亞洲人版）
POC_CAFE_PRESET = (
    "This young East Asian woman with monolid eyes, straight black hair, and light skin "
    "sitting at a messy Taipei coffee shop, caught mid-sentence with mouth slightly open, "
    "glistening forehead with light perspiration, cheap oxidized silver necklace, small mole on cheek, "
    "wrinkled t-shirt with coffee stain, messy hair strands stuck to face, eyes looking at menu off-camera, "
    "shot on iPhone with wide-angle distortion, harsh overhead fluorescent creating uneven lighting, "
    "half face in shadow, cluttered cafe background visible, cups and bags on table, "
    "social media compression artifacts"
)

# 街道場景（亞洲人版）
STREET_PRESET = (
    "This young East Asian woman with monolid eyes, straight black hair, and light skin "
    "walking on a busy Taipei street, looking down at phone, "
    "slightly squinting in bright daylight, wearing casual hoodie, hair slightly messy from wind, "
    "earphones in, cheap tote bag on shoulder, blurred pedestrians and storefronts in background, "
    "shot on iPhone candid street photography, harsh midday sunlight casting shadows under eyes, "
    "slight motion blur, social media compression artifacts, unedited mobile upload"
)

# 辦公室場景（亞洲人版）
OFFICE_PRESET = (
    "This young East Asian woman with monolid eyes, straight black hair, and light skin "
    "at a cluttered office desk, staring at laptop screen with tired eyes, "
    "slight eye bags, hair in loose messy bun, wearing wrinkled blouse, coffee cup beside keyboard, "
    "sticky notes on monitor, fluorescent office lighting creating flat harsh shadows, "
    "shot on iPhone from slightly above, blurred open-plan office background, "
    "social media compression artifacts, candid unposed moment"
)

SCENES = [
    ("cafe", POC_CAFE_PRESET),
    ("street", STREET_PRESET),
    ("office", OFFICE_PRESET),
]

SEED = 42


async def _poll(client, url, headers, timeout=180):
    for _ in range(timeout // 3):
        await asyncio.sleep(3)
        r = await client.get(url, headers=headers)
        d = r.json()
        if d.get("status") == "succeeded":
            out = d.get("output", [])
            return out[0] if isinstance(out, list) and out else out
        elif d.get("status") in ("failed", "canceled"):
            print(f"  ❌ Prediction {d.get('status')}: {d.get('error')}")
            return None
    return None


async def test_scene(scene_name: str, prompt: str, output_dir: str) -> dict:
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "input_image": REFERENCE_FACE_URL,
            "aspect_ratio": "4:5",
            "output_format": "jpg",
            "seed": SEED,
            "safety_tolerance": 5,
        }
    }

    print(f"⏳ 場景：{scene_name} ...")
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # 最多 retry 3 次（應對 429）
            for attempt in range(3):
                r = await client.post(KONTEXT_MAX_URL, json=payload, headers=headers)
                if r.status_code == 429:
                    wait = (attempt + 1) * 15
                    print(f"  ⏱ 429 rate limit，等 {wait}s (attempt {attempt+1})")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                break
            else:
                return {"scene": scene_name, "image_url": None, "success": False, "error": "Max retries (429)"}

            d = r.json()
            status = d.get("status")

            if status == "succeeded":
                out = d.get("output", [])
                image_url = out[0] if isinstance(out, list) and out else out
            elif d.get("output"):
                out = d["output"]
                image_url = out[0] if isinstance(out, list) else out
            else:
                poll_url = d.get("urls", {}).get("get", "")
                if poll_url:
                    image_url = await _poll(client, poll_url, headers) or ""
                else:
                    image_url = ""

        result = {"scene": scene_name, "image_url": image_url, "success": bool(image_url)}
        print(f"  ✅ → {image_url}")
    except Exception as e:
        result = {"scene": scene_name, "image_url": None, "success": False, "error": str(e)}
        print(f"  ❌ → {e}")

    with open(f"{output_dir}/{scene_name}.json", "w") as f:
        json.dump(result, f, indent=2)
    return result


async def run():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"test_results/kontext_face_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    print("🔬 flux-kontext-max 人臉一致性測試")
    print(f"📸 3 個場景：{[s for s, _ in SCENES]}")
    print(f"🎯 策略：input_image = 參考臉照，prompt = 場景描述")
    print(f"💰 預估費用：~$0.12（3 張）")
    print()

    results = []
    for i, (scene_name, prompt) in enumerate(SCENES):
        r = await test_scene(scene_name, prompt, output_dir)
        results.append(r)
        if i < len(SCENES) - 1:
            print(f"  ⏱ 等 10s 避免 rate limit...")
            await asyncio.sleep(10)

    summary = {
        "test_time": timestamp,
        "model": "flux-kontext-max",
        "strategy": "input_image=reference_face",
        "reference_face": REFERENCE_FACE_URL,
        "seed": SEED,
        "results": results,
    }
    with open(f"{output_dir}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print()
    print("📊 結果：")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['scene']} → {r.get('image_url', r.get('error'))}")
    print(f"\n📁 {output_dir}/summary.json")
    return summary


if __name__ == "__main__":
    if not REPLICATE_API_TOKEN:
        print("❌ 未設定 REPLICATE_API_TOKEN")
        exit(1)
    asyncio.run(run())
