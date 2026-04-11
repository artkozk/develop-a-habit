from aiogram.fsm.state import State, StatesGroup


class HabitStates(StatesGroup):
    waiting_name = State()
    waiting_icon = State()
    waiting_sport_target = State()
    waiting_sport_step = State()
    waiting_sport_update_target = State()
    waiting_sport_update_step = State()
    waiting_rename = State()


class DiaryStates(StatesGroup):
    waiting_diary_text = State()
    waiting_diary_voice = State()


class SearchStates(StatesGroup):
    waiting_search_query = State()


class WeeklyStates(StatesGroup):
    waiting_weekly_comment = State()
