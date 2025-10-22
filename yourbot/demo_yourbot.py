# -*- coding: utf-8 -*-
import asyncio
import os
import time

import botpy
from botpy import logging
from botpy.ext.cog_yaml import read
from botpy.message import GroupMessage
from botpy.message import C2CMessage
from botpy.types.message import Reference

test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))

_log = logging.get_logger()


class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")

    async def on_c2c_message_create(self, message: C2CMessage):
        _log.info(f"收到消息: {message.content} 来自 {message.author.user_openid}")
        msg_seq = int(time.time() * 1000 % 1000)
        await message._api.post_c2c_message(
            openid=message.author.user_openid, 
            msg_type=0, 
            msg_id=message.id, 
            msg_seq=msg_seq,
            content=f"我收到了你的消息：{message.content}"
        )
        
    async def on_group_at_message_create(self, message: GroupMessage):
        _log.info(f"收到 @ 消息: {message.content} 来自群聊 {message.group_openid}")
        msg_seq = int(time.time() * 1000 % 1000)
        message_reference = Reference(message_id=message.id)
        # 回复收到的 @ 消息
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            msg_seq=msg_seq,
            message_reference=message_reference,
            content=f"收到了消息：{message.content}"
        )
        _log.info(f"已回复：{message.content}")


if __name__ == "__main__":
    # 通过预设置的类型，设置需要监听的事件通道
    # intents = botpy.Intents.none()
    # intents.public_messages=True

    # 通过kwargs，设置需要监听的事件通道
    intents = botpy.Intents.all()
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])