from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return the current UTC time for timezone-naive DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def require_timezone(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须包含时区")


def to_utc_aware(value: datetime) -> datetime:
    require_timezone(value)
    return value.astimezone(timezone.utc)


def to_utc_naive(value: datetime) -> datetime:
    return to_utc_aware(value).replace(tzinfo=None)


def restore_utc_aware(value: datetime) -> datetime:
    """从数据库读取 UTC-naive，并恢复 UTC 时区。"""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
