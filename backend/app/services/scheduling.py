from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ScheduleType = str


def require_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("timezone must be a valid IANA timezone") from error


def _time_of_day(value: object) -> time:
    if not isinstance(value, str):
        raise TypeError("schedule requires time_of_day")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError("time_of_day must use HH:MM") from error
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ValueError("time_of_day must use HH:MM")
    return parsed


def _round_trip_valid(
    naive: datetime,
    timezone: ZoneInfo,
    *,
    fold: int,
) -> datetime | None:
    candidate = naive.replace(tzinfo=timezone, fold=fold)
    returned = candidate.astimezone(UTC).astimezone(timezone)
    if returned.replace(tzinfo=None) != naive:
        return None
    return candidate


def resolve_local_time(naive: datetime, timezone: ZoneInfo) -> datetime:
    candidate = naive
    for _ in range(24 * 60 + 1):
        first = _round_trip_valid(candidate, timezone, fold=0)
        second = _round_trip_valid(candidate, timezone, fold=1)
        if first is not None:
            if second is not None and first.utcoffset() != second.utcoffset():
                return first
            return first
        if second is not None:
            return second
        candidate += timedelta(minutes=1)
    raise ValueError("could not resolve local schedule time")


def _candidate_times(
    *,
    schedule_type: ScheduleType,
    schedule_config: Mapping[str, object],
    day: date,
) -> list[datetime]:
    if schedule_type == "every_6_hours":
        return [datetime.combine(day, time(hour=hour)) for hour in (0, 6, 12, 18)]
    scheduled_time = _time_of_day(schedule_config.get("time_of_day"))
    if schedule_type == "daily":
        return [datetime.combine(day, scheduled_time)]
    if schedule_type == "weekdays":
        return [datetime.combine(day, scheduled_time)] if day.weekday() < 5 else []
    if schedule_type == "weekly":
        weekday = schedule_config.get("weekday")
        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ValueError("weekly schedule requires weekday from 0 to 6")
        return (
            [datetime.combine(day, scheduled_time)]
            if day.weekday() == weekday
            else []
        )
    if schedule_type == "manual":
        return []
    raise ValueError("unsupported schedule_type")


def next_scheduled_time(
    *,
    schedule_type: ScheduleType,
    schedule_config: Mapping[str, object],
    timezone_name: str,
    after: datetime,
) -> datetime | None:
    if schedule_type == "manual":
        return None
    timezone = require_timezone(timezone_name)
    normalized_after = (
        after.replace(tzinfo=UTC) if after.tzinfo is None else after.astimezone(UTC)
    )
    local_start = normalized_after.astimezone(timezone)
    for offset in range(15):
        day = local_start.date() + timedelta(days=offset)
        for naive in _candidate_times(
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            day=day,
        ):
            candidate = resolve_local_time(naive, timezone).astimezone(UTC)
            if candidate > normalized_after:
                return candidate
    raise ValueError("could not find next schedule occurrence")
