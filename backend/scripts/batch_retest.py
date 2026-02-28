"""
T6：批次回測腳本
生成 N 張圖（可指定不同場景/seed），對每張跑 Hive AI 檢測，
輸出通過率與詳細結果。

AC 目標：Hive score < 0.3（pass rate > 50%）
"""
import asyncio
import json
import os
import sys
from datetime import datetime

import httpx

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.comfyui_service import generate_image
from app.services.ai_detector_service import detect_ai_image

# 預設回測批次（可依需求擴充）
TEST_CASES = [
    {
        "name": "cafe_no_face",
        "prompt": (
            "A young East Asian woman with monolid eyes, straight black hair, light skin "
            "sitting at a messy Taipei coffee shop, caught mid-sentence with mouth slightly open, "
            "glistening forehead with light perspiration, wrinkled t-shirt with coffee stain, "
            "shot on iPhone with wide-angle distortion, harsh overhead fluorescent lighting, "
            "social media compression artifacts"
        ),
        "seed": 42,
        "face_image_url": "",
    },
    {
        "name": "cafe_with_face",
        "prompt": (
            "This young East Asian woman with monolid eyes, straight black hair, and light skin "
            "sitting at a messy Taipei coffee shop, caught mid-sentence with mouth slightly open, "
            "glistening forehead with light perspiration, wrinkled t-shirt with coffee stain, "
            "shot on iPhone with wide-angle distortion, harsh overhead fluorescent lighting, "
            "social media compression artifacts"
        ),
        "seed": 42,
        "face_image_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800",
    },
    {
        "name": "street_with_face",
        "prompt": (
            "This young East Asian woman with monolid eyes, straight black hair, and light skin "
            "walking on a busy Taipei street, looking down at phone, "
            "slightly squinting in bright daylight, wearing casual hoodie, hair slightly messy from wind, "
            "shot on iPhone candid street photography, harsh midday sunlight, "
            "slight motion blur, social media compression artifacts"
        ),
        "seed": 123,
        "face_image_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800",
    },
    {
        "name": "office_with_face",
        "prompt": (
            "This young East Asian woman with monolid eyes, straight black hair, and light skin "
            "at a cluttered office desk, staring at laptop screen with tired eyes, "
            "hair in loose messy bun, wearing wrinkled blouse, coffee cup beside keyboard, "
            "fluorescent office lighting, shot on iPhone from slightly above, "
            "social media compression artifacts"
        ),
        "seed": 456,
        "face_image_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800",
    },
]

HIVE_PASS_THRESHOLD = 0.3


async def run_case(case: dict) -> dict:
    name = case["name"]
    print(f"⏳ [{name}] 生圖中...")
    image_url = await generate_image(
        prompt=case["prompt"],
        seed=case["seed"],
        face_image_url=case["face_image_url"],
    )

    if not image_url:
        print(f"  ❌ [{name}] 生圖失敗")
        return {"name": name, "image_url": None, "hive_score": -1.0, "pass": False, "error": "generation failed"}

    print(f"  🖼  [{name}] → {image_url}")
    print(f"  🔍 [{name}] Hive 檢測中...")
    hive_score = await detect_ai_image(image_url)

    passed = hive_score != -1.0 and hive_score < HIVE_PASS_THRESHOLD
    status = "✅ PASS" if passed else ("⚠️  SKIP(no key)" if hive_score == -1.0 else "❌ FAIL")
    print(f"  {status} [{name}] Hive score = {hive_score:.3f}")

    return {
        "name": name,
        "image_url": image_url,
        "hive_score": hive_score,
        "pass": passed,
    }


async def run():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"test_results/batch_retest_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    print("🔬 T6 批次回測")
    print(f"📸 {len(TEST_CASES)} 個測試案例")
    print(f"🎯 AC 目標：Hive score < {HIVE_PASS_THRESHOLD}")
    print()

    results = []
    for i, case in enumerate(TEST_CASES):
        r = await run_case(case)
        results.append(r)
        with open(f"{output_dir}/{case['name']}.json", "w") as f:
            json.dump(r, f, indent=2)
        if i < len(TEST_CASES) - 1:
            await asyncio.sleep(10)  # 避免 rate limit

    # 統計
    valid = [r for r in results if r["hive_score"] != -1.0]
    passed = [r for r in valid if r["pass"]]
    pass_rate = len(passed) / len(valid) * 100 if valid else 0

    summary = {
        "test_time": timestamp,
        "total": len(results),
        "valid_hive": len(valid),
        "passed": len(passed),
        "pass_rate_pct": round(pass_rate, 1),
        "ac_met": pass_rate >= 50,
        "results": results,
    }
    with open(f"{output_dir}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print()
    print("=" * 50)
    print(f"📊 批次回測結果")
    print(f"   通過 / 有效 / 總計：{len(passed)} / {len(valid)} / {len(results)}")
    print(f"   通過率：{pass_rate:.1f}%  （AC 目標 ≥ 50%）")
    print(f"   AC 達成：{'✅ YES' if summary['ac_met'] else '❌ NO'}")
    print(f"   注意：Hive score = -1.0 表示未設定 HIVE_API_KEY，不計入通過率")
    print(f"\n📁 {output_dir}/summary.json")
    return summary


if __name__ == "__main__":
    asyncio.run(run())
