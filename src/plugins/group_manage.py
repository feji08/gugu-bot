import pandas as pd
from nonebot import on_command
from nonebot.adapters.qq import Bot, Event
from nonebot.adapters.qq.message import MessageSegment
from nonebot.exception import ActionFailed
from ..database import Session, User, Assignment, CheckInRecord, EarlyBirdRecord, LeaveRecord, RewardRecord
from datetime import datetime, timedelta
from ..myGlobals import *
import matplotlib.pyplot as plt
from pathlib import Path
# 设置 Matplotlib 字体，确保支持中文
plt.rcParams["font.family"] = ["SimHei"]  # Windows 用户

# 创建管理命令
send_summary = on_command("周总结（全体）", aliases={"send_summary"})

def get_custom_leave_period_start():
    # 返回自定义请假周期的起始日期
    return leave_start_date

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
    dates = get_week_dates(get_current_time())
    session = Session()
    # 获取所有用户的 user_id
    user_ids = session.query(User.user_id).distinct().all()
    user_ids = [user_id[0] for user_id in user_ids]
    # 初始化辅助矩阵
    early_bird_matrix = [[False] * len(dates) for _ in range(len(user_ids))]  # 辅助矩阵
    earliest_checkin_times = [None] * len(dates)  # 每天的最早打卡时间
    earliest_checkin_users = [None] * len(dates)  # 每天最早打卡的用户索引

    if not user_ids:
        await send_summary.send("没有找到用户数据。")
        session.close()
        return

    # 准备存储总结数据
    summary_data = []
    group_id = event.group_id if hasattr(event, 'group_id') else None

    yesterday_record = {}
    today = get_current_time().date()
    yesterday = today - timedelta(days=1)
    for user_idx, user_id in enumerate(user_ids):
        # 获取用户昵称
        nickname = session.query(User).filter_by(user_id=user_id).first().nickname

        # 每个用户的记录字典
        user_record = {"姓名": nickname}

        for date_idx, date in enumerate(dates):
            # 查询这一天的打卡记录
            start_time, end_time = get_time_window(date.date())
            checkin_record = session.query(CheckInRecord).filter(
                CheckInRecord.user_id == user_id,
                CheckInRecord.checkin_time >= start_time,
                CheckInRecord.checkin_time < end_time
            ).first()

            date_assignment = ''
            if checkin_record:
                assignment_name = session.query(Assignment).filter_by(id=checkin_record.assignment_id).first().name
                if "练笔" in assignment_name:
                    # print(assignment_name)
                    date_assignment = "√输出练笔"
                elif "摘抄" in assignment_name:
                    # print(assignment_name)
                    date_assignment = "√摘抄作业"
                elif "节奏" in assignment_name:
                    # print(assignment_name)
                    date_assignment = "√节奏练习"
                elif "请假" in assignment_name:
                    # print(assignment_name)
                    date_assignment = "×请假"
                else:
                    # print(assignment_name)
                    date_assignment = "√其他"

                # 记录打卡时间
                checkin_time = checkin_record.checkin_time
                if checkin_record.assignment_id != 100:  # 排除请假记录
                    if earliest_checkin_times[date_idx] is None or checkin_time < earliest_checkin_times[date_idx]:
                        earliest_checkin_times[date_idx] = checkin_time
                        earliest_checkin_users[date_idx] = user_idx

            # print(date_only)
            # print(today)
            # means it's yesterday's record, newest
            if end_time.date() == today:
                yesterday_record[nickname] = date_assignment
            user_record[date.strftime("%Y-%m-%d")] = date_assignment

        leave_period_start = get_custom_leave_period_start()
        # 查询用户的请假次数和早鸟卡数量
        leave_record = session.query(LeaveRecord).filter_by(user_id=user_id, leave_period_start=leave_period_start).first()
        leave_count = leave_record.leave_count if leave_record else 0

        early_bird_record = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
        early_bird_count = early_bird_record.count if early_bird_record else 0

        reward_record = session.query(RewardRecord).filter_by(user_id=user_id).first()
        reward_count = reward_record.count if reward_record else 0

        user_record["周期请假"] = leave_count
        user_record["早鸟卡"] = early_bird_count
        user_record["奖励"] = reward_count

        summary_data.append(user_record)

        # 标记每天最早打卡的用户
    for date_idx, user_idx in enumerate(earliest_checkin_users):
        if user_idx is not None:
            early_bird_matrix[user_idx][date_idx] = True

    # 定义高亮函数
    def highlight_early_bird(df,early_bird_matrix):
        # 第一列和后面两列无色
        colors = [["#FBFFE4" for _ in range(df.shape[1])] for _ in range(df.shape[0])]  # 默认背景色为绿色
        for row in colors:
            row[0] = "#FFFFFF"  # 第一列背景为白色
            row[-1] = "#FFFFFF"  # 最后一列背景为白色
            row[-2] = "#FFFFFF"  # 倒数第二列背景为白色
            row[-3] = "#FFFFFF"  # 倒数第三列背景为白色
        # 遍历 early_bird_matrix，标记早鸟
        for user_idx in range(len(early_bird_matrix)):
            for date_idx in range(len(early_bird_matrix[user_idx])):
                if early_bird_matrix[user_idx][date_idx]:  # 如果是早鸟
                    colors[user_idx][date_idx + 1] = "#B3D8A8"  # 设置背景色为浅绿色
                if df.iloc[user_idx][date_idx + 1] == "×请假":
                    colors[user_idx][date_idx + 1] = "#ffe5d9"  # 设置背景色为浅黄色

        return colors

    # 创建 DataFrame
    df = pd.DataFrame(summary_data)
    df.to_csv(f'week_summary_{today}.csv', index=False)

    colors = highlight_early_bird(df, early_bird_matrix)

    fig, ax = plt.subplots(figsize=(2+0.5*len(dates), 0.5+0.5*len(user_ids)))
    ax.axis('off')  # 隐藏坐标轴

    table = ax.table(
        cellText=df.values.tolist(),
        colLabels=df.columns.tolist(),
        loc='center',
        cellLoc='center',
        cellColours=colors  # 设置单元格背景色
    )

    # 设置表格样式
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.5, 1.5)

    # **保存为图片**
    save_path = Path(f"打卡表格_{today}.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight", pad_inches=0.1)  # 高分辨率保存
    plt.show()

    print(f"图片已保存到: {save_path}")
    await send_summary.send("周总结（全体）已生成，图片正在赶来的路上，请耐心等候~")

    file_message = MessageSegment.file_image(save_path)
    # 发送消息
    await send_summary.send(file_message)
    #
    #
    # from wcwidth import wcswidth
    # # 格式化字典内容
    # print(yesterday_record)
    # message_lines = [f"{yesterday.strftime('%Y-%m-%d')}打卡统计："]
    # max_key_width = max(wcswidth(key) for key in yesterday_record.keys())
    #
    # for key, value in yesterday_record.items():
    #     # 计算每个键的实际填充宽度
    #     current_width = wcswidth(key)
    #     full_spaces_needed = max_key_width - current_width
    #
    #     # 尝试使用半角和全角空格混合填充
    #     half_spaces_needed = full_spaces_needed % 2
    #     full_spaces_needed = full_spaces_needed // 2
    #
    #     # 构建填充字符串
    #     padding = '\u3000' * full_spaces_needed + ' ' * half_spaces_needed
    #     message_lines.append(f"{key}{padding} : {value}")
    #
    # # 将格式化后的消息组合成一个字符串
    # formatted_message = "\n".join(message_lines)
    #
    # # 发送今日打卡记录
    # await send_summary.send(formatted_message)
    # # await send_summary.send('本周总结已生成，请联系 @煤油礼帽 获取。')

    # 清理会话
    session.close()
