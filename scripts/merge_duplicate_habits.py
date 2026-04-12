#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from develop_a_habit.db.models import User
from develop_a_habit.db.session import AsyncSessionFactory
from develop_a_habit.services import build_services


async def run(telegram_user_id: int | None) -> int:
    async with AsyncSessionFactory() as session:
        services = build_services(session)
        if telegram_user_id is None:
            users = await services.user_service.list_users()
        else:
            user = await session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
            users = [user] if user is not None else []

        total_merged = 0
        for user in users:
            merged = await services.habit_service.merge_duplicate_habits_by_name(user.id)
            if merged:
                print(
                    f"user_id={user.id} telegram_user_id={user.telegram_user_id}: merged {merged} duplicate habits"
                )
            total_merged += merged

        if total_merged == 0:
            print("No duplicate habits found")
        else:
            print(f"Total merged duplicates: {total_merged}")
        return total_merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate habits by normalized name")
    parser.add_argument(
        "--telegram-user-id",
        type=int,
        default=None,
        help="Optional telegram user id. If omitted, all users are processed.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.telegram_user_id))


if __name__ == "__main__":
    main()
