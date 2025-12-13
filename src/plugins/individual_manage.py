from nonebot import on_command
from nonebot.adapters.qq import Bot, Event
from ..database import Session, Assignment, CheckInRecord, EarlyBirdRecord, LeaveRecord, RewardRecord
from datetime import datetime, timedelta
from ..myGlobals import *

# 创建周总结命令
week_summary = on_command("个人总结", aliases={"week_summary"})

def get_custom_leave_period_start():
    # 返回自定义请假周期的起始日期
    return leave_start_date

def get_custom_leave_period_end():
    # 返回自定义请假周期的结束日期
    return leave_end_date

@week_summary.handle()
async def handle_week_summary(bot: Bot, event: Event):
    session = Session()

    # 获取用户的 user_id
    user_id = event.get_user_id()

    # 获取当前周的起始和结束时间
    start_of_week, end_of_week = get_week_range(get_current_time())

    # 查询请假次数
    leave_period_start = get_custom_leave_period_start()
    # 获取在自定义请假周期内的请假记录
    leave_record = session.query(LeaveRecord).filter(
        LeaveRecord.user_id == user_id,
        LeaveRecord.leave_period_start == leave_period_start
    ).first()
    leave_count = leave_record.leave_count if leave_record else 0

    # 查询早鸟卡数量
    early_bird_record = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
    early_bird_count = early_bird_record.count if early_bird_record else 0

    # 查询奖励次数
    reward = session.query(RewardRecord).filter_by(user_id=user_id).first()
    reward_count = reward.count if reward else 0

    # 查询当前周内的所有打卡记录
    records = session.query(CheckInRecord).filter(
        CheckInRecord.user_id == user_id,
        CheckInRecord.checkin_time >= start_of_week,
        CheckInRecord.checkin_time < end_of_week
    ).all()

    assignment_counts = {}
    if records:
        # 统计每类作业的打卡次数
        for record in records:
            assignment_name = session.query(Assignment).filter_by(id=record.assignment_id).first().name
            if assignment_name in assignment_counts:
                assignment_counts[assignment_name] += 1
            else:
                assignment_counts[assignment_name] = 1

    # 构建总结信息
    summary_message = "本周的打卡情况如下：\n" if records else "本周还没有任何打卡记录"
    if records:
        for assignment, count in assignment_counts.items():
            summary_message += f"{assignment}: {count} 次\n"

    summary_message += f"\n本周期请假次数：{leave_count}/{leave_limit}次\n"
    summary_message += f"当前早鸟卡：{early_bird_count} 张\n"
    summary_message += f"当前奖励：{reward_count} 次\n"

    # 发送总结信息
    await week_summary.send(summary_message)
    session.close()