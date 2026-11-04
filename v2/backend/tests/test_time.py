from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.time import BUSINESS_TZ, to_business_time, utc_now


def test_utc_now_returns_aware_utc_datetime():
    value = utc_now()
    assert value.tzinfo is UTC
    assert value.utcoffset().total_seconds() == 0


def test_to_business_time_converts_utc_to_shanghai():
    value = datetime(2026, 11, 4, 0, 0, tzinfo=UTC)
    converted = to_business_time(value)
    assert converted.tzinfo == BUSINESS_TZ
    assert converted.isoformat() == "2026-11-04T08:00:00+08:00"


def test_to_business_time_treats_sqlite_naive_timestamp_as_utc():
    value = datetime(2026, 11, 4, 0, 0)
    converted = to_business_time(value)
    assert converted.tzinfo == ZoneInfo("Asia/Shanghai")
    assert converted.isoformat() == "2026-11-04T08:00:00+08:00"
