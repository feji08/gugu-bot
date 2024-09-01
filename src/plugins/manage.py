import pandas as pd
from nonebot import on_command
from nonebot.adapters.qq import Bot, Event
from nonebot.adapters.qq.message import MessageSegment
from nonebot.exception import ActionFailed
from ..database import Session, User, Assignment, CheckInRecord, EarlyBirdRecord, LeaveRecord
from datetime import datetime, timedelta
from ..myGlobals import *

# 创建管理命令
send_summary = on_command("发送总结", aliases={"send_summary"})

def get_checkin_day():
    now = datetime.now()
    today_Nam = now.replace(hour=time_delay+2, minute=0, second=0, microsecond=0)

    if now >= today_Nam:
        # 当前时间在18点后，算作后一天
        checkin_day = now + timedelta(days=1)
    else:
        # 当前时间在18点前，算作当天
        checkin_day = now

    return checkin_day.date()
def get_custom_leave_period_start():
    # 返回自定义请假周期的起始日期
    return leave_start_date
def get_week_dates():
    now = datetime.now()
    # 计算出本周的起始日期（周日）
    start_of_week = now - timedelta(days=now.weekday()+1) - timedelta(weeks=1)
    dates = [start_of_week + timedelta(days=i) for i in range(14)]
    return dates

async def get_nickname(bot: Bot, user_id: str, group_id: str = None):
    try:
        if group_id:
            # 如果在群聊中，尝试使用 get_group_member_info 获取昵称
            info = await bot.call_api("get_group_member_info", group_id=group_id, user_id=user_id)
            return info["nickname"]
        else:
            # 如果不是在群聊中，使用 get_stranger_info 获取昵称
            info = await bot.call_api("get_stranger_info", user_id=user_id)
            return info["nickname"]
    except:
        return "Unknown"  # 如果无法获取，返回默认昵称

@send_summary.handle()
async def handle_send_summary(bot: Bot, event: Event):
    # 获取当前周的所有日期
    dates = get_week_dates()
    session = Session()
    # 获取所有用户的 user_id
    user_ids = session.query(User.user_id).distinct().all()
    user_ids = [user_id[0] for user_id in user_ids]

    if not user_ids:
        await send_summary.send("没有找到用户数据。")
        session.close()
        return

    # 准备存储总结数据
    summary_data = []
    group_id = event.group_id if hasattr(event, 'group_id') else None

    today_record = {}
    today = get_checkin_day() - timedelta(days=1)
    for user_id in user_ids:
        # 获取用户昵称
        nickname = id_nickname[user_id]

        # 每个用户的记录字典
        user_record = {"姓名": nickname}

        for date in dates:
            # 查询这一天的打卡记录
            start_time = datetime.combine(date, datetime.min.time()) + timedelta(hours=time_delay)
            end_time = start_time + timedelta(days=1)
            checkin_record = session.query(CheckInRecord).filter(
                CheckInRecord.user_id == user_id,
                CheckInRecord.checkin_time >= start_time,
                CheckInRecord.checkin_time < end_time
            ).first()
            date = date + timedelta(days=1)
            date_only = date.date()

            date_record = ''
            if checkin_record:
                assignment_name = session.query(Assignment).filter_by(id=checkin_record.assignment_id).first().name
                if "练笔" in assignment_name:
                    # print(assignment_name)
                    date_record = "√输出练笔"
                elif "请假" in assignment_name:
                    # print(assignment_name)
                    date_record = "×请假"
                else:
                    # print(assignment_name)
                    date_record = "√其他"

            # print(date_only)
            # print(today)
            if date_only == today:
                today_record[nickname] = date_record
            user_record[date.strftime("%Y-%m-%d")] = date_record

        leave_period_start = get_custom_leave_period_start()
        # 查询用户的请假次数和早鸟卡数量
        leave_record = session.query(LeaveRecord).filter_by(user_id=user_id, leave_period_start=leave_period_start).first()
        leave_count = leave_record.leave_count if leave_record else 0

        early_bird_record = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
        early_bird_count = early_bird_record.count if early_bird_record else 0

        user_record["请假次数"] = leave_count
        user_record["早鸟卡"] = early_bird_count

        summary_data.append(user_record)

    # 创建 DataFrame
    df = pd.DataFrame(summary_data)
    df.to_csv('week_summary.csv', index=False)

    from wcwidth import wcswidth
    # 格式化字典内容
    message_lines = [f"{today.strftime('%Y-%m-%d')}打卡统计："]
    max_key_width = max(wcswidth(key) for key in today_record.keys())

    for key, value in today_record.items():
        # 计算每个键的实际填充宽度
        current_width = wcswidth(key)
        full_spaces_needed = max_key_width - current_width

        # 尝试使用半角和全角空格混合填充
        half_spaces_needed = full_spaces_needed % 2
        full_spaces_needed = full_spaces_needed // 2

        # 构建填充字符串
        padding = '\u3000' * full_spaces_needed + ' ' * half_spaces_needed
        message_lines.append(f"{key}{padding} : {value}")

    # 将格式化后的消息组合成一个字符串
    formatted_message = "\n".join(message_lines)

    # 发送今日打卡记录
    await send_summary.send(formatted_message)
    await send_summary.send('本周总结已生成，请联系 @煤油礼帽 获取。')

    # 清理会话
    session.close()
