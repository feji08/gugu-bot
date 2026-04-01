from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from ...database import (
    Session, User, Assignment, CheckInRecord,
    EarlyBirdRecord, LeaveRecord, RewardRecord,
)
from ...config import config
from .report_gen import generate_report_xlsx

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ---------- 首页 ----------

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse("/admin/users", status_code=303)


# ---------- 用户管理 ----------

@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, msg: str = ""):
    session = Session()
    users = session.query(User).all()
    session.close()
    return templates.TemplateResponse("users.html", {"request": request, "users": users, "msg": msg})


@router.post("/users/{user_id}/edit")
async def users_edit(user_id: int, nickname: str = Form(...), cute_name: str = Form(""), group_level: int = Form(0)):
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.nickname = nickname
        user.cute_name = cute_name or None
        user.group_level = group_level
        session.commit()
    session.close()
    return RedirectResponse("/admin/users?msg=已保存", status_code=303)


@router.get("/users/{user_id}/delete")
async def users_delete(user_id: int):
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        session.query(CheckInRecord).filter_by(user_id=user.user_id).delete()
        session.query(EarlyBirdRecord).filter_by(user_id=user.user_id).delete()
        session.query(LeaveRecord).filter_by(user_id=user.user_id).delete()
        session.query(RewardRecord).filter_by(user_id=user.user_id).delete()
        session.delete(user)
        session.commit()
    session.close()
    return RedirectResponse("/admin/users?msg=已删除", status_code=303)


# ---------- 打卡记录 ----------

@router.get("/checkins", response_class=HTMLResponse)
async def checkins_list(request: Request, msg: str = "", sort: str = "time_desc", date: str = ""):
    session = Session()
    # 获取所有有记录的日期（降序）供下拉筛选
    from sqlalchemy import func
    date_col = func.date(CheckInRecord.checkin_time)
    date_rows = (
        session.query(date_col)
        .distinct()
        .order_by(date_col.desc())
        .limit(60)
        .all()
    )
    available_dates = [str(r[0]) for r in date_rows]

    query = (
        session.query(CheckInRecord, User.nickname, Assignment.name)
        .outerjoin(User, CheckInRecord.user_id == User.user_id)
        .outerjoin(Assignment, CheckInRecord.assignment_id == Assignment.id)
    )
    if date:
        day_start = datetime.strptime(date, "%Y-%m-%d")
        day_end = day_start.replace(hour=23, minute=59, second=59)
        query = query.filter(CheckInRecord.checkin_time.between(day_start, day_end))
    if sort == "time_asc":
        query = query.order_by(CheckInRecord.checkin_time.asc())
    elif sort == "name_asc":
        query = query.order_by(User.nickname.asc(), CheckInRecord.checkin_time.desc())
    elif sort == "name_desc":
        query = query.order_by(User.nickname.desc(), CheckInRecord.checkin_time.desc())
    else:
        query = query.order_by(CheckInRecord.checkin_time.desc())
    raw = query.limit(200).all()
    records = [
        {
            "id": r.CheckInRecord.id,
            "nickname": r.nickname or r.CheckInRecord.user_id,
            "assignment_name": r.name or "未知",
            "checkin_time": r.CheckInRecord.checkin_time.strftime("%Y-%m-%d %H:%M"),
        }
        for r in raw
    ]
    users = session.query(User).order_by(User.nickname).all()
    assignments = session.query(Assignment).all()
    today = datetime.now().strftime("%Y-%m-%d")
    session.close()
    return templates.TemplateResponse("checkins.html", {
        "request": request, "records": records, "msg": msg, "sort": sort,
        "date": date, "available_dates": available_dates,
        "users": users, "assignments": assignments, "today": today,
    })


