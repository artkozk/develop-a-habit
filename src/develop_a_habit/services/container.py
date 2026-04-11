from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.services.diary_service import DiaryService
from develop_a_habit.services.habit_service import HabitService
from develop_a_habit.services.metrics_service import MetricsService
from develop_a_habit.services.user_service import UserService


@dataclass(slots=True)
class ServiceContainer:
    user_service: UserService
    habit_service: HabitService
    metrics_service: MetricsService
    diary_service: DiaryService


def build_services(session: AsyncSession) -> ServiceContainer:
    habit_service = HabitService(session)
    return ServiceContainer(
        user_service=UserService(session),
        habit_service=habit_service,
        metrics_service=MetricsService(habit_service=habit_service),
        diary_service=DiaryService(session),
    )
