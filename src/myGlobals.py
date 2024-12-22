from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

time_zone = ZoneInfo("Asia/Shanghai")
def get_current_day(timezone):
    now_china = datetime.now(timezone)
    return now_china
def get_time_window(current_day):
    time_start = datetime.combine(current_day, datetime.min.time(), tzinfo=ZoneInfo("Asia/Shanghai"))
    time_end = time_start + timedelta(hours=24)
    return time_start, time_end

leave_limit = 3
leave_start_date = datetime(2024, 12, 2)  # 请假周期从2024年9月2日开始
leave_end_date = datetime(2024, 12, 29  )  # 请假周期到2024年9月29日结束