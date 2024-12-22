from sqlalchemy import func
from nonebot import on_command
from nonebot.adapters.qq import Bot, Event
from ..database import Session, Assignment, CheckInRecord, EarlyBirdRecord, LeaveRecord
from ..myGlobals import *

# 创建打卡命令
check_in = on_command("打卡", aliases={"checkin"})

def get_custom_leave_period_start():
    # 返回自定义请假周期的起始日期
    return leave_start_date

def get_custom_leave_period_end():
    # 返回自定义请假周期的结束日期
    return leave_end_date

@check_in.handle()
async def handle_first_receive(bot: Bot, event: Event):
    session = Session()
    # 获取所有作业类型
    assignments = session.query(Assignment).all()
    if not assignments:
        await check_in.send("目前没有可用的作业类型。")
        session.close()
        return
        # 获取用户的 user_id
    user_id = event.get_user_id()
    print(user_id)
    checkin_time = get_current_day(time_zone)
    print(checkin_time)
    # 计算打卡时间的开始和结束
    checkin_time_start,checkin_time_end = get_time_window(checkin_time.date())
    print(checkin_time_start, checkin_time_end)
    # 检查用户是否已经在这个时间段内打过卡
    existing_record = session.query(CheckInRecord).filter(
        CheckInRecord.user_id == user_id,
        CheckInRecord.checkin_time >= checkin_time_start,
        CheckInRecord.checkin_time < checkin_time_end
    ).first()

    if existing_record:
        await check_in.send("你今天已经打过卡了。")
    else:
        # 显示作业类型选项
        assignment_options = "\n".join([f"{i+1}. {a.name}" for i, a in enumerate(assignments) if a.id != 100])
        await check_in.send(f"请选择你要打卡的作业类型，输入对应的数字：\n{assignment_options}")
    session.close()
@check_in.receive()
async def handle_check_in(bot: Bot, event: Event):
    session = Session()
    # 获取用户输入的编号
    user_input = event.get_plaintext().strip()
    if not user_input.isdigit():
        await check_in.reject("无效的输入，请输入数字。")
    assignment_index = int(user_input) - 1
    # 重新查询所有作业类型
    assignments = session.query(Assignment).all()
    if assignment_index < 0 or assignment_index >= len(assignments):
        await check_in.reject("无效的选项，请输入正确的编号。")
    assignment = assignments[assignment_index]
    # 获取用户的 user_id
    user_id = event.get_user_id()
    print(user_id)
    checkin_time = get_current_day(time_zone)
    print(checkin_time)
    # 计算打卡时间的开始和结束
    checkin_time_start,checkin_time_end = get_time_window(checkin_time.date())
    print(checkin_time_start, checkin_time_end)
    # 检查用户是否已经在这个时间段内打过卡
    existing_record = session.query(CheckInRecord).filter(
        CheckInRecord.user_id == user_id,
        CheckInRecord.checkin_time >= checkin_time_start,
        CheckInRecord.checkin_time < checkin_time_end
    ).first()

    if existing_record:
        await check_in.send("你今天已经打过卡了。")
    else:
        # 插入新的打卡记录
        new_record = CheckInRecord(user_id=user_id, assignment_id=assignment.id, checkin_time=checkin_time)
        session.add(new_record)
        session.commit()

        # 检查是否是当天第一个打卡的用户
        record_count = session.query(CheckInRecord).filter(
            CheckInRecord.checkin_time == checkin_time,
            CheckInRecord.assignment_id != 100 ## not leave
        ).count()

        # 查询当天唯一记录是否属于指定用户
        record = session.query(CheckInRecord).filter(
            CheckInRecord.checkin_time == checkin_time,
            CheckInRecord.assignment_id != 100  # 排除特殊记录
        ).first()

        print(record)

        if record_count == 1 and record.user_id == user_id:
            # 给用户加一张早鸟卡
            early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
            if not early_bird:
                early_bird = EarlyBirdRecord(user_id=user_id, count=1)
                session.add(early_bird)
            else:
                early_bird.count += 1
            await check_in.send(f"打卡成功！你在 {checkin_time.date()} 打卡了作业：{assignment.name}。你是今天第一个打卡的，获得了一张早鸟卡！")

        else:
            await check_in.send(f"打卡成功！你在 {checkin_time.date()} 打卡了作业：{assignment.name}")
        session.commit()
    session.close()

