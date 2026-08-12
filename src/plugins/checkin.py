from datetime import datetime
from sqlalchemy import func
from nonebot import on_command, on_type, logger
from nonebot.adapters.qq import Bot, Event, MessageSegment
from nonebot.adapters.qq.event import InteractionCreateEvent
from nonebot.adapters.qq.models import (
    MessageKeyboard, InlineKeyboard, InlineKeyboardRow, Button, RenderData, Action, Permission,
)
from ..database import Session, Assignment, CheckInRecord, EarlyBirdRecord, LeaveRecord, RewardRecord
from ..myGlobals import get_current_time, get_time_window
from ..config import config

# 创建打卡命令
check_in = on_command("打卡", aliases={"checkin"})

def get_custom_leave_period_start():
    # 返回自定义请假周期的起始日期
    return config.cycle_start

def get_custom_leave_period_end():
    # 返回自定义请假周期的结束日期
    return config.cycle_end

@check_in.handle()
async def handle_first_receive(bot: Bot, event: Event):
    session = Session()
    # 获取所有作业类型
    assignments = session.query(Assignment).all()
    if not assignments:
        await check_in.send("目前没有可用的作业类型。")
        session.close()
        return
    user_id = event.get_user_id()
    checkin_time = get_current_time()
    checkin_time_start, checkin_time_end = get_time_window(checkin_time.date())
    # 检查用户是否已经在这个时间段内打过卡
    existing_record = session.query(CheckInRecord).filter(
        CheckInRecord.user_id == user_id,
        CheckInRecord.checkin_time >= checkin_time_start,
        CheckInRecord.checkin_time < checkin_time_end
    ).first()

    if existing_record:
        await check_in.send("你今天已经打过卡了。")
    else:
        show = [a for a in assignments if a.id != 100]
        # 权限锁触发人:把该用户所有 openid 口径全塞进 specify_user_ids，QQ 用哪个校验都能 match；
        # 别人的 id 都不在名单里，锁照样成立
        _a = getattr(event, "author", None)
        _ids = [getattr(_a, k, None) for k in ("member_openid", "union_openid", "id", "user_openid")]
        _ids.append(event.get_user_id())
        _ids = [x for x in dict.fromkeys(_ids) if x]
        perm = Permission(type=0, specify_user_ids=_ids)
        buttons = [Button(id=str(a.id), render_data=RenderData(label=a.name),
                          action=Action(type=1, permission=perm, data=f"checkin:{a.id}"))
                   for a in show]
        buttons.append(Button(id="cancel", render_data=RenderData(label="取消"),
                              action=Action(type=1, permission=perm, data="checkin:cancel")))
        # 一行一个（群里不挤）
        rows = [InlineKeyboardRow(buttons=[b]) for b in buttons]
        kb = MessageKeyboard(content=InlineKeyboard(rows=rows))
        # keyboard 必须挂 markdown 消息(纯文本会被拒 40034011)
        md = MessageSegment.markdown("请选择你要打卡的作业类型，点击对应的按钮：")
        await check_in.send(md + MessageSegment.keyboard(kb))
    session.close()


async def _reply_group(bot, group_openid, msg):
    # 群主动消息(需群主开"机器人主动在群聊内发言")；interaction 不能被动回消息，故改主动发。失败不影响打卡已记录
    try:
        await bot.send_to_group(group_openid=group_openid, message=msg)
    except Exception as e:
        logger.warning(f"[checkin] 群回复失败(可能未开机器人主动发言): {e}")


# 打卡按钮回调:点作业类型 → 记录；点取消 → 取消
checkin_cb = on_type(InteractionCreateEvent, priority=5, block=True)

