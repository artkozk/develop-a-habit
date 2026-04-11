from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.services.habit_service import HabitService
from develop_a_habit.services.metrics_service import MetricsService


@dataclass(slots=True)
class HtmlReportResult:
    file_path: Path


class StatsReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.metrics_service = MetricsService(HabitService(session))

    async def generate_yearly_html(self, user_id: int, telegram_user_id: int, year: int | None = None) -> HtmlReportResult:
        year = year or date.today().year

        start = date(year, 1, 1)
        end = date(year, 12, 31)
        summary = await self.metrics_service.compute_period_metrics(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )

        months: list[dict[str, object]] = []
        for month in range(1, 13):
            month_start = date(year, month, 1)
            _, month_days = calendar.monthrange(year, month)
            month_end = date(year, month, month_days)
            metrics = await self.metrics_service.compute_period_metrics(
                user_id=user_id,
                start_date=month_start,
                end_date=month_end,
            )
            months.append(
                {
                    "month_name": calendar.month_name[month],
                    "plan_slots": metrics.plan_slots,
                    "completed_slots": metrics.completed_slots,
                    "extra_slots": metrics.extra_slots,
                    "plan_completion": metrics.plan_completion,
                    "over_completion": metrics.over_completion,
                }
            )

        weeks: list[dict[str, object]] = []
        current = date.today() - timedelta(days=date.today().weekday())
        for _ in range(8):
            week_start = current
            week_end = week_start + timedelta(days=6)
            metrics = await self.metrics_service.compute_period_metrics(
                user_id=user_id,
                start_date=week_start,
                end_date=week_end,
            )
            weeks.append(
                {
                    "label": f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}",
                    "over_completion": metrics.over_completion,
                    "bar_width": min(int(metrics.over_completion), 200),
                }
            )
            current = current - timedelta(days=7)

        template_env = Environment(
            loader=FileSystemLoader("src/develop_a_habit/templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = template_env.get_template("stats_report.html.j2")
        html = template.render(
            year=year,
            telegram_user_id=telegram_user_id,
            summary={
                "plan_slots": summary.plan_slots,
                "completed_slots": summary.completed_slots,
                "extra_slots": summary.extra_slots,
                "plan_completion": summary.plan_completion,
                "over_completion": summary.over_completion,
            },
            months=months,
            weeks=weeks,
        )

        exports_dir = Path("exports")
        exports_dir.mkdir(parents=True, exist_ok=True)
        file_path = exports_dir / f"stats_report_{telegram_user_id}_{year}.html"
        file_path.write_text(html, encoding="utf-8")
        return HtmlReportResult(file_path=file_path)
