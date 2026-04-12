from datetime import datetime

from develop_a_habit.jobs.schedule_utils import is_weekly_digest_due


def test_weekly_digest_due_from_1730_on_sunday():
    assert is_weekly_digest_due(datetime(2026, 4, 12, 17, 30)) is True
    assert is_weekly_digest_due(datetime(2026, 4, 12, 18, 5)) is True


def test_weekly_digest_not_due_before_1730_or_on_other_days():
    assert is_weekly_digest_due(datetime(2026, 4, 12, 17, 29)) is False
    assert is_weekly_digest_due(datetime(2026, 4, 13, 17, 30)) is False
