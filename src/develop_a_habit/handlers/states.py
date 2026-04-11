from aiogram.fsm.state import State, StatesGroup


class HabitStates(StatesGroup):
    waiting_name = State()
    waiting_rename = State()


class DiaryStates(StatesGroup):
    waiting_diary_text = State()
