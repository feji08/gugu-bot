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

# 定义随机前缀列表
SPY_PREFIXES = [
    "让我看看！哇，",
    "坏咕！你偷偷潜入数据库看了一眼，瞄见",
    "悄悄告诉你，",
    "千辛万苦把原著cp拆开后，你终于发现，",
    "一天的辛苦码字后，你闲来无事，发现",
    "坏咕偷偷看了一页设定卡，显示：",
    "坏咕！发现了一个惊天秘密，",
    "卧槽！",
    "坏咕被抓包了！但临走前偷看了一眼，",
    "让我们揭开谜底，答案是——",
    "通过层层加密，终于得知，",
    "唔，好奇心驱使下你查到了，",
    "调皮的坏咕又发现了什么？",
    "咕咕深夜赶稿后悄悄查到，"
]

leave_limit = 3
leave_start_date = datetime(2024, 12, 2)  # 请假周期从2024年9月2日开始
leave_end_date = datetime(2024, 12, 29  )  # 请假周期到2024年9月29日结束