@router.post("/checkins/add")
async def checkins_add(
    user_id: str = Form(...),
    assignment_id: int = Form(...),
    checkin_date: str = Form(...),
    checkin_hour: int = Form(...),
):
    session = Session()
    checkin_time = datetime.strptime(f"{checkin_date} {checkin_hour}:00:00", "%Y-%m-%d %H:%M:%S")
    record = CheckInRecord(user_id=user_id, assignment_id=assignment_id, checkin_time=checkin_time)
    session.add(record)
    session.commit()
    new_id = record.id
    session.close()
    from urllib.parse import urlencode
    undo = f"/admin/checkins/{new_id}/delete"
    return RedirectResponse(f"/admin/checkins?{urlencode({'msg': '已新增', 'undo': undo})}", status_code=303)


@router.get("/checkins/restore")
async def checkins_restore(user_id: str, assignment_id: int, checkin_time: str):
    session = Session()
    ct = datetime.strptime(checkin_time, "%Y-%m-%d %H:%M:%S")
    record = CheckInRecord(user_id=user_id, assignment_id=assignment_id, checkin_time=ct)
    session.add(record)
    session.commit()
    session.close()
    return RedirectResponse("/admin/checkins?msg=已撤销", status_code=303)


@router.get("/checkins/{record_id}/delete")
async def checkins_delete(record_id: int):
    session = Session()
    record = session.query(CheckInRecord).filter_by(id=record_id).first()
    undo_url = ""
    if record:
        from urllib.parse import urlencode
        undo_url = f"/admin/checkins/restore?{urlencode({'user_id': record.user_id, 'assignment_id': record.assignment_id, 'checkin_time': record.checkin_time.strftime('%Y-%m-%d %H:%M:%S')})}"
        session.delete(record)
        session.commit()
    session.close()
    return RedirectResponse(f"/admin/checkins?{urlencode({'msg': '已删除', 'undo': undo_url})}", status_code=303)


# ---------- 请假/早鸟卡/奖励 ----------

@router.get("/leaves", response_class=HTMLResponse)
async def leaves_list(request: Request, msg: str = ""):
    session = Session()

    current_cycle = config.cycle_start
    leave_raw = (
        session.query(LeaveRecord, User.nickname)
        .outerjoin(User, LeaveRecord.user_id == User.user_id)
        .filter(LeaveRecord.leave_period_start == current_cycle)
        .all()
    )
    leave_records = [
        {
            "id": r.LeaveRecord.id,
            "nickname": r.nickname or r.LeaveRecord.user_id,
            "leave_count": r.LeaveRecord.leave_count,
        }
        for r in leave_raw
    ]

    eb_raw = (
        session.query(EarlyBirdRecord, User.nickname)
        .outerjoin(User, EarlyBirdRecord.user_id == User.user_id)
        .all()
    )
    early_bird_records = [
        {"id": r.EarlyBirdRecord.id, "nickname": r.nickname or r.EarlyBirdRecord.user_id, "count": r.EarlyBirdRecord.count}
        for r in eb_raw
    ]

    rw_raw = (
        session.query(RewardRecord, User.nickname)
        .outerjoin(User, RewardRecord.user_id == User.user_id)
        .all()
    )
    reward_records = [
        {"id": r.RewardRecord.id, "nickname": r.nickname or r.RewardRecord.user_id, "count": r.RewardRecord.count}
        for r in rw_raw
    ]

    session.close()
    return templates.TemplateResponse("leaves.html", {
        "request": request,
        "current_cycle": current_cycle.strftime("%Y-%m-%d"),
        "leave_records": leave_records,
        "early_bird_records": early_bird_records,
        "reward_records": reward_records,
        "msg": msg,
    })


@router.post("/leaves/{record_id}/edit")
async def leaves_edit(record_id: int, leave_count: int = Form(...)):
    session = Session()
    record = session.query(LeaveRecord).filter_by(id=record_id).first()
    old_val = record.leave_count if record else 0
    if record:
        record.leave_count = leave_count
        session.commit()
    session.close()
    from urllib.parse import urlencode
    undo = f"/admin/leaves/{record_id}/revert?leave_count={old_val}"
    return RedirectResponse(f"/admin/leaves?{urlencode({'msg': '已保存', 'undo': undo})}", status_code=303)


