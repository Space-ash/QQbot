"""
webhook_handler.py

职责（非 botpy 部分）：
- 日志写入
- 原始请求 payload 的解析
- 回调地址验证（op=13）签名计算
- 事件验签（op=0）
- 事件类型分发（内部调用 qqbot_utils 中的 botpy 处理函数）
"""

import os
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from nacl.signing import SigningKey
from nacl.exceptions import BadSignatureError

from qqbot_utils import BOT_SECRET, handle_event


# ---------------- 日志配置 ----------------
LOG_DIR = "/opt/qqbot/logs"  # 替换为你的 webhook 日志地址
os.makedirs(LOG_DIR, exist_ok=True)


def write_log(level: str, msg: str) -> None:
	"""单文件临时日志，全部写到 qqbot_webhook.log。"""
	path = os.path.join(LOG_DIR, "qqbot_webhook.log")
	line = f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} | {level} | {msg}\n"
	with open(path, "a+", encoding="utf-8") as f:
		f.write(line)
		f.flush()


def seed_from_secret(secret: str) -> bytes:
	"""用 AppSecret 生成 ed25519 seed（严格 32 字节）。"""
	if not secret:
		raise RuntimeError("BOT_SECRET is empty")
	b = secret.encode("utf-8")
	while len(b) < 32:
		b = b + b
	return b[:32]


# 基于明文 secret 生成签名/验签用的密钥对象
_SIGNING_KEY = SigningKey(seed_from_secret(BOT_SECRET))
_VERIFY_KEY = _SIGNING_KEY.verify_key


def parse_payload(raw: bytes) -> Dict[str, Any]:
	"""解析原始请求体为 JSON。解析失败抛出 400。"""
	try:
		payload = json.loads(raw.decode("utf-8"))
		# 记录 payload 以便排查
		try:
			write_log("INFO", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
		except Exception:
			write_log("INFO", "<payload log unavailable>")
		return payload
	except Exception:
		write_log("ERROR", "Receive invalid JSON")
		raise HTTPException(status_code=400, detail="invalid json")


def handle_op_13_challenge(payload: Dict[str, Any]) -> JSONResponse:
	"""处理回调地址验证（op=13）。返回 JSONResponse。"""
	write_log("INFO", "=== 回调地址验证 ===")
	d = payload.get("d") or {}
	plain_token = d.get("plain_token", "")
	event_ts = d.get("event_ts", "")

	msg = (event_ts + plain_token).encode("utf-8")
	signature = _SIGNING_KEY.sign(msg).signature.hex()
	return JSONResponse({"plain_token": plain_token, "signature": signature})


def verify_event_signature(raw: bytes, headers) -> None:
	"""验证普通事件（op=0）的签名。失败抛出 401。"""
	write_log("INFO", "=== 普通事件 ===")
	sig_hex = headers.get("X-Signature-Ed25519", "")
	ts = headers.get("X-Signature-Timestamp", "")
	if not sig_hex or not ts:
		raise HTTPException(status_code=401, detail="missing signature headers")

	try:
		sig = bytes.fromhex(sig_hex)
	except Exception:
		raise HTTPException(status_code=401, detail="bad signature hex")

	msg = ts.encode("utf-8") + raw
	try:
		_VERIFY_KEY.verify(msg, sig)
	except BadSignatureError:
		raise HTTPException(status_code=401, detail="signature verify failed")


async def dispatch_event(event_type: str, event: Dict[str, Any]) -> None:
	"""根据事件类型分发，实际处理统一委托给 qqbot_utils.handle_event。"""
	await handle_event(event_type, event, write_log)

