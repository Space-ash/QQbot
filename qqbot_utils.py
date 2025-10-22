"""
qqbot_utils.py

职责（仅 botpy 相关）：
- 保存与 botpy 交互所需的配置（APP_ID、BOT_SECRET）
- 将事件字典构造成 botpy 期望的 MessagePayload
- 对特定事件（如 C2C_MESSAGE_CREATE、GROUP_AT_MESSAGE_CREATE）执行 botpy 调用流程

注意：
- 这里保留明文的 APP_ID/BOT_SECRET 仅用于你这台服务器，避免提交到公共仓库。
- 若需扩展机器人功能，请在本文件中新增/修改具体事件处理函数。
"""

from typing import Any, Dict, Callable, Optional

import botpy
from botpy.http import BotHttp
from botpy.api import BotAPI
from botpy.message import C2CMessage, GroupMessage
from botpy.types.gateway import MessagePayload

# 机器人配置（仅供本机使用，不要提交到仓库）
APP_ID = "your_app_id"  # 替换为你的 Bot AppID
BOT_SECRET = "your_bot_secret"  # Bot Secret / AppSecret


def build_message_payload(event: Dict[str, Any]) -> MessagePayload:
	"""将事件字典补全为 botpy 期望的 MessagePayload。

	兼容公域群/C2C消息：
	- GroupMessage 需要 `group_openid`、author.member_openid 等字段（若存在则透传）
	- BaseMessage 里使用 `msg_seq`，若事件中存在则透传
	"""
	payload: Dict[str, Any] = {
		"author": event.get("author", {}),
		"channel_id": event.get("channel_id", ""),  # C2C/群消息可能没有
		"content": event.get("content", ""),
		"guild_id": event.get("guild_id", ""),  # C2C/群消息可能没有
		"id": event.get("id", ""),
		"member": event.get("member", {}),  # C2C/群消息可能没有
		"message_reference": event.get("message_reference", {}),
		"mentions": event.get("mentions", []),
		"attachments": event.get("attachments", []),
		"seq": event.get("seq", 0),
		"seq_in_channel": event.get("seq_in_channel", ""),
		"timestamp": event.get("timestamp", ""),
	}
	# 额外透传 Group/C2C 常见字段（botpy 本地模型会读取这些 key）
	if "group_openid" in event:
		payload["group_openid"] = event.get("group_openid")
	if "msg_seq" in event:
		payload["msg_seq"] = event.get("msg_seq")
	return payload  # type: ignore[return-value]


# 你的自定义 bot 客户端（示例）
# 将具体业务逻辑放在 MyClient 内部，便于集中扩展
from yourbot.demo_yourbot import MyClient  # noqa: E402  (保持与原工程一致)

async def handle_event(event_type: str, event: Dict[str, Any], write_log: Optional[Callable[[str, str], None]] = None) -> None:
	"""统一入口：根据事件类型分发到具体 botpy 处理。

	仅在本文件扩展事件类型分支即可。
	"""
	if event_type == "C2C_MESSAGE_CREATE":
		await handle_c2c_message(event, write_log)
		return

	if event_type == "GROUP_AT_MESSAGE_CREATE":
		await handle_group_at_message(event, write_log)
		return

	# 未覆盖的事件类型：记录日志，便于后续在本文件继续扩展
	if write_log:
		write_log("INFO", f"[qqbot_utils] 未处理的事件类型: {event_type}")


async def handle_c2c_message(event: Dict[str, Any], write_log: Optional[Callable[[str, str], None]] = None) -> None:
	"""处理 C2C_MESSAGE_CREATE 事件并调用 botpy 完成消息响应。

	参数:
		event: 平台传入的事件数据（payload['d']）
		write_log: 可选的日志函数，签名形如 write_log(level, message)
	"""
	try:
		if write_log:
			write_log("INFO", "=== 进入 handle_c2c_message ===")

		event_id = event.get("id", "")

		# 初始化 botpy http 与 api
		http = BotHttp(timeout=5, app_id=APP_ID, secret=BOT_SECRET)
		if write_log:
			try:
				write_log("INFO", f"http vars: {vars(http)}")
			except Exception:
				write_log("INFO", "http vars: <unavailable>")

		api = BotAPI(http)
		if write_log:
			try:
				write_log("INFO", f"api vars: {vars(api)}")
			except Exception:
				write_log("INFO", "api vars: <unavailable>")

		# 构造 botpy 的消息对象
		payload: MessagePayload = build_message_payload(event)
		message = C2CMessage(api, event_id, payload)

		# 初始化你的客户端并调用对应的事件处理
		intents = botpy.Intents(public_messages=True)
		client = MyClient(intents=intents)
		await client.on_c2c_message_create(message)

		if write_log:
			write_log("INFO", "handle_c2c_message 执行完成")
	except Exception as e:
		if write_log:
			write_log("ERROR", f"handle_c2c_message 异常: {e}")
		raise


async def handle_group_at_message(event: Dict[str, Any], write_log: Optional[Callable[[str, str], None]] = None) -> None:
	"""处理 GROUP_AT_MESSAGE_CREATE 事件并调用 botpy 完成消息响应。

	参数:
		event: 平台传入的事件数据（payload['d']）
		write_log: 可选的日志函数，签名形如 write_log(level, message)
	"""
	try:
		if write_log:
			write_log("INFO", "=== 进入 handle_group_at_message ===")

		event_id = event.get("id", "")

		# 初始化 botpy http 与 api
		http = BotHttp(timeout=5, app_id=APP_ID, secret=BOT_SECRET)
		if write_log:
			try:
				write_log("INFO", f"http vars: {vars(http)}")
			except Exception:
				write_log("INFO", "http vars: <unavailable>")

		api = BotAPI(http)
		if write_log:
			try:
				write_log("INFO", f"api vars: {vars(api)}")
			except Exception:
				write_log("INFO", "api vars: <unavailable>")

		# 构造 botpy 的群消息对象
		payload: MessagePayload = build_message_payload(event)
		message = GroupMessage(api, event_id, payload)

		# 初始化你的客户端并调用对应的事件处理
		intents = botpy.Intents(public_messages=True)
		client = MyClient(intents=intents)
		await client.on_group_at_message_create(message)

		if write_log:
			write_log("INFO", "handle_group_at_message 执行完成")
	except Exception as e:
		if write_log:
			write_log("ERROR", f"handle_group_at_message 异常: {e}")
		raise
