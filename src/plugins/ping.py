import os

from nonebot import on_command
from nonebot.adapters.qq.message import MessageSegment
from nonebot.adapters.qq import Bot, Event

from src.plugins.manage import send_summary

ping = on_command("咕咕咕")

@ping.handle()
async def handle_first_receive(bot: Bot, event: Event):
    await ping.send("咕咕咕咕咕咕咕")