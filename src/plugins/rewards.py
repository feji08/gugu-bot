from nonebot import on_command
from nonebot.adapters.qq import Bot, Event
from nonebot import on_regex
from nonebot.params import RegexMatched
from ..database import Session, User, EarlyBirdRecord, RewardRecord

# 使用正则匹配 "给xxx上xx个奖励"
rewards = on_regex(r"/?给(?P<recipient>.+?)上(?P<amount>.+?)个奖励", priority=5, block=True)
@rewards.handle()
async def handle_first_receive(bot: Bot, event: Event):
    # 打印事件的原始消息
    print(f"Event message: {event.get_message()}")
    # 手动解析正则
    import re
    match = re.match(r"/?给(?P<recipient>.+?)上(?P<amount>.+?)个奖励", str(event.get_message()))
    if match:
        recipient = match.group("recipient")
        amount = match.group("amount")
        session = Session()
        try:
            # 查询用户 ID
            user = session.query(User).filter_by(nickname=recipient).first()
            if not user:
                await rewards.send(f"没有叫{recipient}的咕咕哦（捂眼睛）~")
                return
            # 给用户加x张奖励
            reward = session.query(RewardRecord).filter_by(user_id=user.user_id).first()
            if not reward:
                reward = RewardRecord(user_id=user.user_id, count=int(amount))
                session.add(reward)
            else:
                reward.count += int(amount)
            await rewards.send(f"添加成功！恭喜{recipient}获得{amount}次奖励！")
            session.commit()
        except Exception as e:
            await rewards.send(f"添加失败。")
        finally:
            session.close()
    else:
        await rewards.send("没有这个咕咕哦（捂眼睛）~")