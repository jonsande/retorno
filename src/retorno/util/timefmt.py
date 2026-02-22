from __future__ import annotations


def _split_time(seconds: float) -> tuple[int, int, int, int, int]:
    s = int(seconds)
    total_days = s // 86400
    hours = (s % 86400) // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    return s, total_days, hours, mins, secs


def _humanize_year(year: int) -> str:
    if year >= 1_000_000_000:
        return f"{year / 1_000_000_000:.1f}B"
    if year >= 1_000_000:
        return f"{year / 1_000_000:.1f}M"
    if year >= 1_000:
        return f"{year / 1_000:.1f}k"
    return str(year)


def format_elapsed_long(seconds: float) -> str:
    _, total_days, hours, mins, secs = _split_time(seconds)
    if total_days < 365:
        return f"Day {total_days + 1} {hours:02d}:{mins:02d}:{secs:02d}"
    year = total_days // 365 + 1
    day = total_days % 365 + 1
    if year < 10_000:
        return f"Year {year:,} Day {day} {hours:02d}:{mins:02d}:{secs:02d}"
    year_short = _humanize_year(year)
    return f"Year {year_short} +{day}d {hours:02d}:{mins:02d}:{secs:02d}"


def format_elapsed_short(seconds: float, include_seconds: bool = False) -> str:
    _, total_days, hours, mins, secs = _split_time(seconds)
    time_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if include_seconds else f"{hours:02d}:{mins:02d}"
    if total_days < 365:
        return f"T+Y1 D{total_days + 1} {time_str}"
    year = total_days // 365 + 1
    day = total_days % 365 + 1
    if year < 10_000:
        return f"T+Y{year} D{day} {time_str}"
    year_short = _humanize_year(year)
    return f"T+Y{year_short} +{day}d {time_str}"
