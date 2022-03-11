"""
Utility functions
"""
from datetime import datetime, timedelta
import time


def ceil_dt(dt: datetime, delta: timedelta =timedelta(minutes=30)) -> datetime:
    """Ceils a datetime to the nearest timedelta

    Parameters
    ----------
    dt : datetime
        The datetime to ceil
    delta : timedelta, optional
        The timedelta to ceil to, by default timedelta(minutes=30)

    Returns
    -------
    datetime
        The ceiled datetime
    """
    # TODO: instead of ceil_dt, round_dt should be used
    return dt + (datetime.min - dt) % delta


def get_closest_clock_emoji(datetime: datetime) -> str:
    """Returns the clock emoji that most closely matches the given datetime

    Parameters
    ----------
    datetime : datetime
        The datetime to get the closest clock emoji of

    Returns
    -------
    str
        The clock emoji that was gotten
    """
    emojis = {
        "1:00": "🕐",
        "1:30": "🕜",
        "2:00": "🕑",
        "2:30": "🕝",
        "3:00": "🕒",
        "3:30": "🕞",
        "4:00": "🕓",
        "4:30": "🕟",
        "5:00": "🕔",
        "5:30": "🕠",
        "6:00": "🕕",
        "6:30": "🕡",
        "7:00": "🕖",
        "7:30": "🕢",
        "8:00": "🕗",
        "8:30": "🕣",
        "9:00": "🕘",
        "9:30": "🕤",
        "10:00": "🕙",
        "10:30": "🕥",
        "11:00": "🕚",
        "11:30": "🕦",
        "0:00": "🕛",
        "0:30": "🕧",
    }
    # The `% 12` is there to make it 12 hour time instead of 24 hour time
    return emojis[f"{ceil_dt(datetime).hour % 12}:{ceil_dt(datetime).minute:02}"]


def datetime_from_utc_to_local(utc_datetime: datetime) -> datetime:
    """Converts a utc time to local time

    Parameters
    ----------
    utc_datetime : datetime
        The time in UTC

    Returns
    -------
    datetime
        The local time equivalent
    """
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


class cycle:
    def __init__(self, c):
        self._c = c
        self._index = -1

    def __next__(self):
        self._index += 1
        if self._index >= len(self._c):
            self._index = 0
        return self._c[self._index]

    def __previous__(self):
        self._index -= 1
        if self._index < 0:
            self._index = len(self._c) - 1
        return self._c[self._index]


def previous(c: cycle):
    return c.__previous__()
