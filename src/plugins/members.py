from nonebot import on_command
from nonebot.adapters.qq import Bot, Event  # 使用 nonebot.adapters.qq 适配器
from ..database import Session, User, CheckInRecord, EarlyBirdRecord, LeaveRecord, RewardRecord
from sqlalchemy.exc import IntegrityError
from nonebot.adapters.onebot.v11 import Message
from nonebot.params import CommandArg

# add new member
new_member = on_command("新咕报到")
@new_member.handle()
async def handle_first_receive(bot: Bot, event: Event):
    session = Session()

    user_id = event.get_user_id()
    existing_user = session.query(User).filter(User.user_id == user_id).first()
    if existing_user:
        await new_member.send("不要调皮，你已经不是新咕啦~~~~~")
    else:
        await new_member.send(f"欢迎新咕！请再次@本咕并输入你选择的昵称，示例：【@无情的打卡咕-测试中 帽帽】。")
    session.close()

@new_member.receive()
async def handle_new_member(bot: Bot, event: Event):
    session = Session()

    user_id = event.get_user_id()
    user_input = event.get_plaintext().strip()
    if not user_input:
        await new_member.reject("无效的字符，请重新输入。")
    elif session.query(User).filter(User.nickname == user_input).first():
        await new_member.reject("昵称被占用，请重新输入。")
    else:
        new_user = User(user_id=user_id, nickname=user_input)
        session.add(new_user)
        await new_member.send("报到成功！你可以正常使用打卡功能啦！")
    session.commit()
    session.close()

# remove member
remove_member = on_command("踢人", aliases={"remove_user", "delete_user"})

@remove_member.handle()
async def handle_remove_member(bot: Bot, event: Event):
    # 提示用户输入要踢出的昵称
    await remove_member.send("请输入要踢出的用户昵称。")

@remove_member.receive()
async def receive_remove_member(bot: Bot, event: Event):
    session = Session()

    # 获取用户输入的昵称
    user_input = event.get_plaintext().strip()

    # 查找该昵称的用户
    user_to_remove = session.query(User).filter(User.nickname == user_input).first()

    if not user_to_remove:
        await remove_member.finish("未找到指定昵称的用户，请确认昵称输入正确。")
        session.close()
        return

    try:
        # 先删除与用户相关的所有外键记录
        session.query(CheckInRecord).filter(CheckInRecord.user_id == user_to_remove.user_id).delete()
        session.query(EarlyBirdRecord).filter(EarlyBirdRecord.user_id == user_to_remove.user_id).delete()
        session.query(LeaveRecord).filter(LeaveRecord.user_id == user_to_remove.user_id).delete()
        session.query(RewardRecord).filter(RewardRecord.user_id == user_to_remove.user_id).delete()
        # 删除用户记录
        session.query(User).filter(User.user_id == user_to_remove.user_id).delete()

        # 提交事务
        session.commit()
        await remove_member.send(f"成功删除用户：{user_input}")
    except IntegrityError as e:
        # 如果删除失败，回滚事务
        session.rollback()
        await bot.send(event, f"删除用户失败: {str(e)}")
    finally:
        # 关闭 session
        session.close()