@router.get("/leaves/{record_id}/revert")
async def leaves_revert(record_id: int, leave_count: int):
    session = Session()
    record = session.query(LeaveRecord).filter_by(id=record_id).first()
    if record:
        record.leave_count = leave_count
        session.commit()
    session.close()
    return RedirectResponse("/admin/leaves?msg=已撤销", status_code=303)


@router.post("/earlybirds/{record_id}/edit")
async def earlybirds_edit(record_id: int, count: int = Form(...)):
    session = Session()
    record = session.query(EarlyBirdRecord).filter_by(id=record_id).first()
    old_val = record.count if record else 0
    if record:
        record.count = count
        session.commit()
    session.close()
    from urllib.parse import urlencode
    undo = f"/admin/earlybirds/{record_id}/revert?count={old_val}"
    return RedirectResponse(f"/admin/leaves?{urlencode({'msg': '已保存', 'undo': undo})}", status_code=303)


@router.get("/earlybirds/{record_id}/revert")
async def earlybirds_revert(record_id: int, count: int):
    session = Session()
    record = session.query(EarlyBirdRecord).filter_by(id=record_id).first()
    if record:
        record.count = count
        session.commit()
    session.close()
    return RedirectResponse("/admin/leaves?msg=已撤销", status_code=303)


@router.post("/rewards/{record_id}/edit")
async def rewards_edit(record_id: int, count: int = Form(...)):
    session = Session()
    record = session.query(RewardRecord).filter_by(id=record_id).first()
    old_val = record.count if record else 0
    if record:
        record.count = count
        session.commit()
    session.close()
    from urllib.parse import urlencode
    undo = f"/admin/rewards/{record_id}/revert?count={old_val}"
    return RedirectResponse(f"/admin/leaves?{urlencode({'msg': '已保存', 'undo': undo})}", status_code=303)


@router.get("/rewards/{record_id}/revert")
async def rewards_revert(record_id: int, count: int):
    session = Session()
    record = session.query(RewardRecord).filter_by(id=record_id).first()
    if record:
        record.count = count
        session.commit()
    session.close()
    return RedirectResponse("/admin/leaves?msg=已撤销", status_code=303)


# ---------- 配置管理 ----------

@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, msg: str = ""):
    return templates.TemplateResponse("config.html", {"request": request, "config": config, "msg": msg})


@router.post("/config")
async def config_save(
    cycle_start: str = Form(...),
    cycle_end: str = Form(...),
    holiday_start: str = Form(...),
    holiday_end: str = Form(...),
    leave_limit: int = Form(...),
):
    config.cycle_start = config._parse_date(cycle_start)
    config.cycle_end = config._parse_date(cycle_end)
    config.holiday_start = config._parse_date(holiday_start)
    config.holiday_end = config._parse_date(holiday_end)
    config.leave_limit = leave_limit
    config.save()
    return RedirectResponse("/admin/config?msg=配置已保存", status_code=303)


# ---------- 月报 ----------

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    today = datetime.now()
    # 默认上个自然月
    if today.month == 1:
        prev_start = datetime(today.year - 1, 12, 1)
        prev_end = datetime(today.year - 1, 12, 31)
    else:
        import calendar
        prev_month = today.month - 1
        last_day = calendar.monthrange(today.year, prev_month)[1]
        prev_start = datetime(today.year, prev_month, 1)
        prev_end = datetime(today.year, prev_month, last_day)
    return templates.TemplateResponse("report.html", {
        "request": request,
        "default_start": prev_start.strftime("%Y-%m-%d"),
        "default_end": prev_end.strftime("%Y-%m-%d"),
    })


@router.get("/report/download")
async def report_download(start_date: str, end_date: str):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    xlsx_bytes = generate_report_xlsx(start, end)

    filename = f"report_{start_date}_{end_date}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
