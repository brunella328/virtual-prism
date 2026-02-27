"""
Cloudinary Upload Service — Virtual Prism
------------------------------------------
上傳人臉參考圖到 Cloudinary，取得永久公開 URL。
使用 signed upload（API key + secret）。

環境變數：
  CLOUDINARY_CLOUD_NAME  — Cloudinary 帳號的 cloud name
  CLOUDINARY_API_KEY     — API Key
  CLOUDINARY_API_SECRET  — API Secret
"""
import os
import hashlib
import time
import httpx
import logging

logger = logging.getLogger(__name__)

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")


def _make_signature(params: dict, api_secret: str) -> str:
    """產生 Cloudinary signed upload 的 SHA1 signature。"""
    # 排序、串接成 key=value&key=value，加上 api_secret 後 SHA1
    sorted_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    to_sign = sorted_str + api_secret
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()


async def upload_from_url(image_url: str, folder: str = "virtual_prism") -> str:
    """
    直接從 URL 上傳圖片到 Cloudinary（不需後端 download）。
    用於生成圖片轉存（Replicate → Cloudinary）。

    Args:
        image_url: 來源圖片 URL（如 Replicate CDN URL）
        folder: Cloudinary 資料夾（建議 'virtual_prism/{persona_id}'）

    Returns:
        永久公開 URL（https://res.cloudinary.com/...）
    """
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise ValueError("Cloudinary 環境變數未設定")

    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    timestamp = str(int(time.time()))

    params = {"folder": folder, "timestamp": timestamp}
    signature = _make_signature(params, CLOUDINARY_API_SECRET)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            upload_url,
            data={
                "api_key": CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "folder": folder,
                "file": image_url,
            },
        )

    if r.status_code != 200:
        logger.error(f"Cloudinary upload_from_url failed: {r.status_code} {r.text}")
        raise RuntimeError(f"Cloudinary 上傳失敗：HTTP {r.status_code}")

    data = r.json()
    secure_url = data.get("secure_url", "")
    if not secure_url:
        raise RuntimeError(f"Cloudinary 回傳格式異常：{data}")

    logger.info(f"Image uploaded to Cloudinary: {secure_url}")
    return secure_url


async def upload_face_image(file_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """
    上傳人臉參考圖到 Cloudinary（signed upload）。

    Returns:
        永久公開 URL（https://res.cloudinary.com/...）

    Raises:
        RuntimeError: 上傳失敗
        ValueError: 環境變數未設定
    """
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise ValueError(
            "CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET 未設定"
        )

    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    timestamp = str(int(time.time()))

    params = {"timestamp": timestamp}
    signature = _make_signature(params, CLOUDINARY_API_SECRET)

    ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
    filename = f"face.{ext}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            upload_url,
            data={
                "api_key": CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
            },
            files={"file": (filename, file_bytes, content_type)},
        )

    if r.status_code != 200:
        logger.error(f"Cloudinary upload failed: {r.status_code} {r.text}")
        raise RuntimeError(f"Cloudinary 上傳失敗：HTTP {r.status_code}")

    data = r.json()
    secure_url = data.get("secure_url", "")
    if not secure_url:
        raise RuntimeError(f"Cloudinary 回傳格式異常：{data}")

    logger.info(f"Face image uploaded to Cloudinary: {secure_url}")
    return secure_url
