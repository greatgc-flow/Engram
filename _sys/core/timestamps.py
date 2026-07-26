"""Shared ISO timestamp parsing with explicit naive-time policies."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo


def parse_iso_timestamp(
    value: object,
    *,
    naive_policy: str,
    assumed_timezone: tzinfo | None = None,
) -> datetime:
    """Parse ISO8601 and return UTC, applying only the requested naive policy."""
    text = str(value).strip()
    if not text:
        raise ValueError("empty timestamp")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if naive_policy == "reject":
            raise ValueError("naive timestamp has no timezone contract")
        if naive_policy == "assume_local":
            parsed = (
                parsed.replace(tzinfo=assumed_timezone)
                if assumed_timezone is not None
                else parsed.astimezone()
            )
        elif naive_policy == "assume_timezone" and assumed_timezone is not None:
            parsed = parsed.replace(tzinfo=assumed_timezone)
        else:
            raise ValueError(f"invalid naive timestamp policy: {naive_policy}")
    return parsed.astimezone(timezone.utc)
