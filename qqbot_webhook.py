# /opt/qqbot/qqbot_webhook.py
import os
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
import asyncio

import botpy
from botpy.http import BotHttp
from botpy.api import BotAPI
from botpy.message import C2CMessage
from botpy.types.gateway import MessagePayload
from yourbot.demo_yourbot import MyClient  # 导入 demo_chimera.py 中的 MyClient


# ---------------- 日志配置 ----------------
LOG_DIR = "/opt/qqbot/logs"     # 替换为你的webhook日志地址
os.makedirs(LOG_DIR, exist_ok=True)

def write_log(level: str, msg: str):
    """单文件临时日志，全部写到 qqbot_webhook.log"""
    path = os.path.join(LOG_DIR, "qqbot_webhook.log")
    line = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} | {level} | {msg}\n"
    with open(path, "a+", encoding="utf-8") as f:
        f.write(line)
        f.flush()
# -----------------------------------------


# ======= 明文写入（仅用于你这台服务器；不要提交到仓库）=======
APP_ID = "your_app_id_here"                     # 替换为你的 Bot AppID
BOT_SECRET = "your_bot_secret_here"             # Bot Secret / AppSecret
# ============================================================


app = FastAPI()


def seed_from_secret(secret: str) -> bytes:
    """
    用 AppSecret 生成 ed25519 seed（严格 32 字节）：
    1) 先 UTF-8 编码成 bytes
    2) 按 bytes 级别重复拼接直到 >=32
    3) 截断到 32 字节
    """
    if not secret:
        raise RuntimeError("BOT_SECRET is empty")
    b = secret.encode("utf-8")      # 先转 bytes（有非 ASCII 时尤为重要）
    while len(b) < 32:
        b = b + b                   # bytes 级别重复
    return b[:32]                   # 严格 32 字节


def build_message_payload(event: dict) -> MessagePayload:
    # 补全缺失字段
    return {
        "author": event.get("author", {}),
        "channel_id": event.get("channel_id", ""),  # C2C消息可能没有，可设为""
        "content": event.get("content", ""),
        "guild_id": event.get("guild_id", ""),      # C2C消息可能没有，可设为""
        "id": event.get("id", ""),
        "member": event.get("member", {}),          # C2C消息可能没有，可设为{}
        "message_reference": event.get("message_reference", {}),
        "mentions": event.get("mentions", []),
        "attachments": event.get("attachments", []),
        "seq": event.get("seq", 0),
        "seq_in_channel": event.get("seq_in_channel", ""),
        "timestamp": event.get("timestamp", ""),
    }
    

# 基于明文 secret 直接生成签名/验签用的密钥对象
_SIGNING_KEY = SigningKey(seed_from_secret(BOT_SECRET))
_VERIFY_KEY = _SIGNING_KEY.verify_key  # 由同一 seed 推导出的公钥


@app.post("/qqbot-webhook/callback")    # 改为你的回调地址
async def qqbot_callback(request: Request):
    write_log("INFO", "=== 收到Webhook请求 ===")
    # 读取原始 body（验签与 op=13 都可能用到）
    raw = await request.body()
    try:
        # 尝试解析 JSON 数据
        payload = json.loads(raw.decode("utf-8"))
        # 打印 payload 数据，确认内容是否正确
        write_log("INFO", json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    except Exception:
        write_log("ERROR", "Receive invalid JSON")
        raise HTTPException(status_code=400, detail="invalid json")

    op = payload.get("op")

    # --- Op=13：回调地址验证 ---
    if op == 13:
        write_log("INFO", "=== 回调地址验证 ===")
        d = payload.get("d") or {}
        plain_token = d.get("plain_token", "")
        event_ts = d.get("event_ts", "")

        # 按 "event_ts + plain_token" 计算签名（十六进制返回）
        msg = (event_ts + plain_token).encode("utf-8")
        signature = _SIGNING_KEY.sign(msg).signature.hex()

        return JSONResponse({"plain_token": plain_token, "signature": signature})

    # --- 普通事件（op=0）需要验签 ---
    if op == 0:
        write_log("INFO", "=== 普通事件 ===")
        sig_hex = request.headers.get("X-Signature-Ed25519", "")
        ts = request.headers.get("X-Signature-Timestamp", "")
        if not sig_hex or not ts:
            raise HTTPException(status_code=401, detail="missing signature headers")

        try:
            sig = bytes.fromhex(sig_hex)
        except Exception:
            raise HTTPException(status_code=401, detail="bad signature hex")

        # 签名体：timestamp + raw_body
        msg = ts.encode("utf-8") + raw
        try:
            _VERIFY_KEY.verify(msg, sig)  # 验证失败会抛出异常
        except BadSignatureError:
            raise HTTPException(status_code=401, detail="signature verify failed")
            
        # 获取事件数据
        event = payload.get("d", {})
        event_type = payload.get("t", "")
    
        # 检查是否为 C2C 消息创建事件
        if event_type == "C2C_MESSAGE_CREATE":
            write_log("INFO", "=== C2C_MESSAGE_CREATE事件 ===")
            http = BotHttp(timeout=5, app_id=APP_ID, secret=BOT_SECRET)
            write_log("INFO", f"http vars: {vars(http)}")
            api = BotAPI(http)
            write_log("INFO", f"api vars: {vars(api)}")
            event_id = event.get("id", "")
            payload = build_message_payload(event)
            message = C2CMessage(api, event_id, payload)
            intents = botpy.Intents(public_messages=True)
            client = MyClient(intents=intents)
            await client.on_c2c_message_create(message)

        # ---- 在这里把事件放到后台处理（异步队列/线程池），快速 ACK ----
        # 例如：event = payload.get("d", {}); event_type = payload.get("t")
        # TODO: dispatch(event_type, event)

        return Response(status_code=200)  # 立刻ACK，避免平台重试

    # 其他 op（比如平台探测）直接 ACK
    return Response(status_code=200)