@checkin_cb.handle()
async def handle_checkin_button(bot: Bot, event: InteractionCreateEvent):
    data = event.data.resolved.button_data or ""
    if not data.startswith("checkin:"):
        return  # 非打卡按钮，放行
    iid = event.id
    user_id = event.get_user_id()          # 群场景=group_member_openid，与打卡记录一致
    group_openid = event.group_openid
    choice = data.split(":", 1)[1]

    if choice == "cancel":
        await bot.put_interaction(interaction_id=iid, code=0)
        await _reply_group(bot, group_openid, "已取消打卡。")
        return

    assignment_id = int(choice)
    session = Session()
    try:
        checkin_time = get_current_time()
        checkin_time_start, checkin_time_end = get_time_window(checkin_time.date())
        existing_record = session.query(CheckInRecord).filter(
            CheckInRecord.user_id == user_id,
            CheckInRecord.checkin_time >= checkin_time_start,
            CheckInRecord.checkin_time < checkin_time_end
        ).first()
        if existing_record:
            await bot.put_interaction(interaction_id=iid, code=3)  # 3=重复操作(已打卡)
            return
        assignment = session.query(Assignment).filter_by(id=assignment_id).first()
        if not assignment:
            await bot.put_interaction(interaction_id=iid, code=1)  # 1=操作失败
            return

        # 插入新的打卡记录
        new_record = CheckInRecord(user_id=user_id, assignment_id=assignment.id, checkin_time=checkin_time)
        session.add(new_record)
        session.commit()

        # 检查是否是当天第一个打卡的用户
        record_count = session.query(CheckInRecord).filter(
            CheckInRecord.checkin_time == checkin_time,
            CheckInRecord.assignment_id != 100  ## not leave
        ).count()
        record = session.query(CheckInRecord).filter(
            func.date(CheckInRecord.checkin_time) == checkin_time.date(),
            CheckInRecord.assignment_id != 100  # 排除特殊记录
        ).first()

        # 公休奖励
        checkin_time_naive = checkin_time.replace(tzinfo=None)
        if not "摘抄" in assignment.name and datetime.combine(config.holiday_start, datetime.min.time()) < checkin_time_naive <= datetime.combine(config.holiday_end, datetime.max.time()):
            early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
            if not early_bird:
                early_bird = EarlyBirdRecord(user_id=user_id, count=1)
                session.add(early_bird)
            else:
                early_bird.count += 1
            msg = f"打卡成功！你在 {checkin_time.date()} 打卡了作业：{assignment.name}。公休日打卡获得一张早鸟卡！"
        elif record_count == 1 and record.user_id == user_id:
            early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
            if not early_bird:
                early_bird = EarlyBirdRecord(user_id=user_id, count=1)
                session.add(early_bird)
            else:
                early_bird.count += 1
            msg = f"打卡成功！你在 {checkin_time.date()} 打卡了作业：{assignment.name}。你是今天第一个打卡的，获得了一张早鸟卡！"
        else:
            msg = f"打卡成功！你在 {checkin_time.date()} 打卡了作业：{assignment.name}"
        session.commit()

        # 先 ack(免按钮转圈)，再主动发打卡成功(interaction 不能被动回消息)
        await bot.put_interaction(interaction_id=iid, code=0)
        await _reply_group(bot, group_openid, msg)
    finally:
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

    if (leave_record and leave_record.leave_count >= config.leave_limit) or config.leave_limit == 0:
        # 本周请假次数达到上限，检查是否有足够的早鸟卡兑换
        early_bird = session.query(EarlyBirdRecord).filter_by(user_id=user_id).first()
        # 没有早鸟卡
        if not early_bird or early_bird.count < 2:
            reward = session.query(RewardRecord).filter_by(user_id=user_id).first()
            if not reward or reward.count < 1:
                await leave.send(f"你本周期已请假{config.leave_limit}次，无法再请假。")
            else:
                await leave.send(f"你本周期已请假{config.leave_limit}次，剩余早鸟卡不足，但有奖励次数。发送指令“/奖励请假”，使用1次奖励兑换一次请假。")
        else:
            await leave.send(f"你本周期已请假{config.leave_limit}次，剩余早鸟卡充足。发送指令“/兑换请假”，使用2张早鸟卡兑换一次请假。")
    else:
        # 正常请假
        # 首先记录请假时间（特殊checkin）
        checkin_time = get_current_time()
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
        await leave.send(f"请假成功！你本周期已经请假 {leave_record.leave_count} 次，剩余{config.leave_limit-leave_record.leave_count}次。")

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
        checkin_time= get_current_time()
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

redeem_reward = on_command("奖励请假", aliases={"reward_leave"})
@redeem_reward.handle()
async def handle_redeem_reward(bot: Bot, event: Event):
    session = Session()
    user_id = event.get_user_id()
    reward = session.query(RewardRecord).filter_by(user_id=user_id).first()
    leave_period_start = get_custom_leave_period_start()

    if not reward or reward.count < 1:
        await redeem_early_bird.send("你没有足够的奖励兑换请假。")
    else:
        # 打卡记录
        checkin_time= get_current_time()
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

        reward.count -= 1
        session.commit()
        await redeem_early_bird.send(f"兑换成功！你本周期已经请假 {leave_record.leave_count} 次。")

    session.close()
