"""
InstantID 參數網格搜尋測試腳本
測試不同 controlnet_conditioning_scale 參數對人臉一致性和真實感的影響
"""
import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.comfyui_service import generate_image_instantid, build_realism_prompt

# 測試配置
PARAMS_TO_TEST = [0.6, 0.7, 0.8, 0.9, 1.0]
SEEDS = [42, 123, 456]  # 3 個不同 seed

# 測試場景
TEST_SCENARIOS = [
    {
        "name": "gym_flash",
        "character_desc": "young Asian woman, athletic build, fit physique",
        "scene_prompt": "at a gym doing workout, wearing sports bra and leggings, sweaty after exercise",
        "camera_style": "night",  # 閃光燈模式
    },
    {
        "name": "outdoor_park",
        "character_desc": "young Asian woman, athletic build, natural beauty",
        "scene_prompt": "at a park, casual outfit, relaxed pose, natural daylight",
        "camera_style": "outdoor",  # 戶外陽光
    },
    {
        "name": "cafe_casual",
        "character_desc": "young Asian woman, casual style",
        "scene_prompt": "at a coffee shop, sitting by window, drinking coffee, casual clothes",
        "camera_style": "indoor",  # 咖啡廳日常
    },
]

# 參考人臉圖（需要高品質、正面、光線良好的圖片）
# 使用 Unsplash 公開圖片作為測試
REFERENCE_FACE_URL = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800"


async def test_single_config(
    param: float,
    scenario: Dict,
    seed: int,
    output_dir: str
) -> Dict:
    """測試單一參數配置"""
    
    # 建立 Prompt
    full_prompt = build_realism_prompt(
        character_desc=scenario["character_desc"],
        scene_prompt=scenario["scene_prompt"],
        camera_style=scenario["camera_style"]
    )
    
    print(f"  Testing: param={param}, seed={seed}, scene={scenario['name']}")
    
    try:
        image_url = await generate_image_instantid(
            face_image_url=REFERENCE_FACE_URL,
            prompt=full_prompt,
            seed=seed,
            controlnet_conditioning_scale=param  # 測試此參數
        )
        
        result = {
            "param": param,
            "scenario": scenario["name"],
            "seed": seed,
            "image_url": image_url,
            "prompt": full_prompt,
            "success": True,
            "error": None
        }
        
        # 儲存結果
        filename = f"{scenario['name']}_param{param}_seed{seed}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"    ✅ Success: {image_url}")
        return result
        
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        return {
            "param": param,
            "scenario": scenario["name"],
            "seed": seed,
            "image_url": None,
            "success": False,
            "error": str(e)
        }


async def run_grid_search():
    """執行完整的參數網格搜尋"""
    
    # 建立輸出目錄
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"test_results/instantid_params_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🔬 InstantID 參數網格搜尋")
    print(f"📁 輸出目錄: {output_dir}")
    print(f"🎯 測試矩陣: {len(PARAMS_TO_TEST)} params × {len(TEST_SCENARIOS)} scenarios × {len(SEEDS)} seeds = {len(PARAMS_TO_TEST) * len(TEST_SCENARIOS) * len(SEEDS)} 張圖")
    print()
    
    all_results = []
    
    for param in PARAMS_TO_TEST:
        print(f"\n📊 Testing controlnet_conditioning_scale = {param}")
        
        for scenario in TEST_SCENARIOS:
            print(f"  Scene: {scenario['name']} ({scenario['camera_style']})")
            
            for seed in SEEDS:
                result = await test_single_config(param, scenario, seed, output_dir)
                all_results.append(result)
                
                # 避免 API 限速，每次請求間隔 3 秒
                await asyncio.sleep(3)
    
    # 儲存總結報告
    summary = {
        "test_time": timestamp,
        "total_tests": len(all_results),
        "success_count": sum(1 for r in all_results if r["success"]),
        "failed_count": sum(1 for r in all_results if not r["success"]),
        "params_tested": PARAMS_TO_TEST,
        "scenarios": [s["name"] for s in TEST_SCENARIOS],
        "results": all_results
    }
    
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ 測試完成！")
    print(f"   成功: {summary['success_count']}")
    print(f"   失敗: {summary['failed_count']}")
    print(f"   報告: {summary_path}")
    
    return summary


if __name__ == "__main__":
    # 檢查 API Token
    if not os.getenv("REPLICATE_API_TOKEN"):
        print("❌ 錯誤: 未設定 REPLICATE_API_TOKEN")
        print("請在 .env 檔案中設定 REPLICATE_API_TOKEN")
        exit(1)
    
    print("⚠️  警告: 此測試將生成 45 張圖片")
    print("⚠️  預估費用: 約 $1.67 (45 × $0.037)")
    print()
    
    confirm = input("是否繼續？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消")
        exit(0)
    
    asyncio.run(run_grid_search())
