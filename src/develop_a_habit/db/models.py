import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from develop_a_habit.db.base import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class HabitType(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class TimeSlot(str, enum.Enum):
    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"
    ALL_DAY = "all_day"


class ScheduleType(str, enum.Enum):
    DAILY = "daily"
    EVERY_OTHER_DAY = "every_other_day"
    SPECIFIC_WEEKDAYS = "specific_weekdays"


class CheckinStatus(str, enum.Enum):
    DONE = "done"
    MISSED = "missed"
    VIOLATED = "violated"
    OPTIONAL_DONE = "optional_done"


class DiaryEntryType(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    MIXED = "mixed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(128), default="Europe/Moscow")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    habits: Mapped[list["Habit"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    day_off_rules: Mapped[list["DayOffRule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    icon_emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    habit_type: Mapped[HabitType] = mapped_column(
        Enum(HabitType, name="habit_type", values_callable=_enum_values)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="habits")
    schedule_rules: Mapped[list["HabitScheduleRule"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan"
    )
    checkins: Mapped[list["HabitCheckin"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan"
    )


class HabitScheduleRule(Base):
    __tablename__ = "habit_schedule_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True)
    schedule_type: Mapped[ScheduleType] = mapped_column(
        Enum(ScheduleType, name="schedule_type", values_callable=_enum_values)
    )
    time_slot: Mapped[TimeSlot] = mapped_column(
        Enum(TimeSlot, name="time_slot", values_callable=_enum_values), index=True
    )
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    start_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    habit: Mapped[Habit] = relationship(back_populates="schedule_rules")


class DayOffRule(Base):
    __tablename__ = "day_off_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exact_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(back_populates="day_off_rules")


class HabitCheckin(Base):
    __tablename__ = "habit_checkins"
    __table_args__ = (
        UniqueConstraint("habit_id", "check_date", "time_slot", name="uq_habit_checkin_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True)
    check_date: Mapped[date] = mapped_column(Date, index=True)
    time_slot: Mapped[TimeSlot] = mapped_column(
        Enum(TimeSlot, name="time_slot", values_callable=_enum_values), index=True
    )
    status: Mapped[CheckinStatus] = mapped_column(
        Enum(CheckinStatus, name="checkin_status", values_callable=_enum_values)
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    habit: Mapped[Habit] = relationship(back_populates="checkins")


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    entry_type: Mapped[DiaryEntryType] = mapped_column(
        Enum(DiaryEntryType, name="diary_entry_type", values_callable=_enum_values)
    )
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="diary_entries")
    voice: Mapped["DiaryVoice | None"] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    transcript: Mapped["DiaryTranscript | None"] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class DiaryVoice(Base):
    __tablename__ = "diary_voice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("diary_entries.id", ondelete="CASCADE"), unique=True, index=True
    )
    telegram_file_id: Mapped[str] = mapped_column(String(256), index=True)
    telegram_file_unique_id: Mapped[str] = mapped_column(String(256), index=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entry: Mapped[DiaryEntry] = relationship(back_populates="voice")


class DiaryTranscript(Base):
    __tablename__ = "diary_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("diary_entries.id", ondelete="CASCADE"), unique=True, index=True
    )
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stt_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    entry: Mapped[DiaryEntry] = relationship(back_populates="transcript")


class WeeklyPrompt(Base):
    __tablename__ = "weekly_prompts"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_prompt_user_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    comment_saved: Mapped[bool] = mapped_column(Boolean, default=False)
