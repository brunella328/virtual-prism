from fastapi import APIRouter

router = APIRouter()

@router.post("/webhook/instagram")
async def instagram_webhook():
    """T10: 接收 IG 留言 Webhook"""
    pass

@router.get("/replies/pending/{persona_id}")
async def get_pending_replies(persona_id: str):
    """取得待確認回覆列表"""
    pass

@router.post("/replies/{reply_id}/send")
async def send_reply(reply_id: str):
    """確認發送回覆"""
    pass
