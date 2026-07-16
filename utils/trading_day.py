import datetime
import requests
from typing import Optional

CN_HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-22", "2026-01-23", "2026-01-24", "2026-01-25", "2026-01-26",
    "2026-01-27", "2026-01-28", "2026-04-04", "2026-04-05", "2026-04-06",
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    "2026-06-19", "2026-06-20", "2026-06-21",
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05",
    "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"
]

CN_WEEKENDS = [5, 6]


def is_trading_day(date: Optional[datetime.date] = None) -> bool:
    if date is None:
        date = datetime.date.today()

    if date.weekday() in CN_WEEKENDS:
        return False

    date_str = date.strftime("%Y-%m-%d")
    if date_str in CN_HOLIDAYS_2026:
        return False

    return True


def is_today_trading_day() -> bool:
    return is_trading_day()


def get_next_trading_day(date: Optional[datetime.date] = None) -> datetime.date:
    if date is None:
        date = datetime.date.today()

    next_day = date + datetime.timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += datetime.timedelta(days=1)
    return next_day


def get_last_trading_day(date: Optional[datetime.date] = None) -> datetime.date:
    if date is None:
        date = datetime.date.today()

    last_day = date - datetime.timedelta(days=1)
    while not is_trading_day(last_day):
        last_day -= datetime.timedelta(days=1)
    return last_day


def get_trading_days_in_month(year: int, month: int) -> list[datetime.date]:
    trading_days = []
    for day in range(1, 32):
        try:
            date = datetime.date(year, month, day)
            if is_trading_day(date):
                trading_days.append(date)
        except ValueError:
            break
    return trading_days