# 创建请假命令
leave = on_command("请假", aliases={"leave"})

@leave.handle()
async def handle_leave(bot: Bot, event: Event):
    session = Session()

    user_id = event.get_user_id()
    leave_period_start = get_custom_leave_period_start()
    leave_period_end = get_custom_leave_period_end()

    # 获取在自定义请假周期内的请假记录
    leave_record = session.query(LeaveRecord).filter(
        LeaveRecord.user_id == user_id,
        LeaveRecord.leave_period_start == leave_period_start
    ).first()

    if leave_record and leave_record.leave_count >= leave_limit:
        # 本周请假次数达到上限，检查是否有足够的早鸟卡兑换
        early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
        if not early_bird or early_bird.count < 2:
            await leave.send(f"你本周期已经请假{leave_limit}次，无法再请假。")
        else:
            await leave.send(f"你本周期已经请假{leave_limit}次，无法再请假，但是你有足够的早鸟卡。发送指令“/兑换请假”，使用2张早鸟卡兑换一次请假。")
    else:
        # 正常请假
        # 首先记录请假时间（特殊checkin）
        checkin_time = get_current_day(time_zone)
        print(checkin_time)
        # 计算打卡时间的开始和结束
        checkin_time_start,checkin_time_end = get_time_window(checkin_time.date())
        print(checkin_time_start, checkin_time_end)

        # 检查用户是否已经在这个时间段内打过卡
        existing_record = session.query(CheckInRecord).filter(
            CheckInRecord.user_id == user_id,
            CheckInRecord.checkin_time >= checkin_time_start,
            CheckInRecord.checkin_time < checkin_time_end
        ).first()

        if existing_record:
            await check_in.send("你今天已经打过卡了。")
        else:
            # 插入新的打卡记录
            new_record = CheckInRecord(user_id=user_id, assignment_id=100, checkin_time = checkin_time)
            session.add(new_record)
            session.commit()

        if not leave_record:
            leave_record = LeaveRecord(user_id=user_id, leave_period_start=leave_period_start, leave_count=1)
            session.add(leave_record)
        else:
            leave_record.leave_count += 1
        session.commit()
        await leave.send(f"请假成功！你本周期已经请假 {leave_record.leave_count} 次，剩余{leave_limit-leave_record.leave_count}次。")

    session.close()

# 创建兑换早鸟卡命令
redeem_early_bird = on_command("兑换请假", aliases={"redeem_leave"})

@redeem_early_bird.handle()
async def handle_redeem(bot: Bot, event: Event):
    session = Session()

    user_id = event.get_user_id()
    early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()

    leave_period_start = get_custom_leave_period_start()

    if not early_bird or early_bird.count < 2:
        await redeem_early_bird.send("你没有足够的早鸟卡兑换请假。需要2张早鸟卡才能兑换一次请假。")
    else:
        # 打卡记录
        checkin_time= get_current_day(time_zone)
        print(checkin_time)
        # 计算打卡时间的开始和结束
        checkin_time_start,checkin_time_end = get_time_window(checkin_time.date())
        print(checkin_time_start, checkin_time_end)
        # 检查用户是否已经在这个时间段内打过卡
        existing_record = session.query(CheckInRecord).filter(
            CheckInRecord.user_id == user_id,
            CheckInRecord.checkin_time >= checkin_time_start,
            CheckInRecord.checkin_time < checkin_time_end
        ).first()

        if existing_record:
            await check_in.send("你今天已经打过卡了。")
        else:
            # 插入新的打卡记录
            new_record = CheckInRecord(user_id=user_id, assignment_id=100, checkin_time = checkin_time)
            session.add(new_record)
            session.commit()
        # 请假记录
        leave_record = session.query(LeaveRecord).filter_by(user_id=user_id, leave_period_start=leave_period_start).first()
        if not leave_record:
            leave_record = LeaveRecord(user_id=user_id, leave_period_start=leave_period_start, leave_count=1)
            session.add(leave_record)
        else:
            leave_record.leave_count += 1

        early_bird.count -= 2
        session.commit()
        await redeem_early_bird.send(f"兑换成功！你本周期已经请假 {leave_record.leave_count} 次。")

    session.close()