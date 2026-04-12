from __future__ import annotations

from datetime import datetime


def is_weekly_digest_due(local_now: datetime) -> bool:
    """Return True when it's Sunday 17:30+ in user's local timezone."""
    return local_now.weekday() == 6 and (
        local_now.hour > 17 or (local_now.hour == 17 and local_now.minute >= 30)
    )
