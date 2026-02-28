#!/bin/bash
# T7 快速測試一鍵啟動腳本

echo "🐺 T7 - InstantID 參數測試"
echo "=========================================="
echo ""

# 切換到 backend 目錄
cd "$(dirname "$0")/.." || exit 1

# 檢查 .env
if [ ! -f ".env" ]; then
    echo "❌ 錯誤: .env 檔案不存在"
    exit 1
fi

# 檢查 API Token
if ! grep -q "REPLICATE_API_TOKEN" .env; then
    echo "❌ 錯誤: REPLICATE_API_TOKEN 未設定"
    exit 1
fi

echo "✅ 環境檢查通過"
echo ""

# 執行測試
python scripts/test_instantid_quick.py
