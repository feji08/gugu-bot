from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

time_zone = ZoneInfo("Asia/Shanghai")
def get_current_time():
    now_china = datetime.now(time_zone)
    return now_china
def get_time_window(current_day):
    time_start = datetime.combine(current_day, datetime.min.time(), tzinfo=time_zone)
    time_end = time_start + timedelta(hours=24)
    return time_start, time_end
def get_week_dates(current_time):
    # 为确保有昨天数据，计算上周一的日期 now.weekday() 0-6表示周一到周日
    today = datetime.combine(current_time.date(), datetime.min.time(), tzinfo=time_zone)
    start_of_last_week = today - timedelta(days=today.weekday()+7)
    # 生成从上周一到今天的日期
    dates = [start_of_last_week + timedelta(days=i)
             for i in range((current_time - start_of_last_week).days + 1)]
    return dates

# print(get_week_dates(get_current_time()))

def get_week_range(current_time):
    # 计算本周一的日期 now.weekday() 0-6表示周一到周日
    today = datetime.combine(current_time, datetime.min.time(), tzinfo=time_zone)
    start_of_week = today - timedelta(days=today.weekday())
    # 计算下周一的日期
    end_of_week = start_of_week + timedelta(days=7)
    return start_of_week, end_of_week

# print(get_week_range(get_current_time()))

leave_limit = 3
leave_start_date = datetime(2024, 12, 2)  # 请假周期从2024年9月2日开始
leave_end_date = datetime(2024, 12, 29  )  # 请假周期到2024年9月29日结束