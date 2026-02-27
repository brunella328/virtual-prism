"""
Persona Storage Service
-----------------------
簡單的檔案存儲機制（暫不使用資料庫）
每個 persona 存為獨立的 JSON 檔案：data/personas/{persona_id}.json
"""
import json
import os
from typing import List, Optional
from pathlib import Path
from app.models.persona import PersonaCard

# 存儲目錄
STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "personas"


def ensure_storage_dir():
    """確保存儲目錄存在"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_persona(persona_id: str, persona: PersonaCard) -> None:
    """儲存 persona 到 JSON 檔案
    
    Args:
        persona_id: Persona 唯一 ID
        persona: PersonaCard 物件
    """
    ensure_storage_dir()
    file_path = STORAGE_DIR / f"{persona_id}.json"
    
    # 轉換為 dict 並儲存
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(persona.model_dump(), f, ensure_ascii=False, indent=2)


def load_persona(persona_id: str) -> Optional[PersonaCard]:
    """從 JSON 檔案讀取 persona
    
    Args:
        persona_id: Persona 唯一 ID
    
    Returns:
        PersonaCard 物件，若不存在則回傳 None
    """
    file_path = STORAGE_DIR / f"{persona_id}.json"
    
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return PersonaCard(**data)


def list_personas() -> List[PersonaCard]:
    """列出所有已儲存的 personas
    
    Returns:
        PersonaCard 物件列表
    """
    ensure_storage_dir()
    personas = []
    
    for file_path in STORAGE_DIR.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            personas.append(PersonaCard(**data))
        except Exception as e:
            # 跳過無效的 JSON 檔案
            print(f"Warning: Failed to load {file_path}: {e}")
            continue
    
    return personas


def delete_persona(persona_id: str) -> bool:
    """刪除 persona
    
    Args:
        persona_id: Persona 唯一 ID
    
    Returns:
        True 若刪除成功，False 若檔案不存在
    """
    file_path = STORAGE_DIR / f"{persona_id}.json"
    
    if not file_path.exists():
        return False
    
    file_path.unlink()
    return True
