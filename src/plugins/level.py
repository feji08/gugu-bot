from nonebot import on_command
from nonebot.adapters.qq import Bot, Event  # 使用 nonebot.adapters.qq 适配器
from ..database import Session, User

# 群组等级映射字典
GROUP_LEVEL_MAPPING = {
    0: "新人",
    1: "进阶",
    2: "高阶"
}

# 创建一个命令处理器来获取群组等级并询问是否要更新
get_group = on_command("群组")

@get_group.handle()
async def handle_get_group(bot: Bot, event: Event):
    # 获取用户的 user_id
    user_id = event.get_user_id()

    # 创建数据库会话
    session = Session()

    try:
        # 查询用户是否存在
        user = session.query(User).filter_by(user_id=user_id).first()
        if user is None:
            # 如果用户不存在，插入新记录，设定 level 为 0
            new_user = User(user_id=user_id, group_level=0)
            session.add(new_user)
            session.commit()
            group_level = 0  # 新插入的用户群组等级为 0
        else:
            # 如果用户已存在，获取其群组等级
            group_level = user.group_level

        # 获取群组名称
        group_name = GROUP_LEVEL_MAPPING.get(group_level, "未知等级")

        # 发送用户 ID 和群组等级，并给出选项
        options = "\n".join([f"{k}. {v}" for k, v in GROUP_LEVEL_MAPPING.items()])
        await get_group.send(
            f"你的当前群组等级是：{group_level}（{group_name}）\n"
            f"你可以选择更换到以下等级：\n{options}\n"
            f"请输入对应的数字进行选择，或者输入'退出'来保持不变。"
        )

    finally:
        # 关闭数据库会话
        session.close()

@get_group.receive()
async def handle_group_selection(bot: Bot, event: Event):
    user_input = event.get_plaintext().strip()

    if user_input == "退出":
        await get_group.send("好的，你的群组等级保持不变。")
        return

    level_map = {"0": 0, "1": 1, "2": 2}

    if user_input not in level_map:
        # 用户输入的不是有效的选项，重新提示
        await get_group.reject("无效的选项，请输入 0、1 或 2 以选择群组等级，或者输入'退出'来保持不变。")

    new_level = level_map[user_input]

    # 获取用户的 user_id
    user_id = event.get_user_id()

    # 创建数据库会话
    session = Session()

    try:
        # 查询用户是否存在
        user = session.query(User).filter_by(user_id=user_id).first()

        if user is None:
            # 如果用户不存在，插入新记录
            new_user = User(user_id=user_id, group_level=new_level)
            session.add(new_user)
        else:
            # 如果用户已存在，更新其群组等级
            user.group_level = new_level

        session.commit()

        # 获取群组名称
        group_name = GROUP_LEVEL_MAPPING[new_level]

        # 发送确认消息
        await get_group.send(f"你的群组等级已更新为：{new_level}（{group_name}）")

    finally:
        # 关闭数据库会话
        session.close()
