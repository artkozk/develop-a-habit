from aiogram.fsm.state import State, StatesGroup


class HabitStates(StatesGroup):
    waiting_name = State()
    waiting_rename = State()
