"""Trim points in seconds on the original audio timeline."""

import math


def trim_points(value):
    if value is None:
        return 0, None
    if not isinstance(value, dict):
        raise ValueError("Invalid trim selection.")
    start, end = value.get("start"), value.get("end")
    if (
        any(
            type(point) not in (int, float) or not 0 <= point <= 86400 or not math.isfinite(point)
            for point in (start, end)
            if point is not None
        )
        or start is None
        or (end is not None and end <= start)
    ):
        raise ValueError("Choose an end time after the start time.")
    return start, end
