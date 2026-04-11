from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from develop_a_habit.services.habit_service import HabitService
from develop_a_habit.services.user_service import UserService


@dataclass(slots=True)
class ServiceContainer:
    user_service: UserService
    habit_service: HabitService


def build_services(session: AsyncSession) -> ServiceContainer:
    return ServiceContainer(
        user_service=UserService(session),
        habit_service=HabitService(session),
    )
