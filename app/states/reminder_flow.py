from aiogram.fsm.state import State, StatesGroup


class ReminderFlow(StatesGroup):
    waiting_for_text = State()
    waiting_for_recipients = State()
    waiting_for_date = State()
    waiting_for_weekday = State()
    waiting_for_time = State()
