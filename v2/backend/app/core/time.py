"""Time helpers: persist UTC timestamps; convert to Asia/Shanghai at presentation boundaries."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_business_time(value: datetime) -> datetime:
    """Convert an aware UTC/database timestamp to the business timezone."""
    if value.tzinfo is None:
        # SQLite may return naive values for DateTime(timezone=True).
        value = value.replace(tzinfo=UTC)
    return value.astimezone(BUSINESS_TZ)
