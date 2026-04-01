import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

time_zone = ZoneInfo("Asia/Shanghai")

_config_path = Path(__file__).parent / "database" / "config.json"

def _default_dates():
    today = datetime.now(time_zone)
    import calendar
    last_day = calendar.monthrange(today.year, today.month)[1]
    return {
        "leave_limit": 0,
        "cycle_start": f"{today.year}-{today.month:02d}-01",
        "cycle_end": f"{today.year}-{today.month:02d}-{last_day}",
        "holiday_start": f"{today.year}-{today.month:02d}-01",
        "holiday_end": f"{today.year}-{today.month:02d}-05",
    }

_DEFAULTS = _default_dates()


class _Config:
    def __init__(self):
        self.leave_limit: int = 0
        self.cycle_start: datetime = datetime(2026, 4, 1, tzinfo=time_zone)
        self.cycle_end: datetime = datetime(2026, 4, 30, tzinfo=time_zone)
        self.holiday_start: datetime = datetime(2026, 2, 17, tzinfo=time_zone)
        self.holiday_end: datetime = datetime(2026, 2, 19, tzinfo=time_zone)
        self.load()

    def _parse_date(self, s: str) -> datetime:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=time_zone)

    def load(self):
        if _config_path.exists():
            with open(_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.leave_limit = data.get("leave_limit", _DEFAULTS["leave_limit"])
            self.cycle_start = self._parse_date(data.get("cycle_start", _DEFAULTS["cycle_start"]))
            self.cycle_end = self._parse_date(data.get("cycle_end", _DEFAULTS["cycle_end"]))
            self.holiday_start = self._parse_date(data.get("holiday_start", _DEFAULTS["holiday_start"]))
            self.holiday_end = self._parse_date(data.get("holiday_end", _DEFAULTS["holiday_end"]))

    def save(self):
        data = {
            "leave_limit": self.leave_limit,
            "cycle_start": self.cycle_start.strftime("%Y-%m-%d"),
            "cycle_end": self.cycle_end.strftime("%Y-%m-%d"),
            "holiday_start": self.holiday_start.strftime("%Y-%m-%d"),
            "holiday_end": self.holiday_end.strftime("%Y-%m-%d"),
        }
        with open(_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


config = _Config()
