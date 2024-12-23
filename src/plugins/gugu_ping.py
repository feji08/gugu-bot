import os

from nonebot import on_command
from nonebot.adapters.qq.message import MessageSegment
from nonebot.adapters.qq import Bot, Event
from nonebot import on_regex
from nonebot.params import RegexMatched
from ..database import Session, User, EarlyBirdRecord

from src.plugins.group_manage import send_summary

ping = on_command("咕咕咕")

@ping.handle()
async def handle_first_receive(bot: Bot, event: Event):
    await ping.send("咕咕咕咕咕咕咕")

# 使用正则匹配 "偷看xxx的鸟鸟卡"
spy = on_regex(r"/偷看(?P<target>.+)的鸟鸟卡", priority=1, block=True)
@spy.handle()
async def handle_first_receive(bot: Bot, event: Event):
    # 打印事件的原始消息
    print(f"Event message: {event.get_message()}")
    # 手动解析正则
    import re
    match = re.match(r"/?偷看(?P<target>.+?)的鸟鸟卡", str(event.get_message()))
    if match:
        target = match.group("target")
        session = Session()
        try:
            # 查询用户 ID
            user = session.query(User).filter_by(nickname=target).first()
            if not user:
                await spy.send(f"没有叫{target}的咕咕哦（捂眼睛）~")
                return

            # 查询早鸟记录的 count 值
            record = session.query(EarlyBirdRecord).filter_by(user_id=user.user_id).first()

            # 返回结果
            await spy.send(
                f"{target}居然有{record.count}张鸟鸟卡！"
            )
        except Exception as e:
            await spy.send(f"偷看失败,鸟鸟卡被群主偷走了~")
        finally:
            session.close()
    else:
        await spy.send("叫错咕咕啦~")