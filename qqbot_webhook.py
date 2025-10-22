from fastapi import FastAPI, Request, Response

import webhook_handler as wh


app = FastAPI()


@app.post("/qqbot-webhook/callback")
async def qqbot_callback(request: Request):
    wh.write_log("INFO", "=== 收到Webhook请求 ===")

    # 读取原始 body（验签与 op=13 都可能用到）
    raw = await request.body()
    payload = wh.parse_payload(raw)

    op = payload.get("op")

    # Op=13：回调地址验证
    if op == 13:
        return wh.handle_op_13_challenge(payload)

    # 普通事件（op=0）：验签 + 分发
    if op == 0:
        wh.verify_event_signature(raw, request.headers)

        event = payload.get("d", {})
        event_type = payload.get("t", "")

        # 分发事件（C2C_MESSAGE_CREATE 等）
        await wh.dispatch_event(event_type, event)
        return Response(status_code=200)

    # 其他 op（比如平台探测）直接 ACK
    return Response(status_code=200)
